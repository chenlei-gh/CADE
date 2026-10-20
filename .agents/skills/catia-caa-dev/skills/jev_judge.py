"""
Jev Judgment Layer — semantic tie-breakers for ``analyze()``
============================================================
Jev (TypeSafe System One) answers narrow typed questions about *ordering*
and *wording*. It is **not** an evidence source. The repository contract is
explicit (``docs/AI_SKILL_ACTIVATION_FINDINGS.md`` §8):

    JEV 是审查器，不是证据源。

So this module is deliberately allowed to influence only two things:

1. Which degraded next action an agent is told to try **first** after the
   curated catalog returns nothing (``first_action``).
2. Whether a regex-extracted token **reads like** a CAA type identifier, so a
   NOT-FOUND verdict can be worded as "probably a typo/product name" instead
   of "confirmed absent" (``identifier_plausibility``).

Existence and attribution facts come only from the authoritative indexes
(``.dic`` / HeaderMap / MethodIndex / CAADoc). Nothing here may be quoted as
proof that an API exists.

Dependency policy
-----------------
``urllib.request`` from the standard library only. ``config/requirements.txt``
promises "No external dependencies — Python standard library only", so
``requests`` must not be imported here.

Fail-open behavior
------------------
Any problem (no key, offline, DNS failure, timeout, HTTP error, malformed
JSON, unexpected shape) returns ``None``. Callers then keep their deterministic
ordering. This layer must never raise into ``analyze()`` and must never add
latency to a path that is not already a degraded/negative verdict.

Controls
--------
``CADE_JEV=0``   disable unconditionally
``CADE_JEV=1``   enable if a key exists (same as the default)
``TYPESAFE_API_KEY``   required for any call; never logged

CLI (manual triage, not part of the analyze path)::

    python skills/jev_judge.py "如何在CAA中创建场景"
    python skills/jev_judge.py --names CATIAScene CATIA
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
DEFAULT_TIMEOUT = 6.0
MAX_RESPONSE_BYTES = 1 << 20

# Observability counters, same style as catalog.CACHE_STATS.
STATS: Dict[str, int] = {
    "calls": 0, "ok": 0, "skipped": 0, "failed": 0, "cache_hit": 0,
}

# The degraded path is deterministic per (state, questions), so a small
# process cache prevents repeated network calls when the same query is
# retried (test suites, agent re-invocation). Bounded, cleared wholesale.
_CACHE: Dict[str, Optional[dict]] = {}
_CACHE_MAX = 64

# Confidence below this is treated as "no opinion" — an uninformative
# distribution must not reorder a deterministic plan.
MIN_CONFIDENCE = 0.5

_OPTION_DESC = {
    "retrieval_health": (
        "Repair the retrieval layer first: the knowledge search itself may be "
        "broken, so any negative answer would be meaningless."
    ),
    "shipped_dic": (
        "Look the identifier up in the shipped .dic dictionary. This decides "
        "whether the name exists anywhere in the delivered product."
    ),
    "public_header": (
        "Look the identifier up in the PublicInterfaces header index. This "
        "decides whether it is callable public C++ CAA API."
    ),
    "caadoc": (
        "Browse CAADoc / the framework navigation files for design intent and "
        "documented usage. Explains how a confirmed API is meant to be used."
    ),
    "not_public_api": (
        "Treat the capability as outside the public C++ CAA API and switch to "
        "native / private investigation instead of guessing interface names."
    ),
}


def enabled() -> bool:
    """True when a Jev call is permitted in this process."""
    flag = os.environ.get("CADE_JEV", "").strip().lower()
    if flag in ("0", "false", "off", "no", "disable", "disabled"):
        return False
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


def evaluate(state, questions, timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    """POST one evaluation. Returns ``{model, answers, usage}`` or ``None``.

    Never raises and never logs the credential.
    """
    if not questions or not enabled():
        STATS["skipped"] += 1
        return None

    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        STATS["skipped"] += 1
        return None

    body = {"model": MODEL, "state": state, "questions": questions}
    try:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        logger.debug("Jev payload not serializable: %s", e)
        STATS["failed"] += 1
        return None

    cache_key = hashlib.sha1(payload).hexdigest()
    if cache_key in _CACHE:
        STATS["cache_hit"] += 1
        return _CACHE[cache_key]

    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
    )

    STATS["calls"] += 1
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES)
    except Exception as e:  # noqa: BLE001 - optional layer, must fail open
        STATS["failed"] += 1
        logger.debug("Jev request failed: %s", type(e).__name__)
        return None

    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        STATS["failed"] += 1
        logger.debug("Jev response unreadable: %s", type(e).__name__)
        return None

    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        STATS["failed"] += 1
        logger.debug("Jev response missing 'answers'")
        return None

    STATS["ok"] += 1
    result = {
        "model": data.get("model", ""),
        "answers": answers,
        "usage": data.get("usage", {}),
    }
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[cache_key] = result
    return result


def first_action(request: str, candidates: List[str], options: List[str],
                 catalog_healthy: bool = True,
                 timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    """Pick which degraded next action should be tried first.

    Returns ``{model, choice, confidence, probabilities, role}`` or ``None``.
    ``role`` is always ``"ordering-only"`` — callers must not surface this as
    a fact about the API.
    """
    allowed = [o for o in options if o in _OPTION_DESC]
    if len(allowed) < 2 or not enabled():
        return None

    state = {
        "agent_request": (request or "")[:800],
        "caa_identifiers_mentioned": list(candidates)[:6],
        "knowledge_catalog_healthy": bool(catalog_healthy),
        "candidate_next_actions": {o: _OPTION_DESC[o] for o in allowed},
    }
    questions = {
        "first_action": {
            "type": "choice",
            "instructions": (
                "A CATIA CAA development assistant could not answer the request "
                "from its curated knowledge base. Pick the single next action "
                "most likely to produce a grounded answer. Settle existence "
                "before explaining usage: prefer an action whose result can "
                "prove or disprove that the name exists. If the catalog itself "
                "may be broken, repair it before trusting any negative result."
            ),
            "criteria": {o: _OPTION_DESC[o] for o in allowed},
        }
    }

    resp = evaluate(state, questions, timeout=timeout)
    if not resp:
        return None

    answer = resp["answers"].get("first_action")
    if not isinstance(answer, dict):
        return None
    choice = answer.get("choice")
    if choice not in allowed:
        return None

    confidence = answer.get("confidence")
    if confidence is not None and confidence < MIN_CONFIDENCE:
        # A low-confidence ordering is not worth overriding a deterministic
        # one; report nothing rather than a coin flip dressed as a judgment.
        return None
    return {
        "model": resp.get("model", ""),
        "choice": choice,
        "confidence": confidence,
        "probabilities": answer.get("probabilities"),
        "role": "ordering-only",
    }


def is_knowledge_question(request: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    """Decide whether a request asks about CAA concepts rather than the workspace.

    Callers use this ONLY after their deterministic keyword tables miss, and
    only to choose a routing branch — never to assert a fact. Returns
    ``{model, probability, role}`` or ``None`` when Jev is unavailable.
    """
    text = (request or "").strip()
    if len(text) < 3 or not enabled():
        return None

    questions = {
        "is_knowledge": {
            "type": "noul",
            "instructions": (
                "Is `request` asking about CATIA CAA domain knowledge, APIs, "
                "concepts, or design practices, as opposed to asking the "
                "assistant to operate on a source workspace it has open?"
            ),
            "criteria": {
                "true": (
                    "Asks what/how/why about CAA features, interfaces, dialogs, "
                    "geometry, scenes, assembly, documentation, or a named API"
                ),
                "false": (
                    "Asks to list, analyze, build, fix, rename, roll back, or "
                    "otherwise operate on workspace modules, commands, or files"
                ),
            },
        }
    }
    resp = evaluate({"request": text[:1200]}, questions, timeout=timeout)
    if not resp:
        return None

    answer = resp["answers"].get("is_knowledge")
    if not isinstance(answer, dict):
        return None
    prob = answer.get("noul")
    if prob is None:
        return None
    return {
        "model": resp.get("model", ""),
        "probability": prob,
        "role": "routing-only",
    }


def identifier_plausibility(names: List[str], request: str = "",
                            timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    """Probability that each token reads like a declared CAA type name.

    Used only to soften or sharpen the wording of an already-deterministic
    NOT-FOUND verdict. Returns ``{model, probabilities, role}`` or ``None``.
    """
    seen: List[str] = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    if not seen or not enabled():
        return None

    questions = {}
    for n in seen[:6]:
        questions[n] = {
            "type": "noul",
            "instructions": (
                "Could `{n}` plausibly be the name of a CATIA CAA interface or "
                "component class, as opposed to a product name, a file name, or "
                "an ordinary word? The surrounding request is `{req}`."
            ).format(n=n, req=(request or "")[:300]),
            "criteria": {
                "true": "Reads like a declared C++/IDL CAA type name",
                "false": "Product name, prose, filename, or unrelated token",
            },
        }

    resp = evaluate(
        {"agent_request": (request or "")[:800], "names": seen},
        questions,
        timeout=timeout,
    )
    if not resp:
        return None

    probs: Dict[str, Optional[float]] = {}
    for n in questions:
        answer = resp["answers"].get(n)
        if isinstance(answer, dict):
            probs[n] = answer.get("noul")
    if not probs:
        return None
    return {
        "model": resp.get("model", ""),
        "probabilities": probs,
        "role": "wording-only",
    }


def judge_chain_relevance(request: str, candidate: dict,
                          timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    """Judge how relevant a recovered official call chain is to the user's intent.

    Role: 'review-only'. Jev (TypeSafe System One) provides semantic scoring
    to evaluate whether the recovered calling sequence logically answers the
    user's development request. Existence and attribution facts remain
    exclusively verified by local authoritative indexes (HeaderMap, MethodIndex).

    Returns ``{model, choice, confidence, probabilities, role}`` or ``None``.
    """
    if not candidate or not enabled():
        return None

    steps = candidate.get("steps", [])[:10]
    call_summary = []
    for s in steps:
        caller = s.get("caller_type") or s.get("caller_var") or s.get("caller", "")
        kind = s.get("kind", "")
        if kind == "query_interface":
            target_itf = s.get("target_type") or s.get("target") or ""
            res_var = s.get("result_var") or ""
            call_summary.append(f"{caller}->QueryInterface({target_itf}, &{res_var})")
        else:
            meth = s.get("method") or s.get("target") or ""
            args = s.get("args") or ""
            res = s.get("result_type") or s.get("result_var") or ""
            ret_str = f" => {res}" if res else ""
            call_summary.append(f"{caller}->{meth}({args}){ret_str}")

    state = {
        "user_request": (request or "")[:800],
        "usecase_name": str(candidate.get("usecase", "")),
        "source_file": str(candidate.get("file", "")),
        "connectivity_status": str(candidate.get("connectivity_status", "connected")),
        "key_interfaces": list(candidate.get("key_interfaces", []))[:8],
        "call_summary": call_summary,
    }

    questions = {
        "chain_relevance": {
            "type": "choice",
            "instructions": (
                "A CATIA CAA chain explorer recovered an official call sequence "
                "from a Dassault CAADoc sample. Judge how well this call sequence "
                "matches the user's CAA development requirement."
            ),
            "criteria": {
                "highly_relevant": (
                    "The recovered sequence directly demonstrates how to obtain, "
                    "instantiate, query, or mutate the target CAA object requested."
                ),
                "partially_relevant": (
                    "The sequence touches related concepts or domain objects, "
                    "but only provides a partial step or peripheral interaction."
                ),
                "not_relevant": (
                    "The sequence is unrelated to the user's actual goal despite "
                    "sharing a token or identifier."
                ),
            },
        }
    }

    resp = evaluate(state, questions, timeout=timeout)
    if not resp:
        return None

    answer = resp["answers"].get("chain_relevance")
    if not isinstance(answer, dict):
        return None

    choice = answer.get("choice")
    if choice not in ("highly_relevant", "partially_relevant", "not_relevant"):
        return None

    return {
        "model": resp.get("model", ""),
        "choice": choice,
        "confidence": answer.get("confidence"),
        "probabilities": answer.get("probabilities"),
        "role": "review-only",
    }


# ─── CLI ─────────────────────────────────────────────────────────

def _cli(argv: List[str]) -> int:
    if "--names" in argv:
        idx = argv.index("--names")
        names = [a for a in argv[idx + 1:] if not a.startswith("-")]
        if not names:
            print("usage: jev_judge.py --names <Name> [Name2 ...]")
            return 2
        out = identifier_plausibility(names)
    elif "--route" in argv:
        flags = {a for a in argv if a.startswith("-")}
        query = " ".join(a for a in argv if a not in flags)
        if not query:
            print("usage: jev_judge.py --route <request text>")
            return 2
        out = is_knowledge_question(query)
    else:
        flags = {a for a in argv if a.startswith("-")}
        query = " ".join(a for a in argv if a not in flags)
        if not query:
            print("usage: jev_judge.py <request text>")
            print("       jev_judge.py --route <request text>")
            print("       jev_judge.py --names <Name> [Name2 ...]")
            return 2
        options = [o for o in _OPTION_DESC
                   if o in ("shipped_dic", "public_header", "caadoc", "not_public_api")]
        out = first_action(query, [], options, catalog_healthy=True)

    if out is None:
        print("Jev unavailable (no key, CADE_JEV=0, or request failed).")
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv[1:]))
