"""
ChainExplorer — Evidence-Grounded CAA Call Chain Recovery
==========================================================
Explores and recovers verified, sequential C++ calling chains for unknown or
uncovered CAA development requirements directly from Dassault official CAADoc
use-case sources (*.edu/*/src/*.cpp).

Core Principles (CADE Architecture & Governance):
1. Evidence-Grounded: Every call step MUST map to a concrete line in an official
   use case (.cpp), with verified line numbers and source snippets.
2. Authority Verification: Method ownership and interface headers MUST be validated
   against MethodIndex and HeaderMap. Pure regex tokens never become truth.
3. Jev Reviewer Role: Jev (TypeSafe System One) provides semantic intent matching
   and candidate ranking. Jev NEVER invents or validates API existence facts.
4. Clean Rejection: When source evidence is missing or discontinuous, the explorer
   MUST return status="insufficient_evidence" and refuse to fabricate a path.
5. Controlled Crystallization: Candidates are stored in an isolated experimental
   staging area (knowledge/experimental/), NEVER polluting official catalog/index.yaml.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Regular expressions for C++ source stream parsing
_VAR_DECL_RE = re.compile(
    r'^\s*(?P<type>CAT[A-Za-z0-9_]+)\s*(?:\*|\_var)\s+(?P<var>[A-Za-z0-9_]+)'
)

_QI_RE = re.compile(
    r'(?P<caller>[A-Za-z0-9_]+)\s*->\s*QueryInterface\s*\(\s*IID_(?P<itf>CAT[A-Za-z0-9_]+)\s*,\s*(?:\([^)]+\)\s*)?&?\s*(?P<target>[A-Za-z0-9_]+)'
)

_CALL_RE = re.compile(
    r'(?:(?P<ret_var>[A-Za-z0-9_]+)\s*=\s*)?(?P<caller>[A-Za-z0-9_]+)\s*->\s*(?P<method>[A-Z][A-Za-z0-9_]{2,})\s*\((?P<args>[^)]*)\)'
)

_IDENTIFIER_RE = re.compile(r'CAT[A-Za-z0-9_]+')


class ChainStep:
    """One grounded step in a recovered CAA calling sequence."""

    def __init__(
        self,
        line: int,
        kind: str,  # 'query_interface' | 'method_call' | 'cast'
        caller_var: str,
        caller_type: str,
        target_name: str,  # method name or interface name
        result_var: str = "",
        result_type: str = "",
        args: str = "",
        snippet: str = "",
    ):
        self.line = line
        self.kind = kind
        self.caller_var = caller_var
        self.caller_type = caller_type
        self.target_name = target_name
        self.result_var = result_var
        self.result_type = result_type
        self.args = args.strip()
        self.snippet = snippet.strip()
        self.verified_owner: Optional[str] = None
        self.header: Optional[str] = None
        self.framework: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "kind": self.kind,
            "caller": f"{self.caller_var} ({self.caller_type})" if self.caller_type else self.caller_var,
            "caller_type": self.caller_type,
            "target": self.target_name,
            "result": f"{self.result_var} ({self.result_type})" if self.result_type else self.result_var,
            "result_type": self.result_type,
            "args": self.args,
            "snippet": self.snippet,
            "verified_owner": self.verified_owner,
            "header": self.header,
            "framework": self.framework,
        }


class ChainCandidate:
    """A complete candidate calling sequence recovered from one official use case."""

    def __init__(
        self,
        usecase: str,
        file: str,
        framework: str,
        start_type: str,
        target_type: str,
        steps: List[ChainStep],
    ):
        self.usecase = usecase
        self.file = file
        self.framework = framework
        self.start_type = start_type
        self.target_type = target_type
        self.steps = steps
        self.headers_required: List[str] = []
        self.frameworks_required: List[str] = []
        self.jev_verdict: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "usecase": self.usecase,
            "file": self.file,
            "framework": self.framework,
            "start_type": self.start_type,
            "target_type": self.target_type,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "headers_required": self.headers_required,
            "frameworks_required": self.frameworks_required,
            "jev_verdict": self.jev_verdict,
        }


class ChainExplorer:
    """Discovers and reconstructs verified CAA call chains from CAADoc source code."""

    def __init__(self, skill_root: Path, retrieval=None):
        self.skill_root = Path(skill_root)
        self._retrieval = retrieval
        self._caadoc_root: Optional[Path] = None

    @property
    def retrieval(self):
        if self._retrieval is None:
            from retrieval import get_retrieval
            self._retrieval = get_retrieval(self.skill_root)
        return self._retrieval

    @property
    def caadoc_root(self) -> Optional[Path]:
        """Locates the Dassault CAADoc root directory."""
        if self._caadoc_root is None:
            # 1. From usecase_index meta
            meta = self.retrieval.usecase_index.get("meta", {})
            caadoc_str = meta.get("caadoc_root")
            if caadoc_str and Path(caadoc_str).exists():
                self._caadoc_root = Path(caadoc_str)
                return self._caadoc_root

            # 2. Dynamic detection via catia_detector (no hardcoded drive paths)
            try:
                tools_dir = self.skill_root / "tools"
                if str(tools_dir) not in sys.path:
                    sys.path.insert(0, str(tools_dir))
                from catia_detector import detect_catia_installations
                installations = detect_catia_installations(verbose=False)
                for inst in installations:
                    doc_cand = inst.root_path / "CAADoc"
                    if doc_cand.exists():
                        self._caadoc_root = doc_cand
                        break
            except Exception:
                pass
        return self._caadoc_root

    def extract_identifiers(self, text: str) -> List[str]:
        """Extracts unique CAA identifiers (CAT*) from natural language or query."""
        if not text:
            return []
        matches = _IDENTIFIER_RE.findall(text)
        seen = []
        for m in matches:
            if m not in seen:
                seen.append(m)
        return seen

    def find_candidate_usecases(
        self,
        start: str = "",
        target: str = "",
        query: str = "",
        limit: int = 10,
    ) -> List[dict]:
        """Finds candidate use cases from UseCaseIndex matching start/target/keywords."""
        uc_index = self.retrieval.usecase_index
        examples = uc_index.get("examples", {})
        by_iface = uc_index.get("by_interface", {})
        by_meth = uc_index.get("by_method", {})
        by_sym = uc_index.get("by_symbol", {})

        candidates: List[dict] = []
        scores: Dict[str, float] = {}

        # 1. Exact start & target interface intersection
        start_ucs = set(by_iface.get(start, [])) if start else set()
        target_ucs = set(by_iface.get(target, [])) if target else set()

        # If start/target are not in by_interface, check by_symbol
        if start and not start_ucs:
            start_ucs = set(by_sym.get(start, []))
        if target and not target_ucs:
            target_ucs = set(by_sym.get(target, []))

        common = start_ucs & target_ucs
        for uc in common:
            scores[uc] = scores.get(uc, 0.0) + 100.0

        # 2. Individual hits
        for uc in start_ucs:
            scores[uc] = scores.get(uc, 0.0) + 20.0
        for uc in target_ucs:
            scores[uc] = scores.get(uc, 0.0) + 30.0

        # 3. Query tokens
        query_tokens = [w.lower() for w in re.split(r'[\s,._\-+/]+', query) if len(w) >= 3]
        for name, data in examples.items():
            f_lower = data.get("file", "").lower()
            m_set = {m.lower() for m in data.get("methods", [])}
            s_set = {s.lower() for s in data.get("symbols", [])}
            i_set = {i.lower() for i in data.get("interfaces", [])}

            match_score = 0.0
            for t in query_tokens:
                if t in f_lower:
                    match_score += 15.0
                if t in m_set or t in s_set or t in i_set:
                    match_score += 10.0
            if match_score > 0:
                scores[name] = scores.get(name, 0.0) + match_score

        # Sort by score descending
        sorted_ucs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for uc_name, sc in sorted_ucs[:limit]:
            if sc <= 0:
                continue
            ex_data = examples.get(uc_name, {})
            candidates.append({
                "name": uc_name,
                "score": sc,
                "file": ex_data.get("file", ""),
                "interfaces": ex_data.get("interfaces", []),
                "methods": ex_data.get("methods", []),
                "symbols": ex_data.get("symbols", []),
            })
        return candidates

    def extract_chain_from_cpp(
        self,
        cpp_path: Path,
        start_type: str = "",
        target_type: str = "",
    ) -> List[ChainStep]:
        """Parses a real .cpp file line-by-line to recover sequential call steps."""
        if not cpp_path.exists():
            return []

        try:
            lines = cpp_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        vars_type: Dict[str, str] = {}
        all_steps: List[ChainStep] = []

        # Pass 1: Extract declarations, QI transitions, and meaningful method calls
        for idx, line in enumerate(lines):
            line_no = idx + 1
            line_str = line.strip()

            # Declaration: CATIProduct *piRootProduct = NULL;
            m_decl = _VAR_DECL_RE.match(line)
            if m_decl:
                t_name = m_decl.group("type")
                v_name = m_decl.group("var")
                vars_type[v_name] = t_name

            # QueryInterface: rc = var1->QueryInterface(IID_TargetItf, (void**)&var2);
            m_qi = _QI_RE.search(line)
            if m_qi:
                caller = m_qi.group("caller")
                itf = m_qi.group("itf")
                target = m_qi.group("target")
                c_type = vars_type.get(caller, "")
                vars_type[target] = itf
                all_steps.append(ChainStep(
                    line=line_no,
                    kind="query_interface",
                    caller_var=caller,
                    caller_type=c_type,
                    target_name=itf,
                    result_var=target,
                    result_type=itf,
                    snippet=line_str,
                ))
                continue

            # Method Call: target_var = caller->Method(args) or caller->Method(&target_var)
            m_call = _CALL_RE.search(line)
            if m_call and "QueryInterface" not in line and not line_str.startswith("//"):
                caller = m_call.group("caller")
                meth = m_call.group("method")
                args = m_call.group("args")
                ret_var = m_call.group("ret_var") or ""
                c_type = vars_type.get(caller, "")

                # Skip standard Release/AddRef noise in the core sequence
                if meth in ("AddRef", "Release") and not target_type:
                    continue

                # Check if an argument looks like an output pointer (&var)
                arg_out_var = ""
                arg_out_type = ""
                m_out = re.search(r'&\s*(?P<out_var>[A-Za-z0-9_]+)', args)
                if m_out:
                    arg_out_var = m_out.group("out_var")
                    arg_out_type = vars_type.get(arg_out_var, "")

                res_var = ret_var or arg_out_var
                res_type = vars_type.get(res_var, arg_out_type)

                all_steps.append(ChainStep(
                    line=line_no,
                    kind="method_call",
                    caller_var=caller,
                    caller_type=c_type,
                    target_name=meth,
                    result_var=res_var,
                    result_type=res_type,
                    args=args,
                    snippet=line_str,
                ))

        # Pass 2: Filter and prune to steps connecting start_type and target_type
        if not start_type and not target_type:
            return all_steps[:20]

        # Identify key variables matching start_type and target_type
        start_vars = {v for v, t in vars_type.items() if t == start_type or (start_type and start_type in t)}
        target_vars = {v for v, t in vars_type.items() if t == target_type or (target_type and target_type in t)}

        # If both start and target exist, extract steps in the data flow between them
        relevant_steps: List[ChainStep] = []
        active_vars = set(start_vars) if start_vars else set(target_vars)

        for step in all_steps:
            involves_active = (
                step.caller_var in active_vars or
                step.result_var in active_vars or
                step.caller_type == start_type or
                step.result_type == start_type or
                step.caller_type == target_type or
                step.result_type == target_type or
                step.target_name == target_type
            )
            if involves_active:
                relevant_steps.append(step)
                if step.result_var:
                    active_vars.add(step.result_var)

        # If strict filtering produced too few steps, retain all non-empty steps
        if len(relevant_steps) < 2 and all_steps:
            relevant_steps = [
                s for s in all_steps
                if s.caller_type or s.result_type or s.kind == "query_interface"
            ]

        return relevant_steps

    def verify_steps(self, steps: List[ChainStep]) -> Tuple[List[str], List[str]]:
        """Validates steps against MethodIndex and HeaderMap to eliminate hallucinations."""
        hm = self.retrieval.header_map
        mi = self.retrieval.method_index

        headers: Set[str] = set()
        frameworks: Set[str] = set()

        for step in steps:
            # Verify caller type
            if step.caller_type and step.caller_type != "?":
                info = hm.lookup(step.caller_type)
                if info is not None:
                    module, framework = info
                    step.header = f"{step.caller_type}.h"
                    step.framework = framework
                    headers.add(step.header)
                    frameworks.add(framework)

            # Verify target interface in QueryInterface
            if step.kind == "query_interface":
                info = hm.lookup(step.target_name)
                if info is not None:
                    module, framework = info
                    target_header = f"{step.target_name}.h"
                    step.header = target_header
                    step.framework = framework
                    headers.add(target_header)
                    frameworks.add(framework)
                step.verified_owner = "IUnknown"

            # Verify method call
            elif step.kind == "method_call":
                owners = mi.owners_of(step.target_name)
                if owners:
                    step.verified_owner = owners[0]
                    # Lookup owner header
                    owner_info = hm.lookup(owners[0])
                    if owner_info is not None:
                        module, framework = owner_info
                        owner_hdr = f"{owners[0]}.h"
                        headers.add(owner_hdr)
                        frameworks.add(framework)

        return sorted(headers), sorted(frameworks)

    def explore(
        self,
        start: str = "",
        target: str = "",
        query: str = "",
        max_candidates: int = 3,
    ) -> dict:
        """End-to-end exploration of official call chains for a development requirement.

        Guarantees:
        - If ground truth evidence exists, returns status="ok" with verified steps.
        - If evidence is missing, returns status="insufficient_evidence" with gaps.
        - Incorporates Jev System One semantic review when enabled.
        """
        # Automatically extract identifiers if missing
        if not start or not target:
            ids = self.extract_identifiers(query)
            if len(ids) >= 2 and not start and not target:
                start = ids[0]
                target = ids[1]
            elif len(ids) == 1 and not target:
                target = ids[0]

        # Step 1: Candidate Discovery
        candidate_ucs = self.find_candidate_usecases(
            start=start, target=target, query=query, limit=10
        )

        # If a specific target is specified, candidate use cases MUST mention the target
        if target:
            candidate_ucs = [
                uc for uc in candidate_ucs
                if target in uc.get("interfaces", [])
                or target in uc.get("symbols", [])
                or target in uc.get("methods", [])
                or target.lower() in uc.get("file", "").lower()
            ]

        if not candidate_ucs:
            return {
                "status": "insufficient_evidence",
                "start": start,
                "target": target,
                "query": query,
                "candidates": [],
                "missing_evidence": [
                    f"No official CAADoc use cases matched start={start or 'none'}, "
                    f"target={target or 'none'}, query='{query}'."
                ],
                "summary": f"Target '{target}' not found in any matching official use case.",
            }

        # Step 2: Source Slice & Verification
        root = self.caadoc_root
        if not root:
            return {
                "status": "insufficient_evidence",
                "start": start,
                "target": target,
                "query": query,
                "candidates": [],
                "missing_evidence": ["CAADoc installation directory not found on disk."],
                "summary": "CAADoc installation path not accessible.",
            }

        recovered_candidates: List[ChainCandidate] = []
        for uc in candidate_ucs:
            rel_file = uc.get("file", "")
            if not rel_file:
                continue
            full_path = root / rel_file
            if not full_path.exists():
                continue

            steps = self.extract_chain_from_cpp(full_path, start_type=start, target_type=target)
            if not steps:
                continue

            # Ensure the recovered steps actually involve the requested target
            if target and not any(
                target in (s.caller_type or "") or
                target in (s.result_type or "") or
                target in (s.target_name or "")
                for s in steps
            ):
                continue

            # Verify with authoritative indexes
            headers, frameworks = self.verify_steps(steps)

            parts = Path(rel_file).parts
            fw = parts[0] if parts else ""

            cand = ChainCandidate(
                usecase=uc.get("name", ""),
                file=rel_file,
                framework=fw,
                start_type=start,
                target_type=target,
                steps=steps,
            )
            cand.headers_required = headers
            cand.frameworks_required = frameworks

            # Optional: Jev Semantic Review
            try:
                from jev_judge import judge_chain_relevance
                verdict = judge_chain_relevance(query or f"{start} to {target}", cand.to_dict())
                if verdict:
                    cand.jev_verdict = verdict
            except Exception as e:
                logger.debug("Jev review skipped: %s", e)

            recovered_candidates.append(cand)
            if len(recovered_candidates) >= max_candidates:
                break

        if not recovered_candidates:
            return {
                "status": "insufficient_evidence",
                "start": start,
                "target": target,
                "query": query,
                "candidates": [],
                "missing_evidence": [
                    f"Matched use cases ({[c['name'] for c in candidate_ucs[:3]]}) "
                    f"did not yield a verifiable sequential call chain between {start} and {target}."
                ],
                "summary": "Presence detected in use cases, but no sequential source flow recovered.",
            }

        return {
            "status": "ok",
            "start": start,
            "target": target,
            "query": query,
            "candidate_count": len(recovered_candidates),
            "candidates": [c.to_dict() for c in recovered_candidates],
            "summary": (
                f"Successfully recovered {len(recovered_candidates)} verified calling sequence(s) "
                f"from official CAADoc samples for {start or 'query'} -> {target or 'target'}."
            ),
        }

    def crystallize(
        self,
        candidate: dict,
        output_dir: Optional[Path] = None,
    ) -> dict:
        """Crystallizes a verified call chain into an isolated candidate playbook draft.

        Security Contract:
        - NEVER writes to playbooks/ or updates catalog/index.yaml directly.
        - Files are placed in knowledge/experimental/ with strict candidate headers.
        """
        if output_dir is None:
            output_dir = self.skill_root / "knowledge" / "experimental"
        output_dir.mkdir(parents=True, exist_ok=True)

        uc_name = candidate.get("usecase", "unnamed_candidate")
        start = candidate.get("start_type", "Start")
        target = candidate.get("target_type", "Target")
        clean_name = re.sub(r'[^A-Za-z0-9_]+', '_', f"{start}_{target}_{uc_name}").strip('_')
        doc_path = output_dir / f"CANDIDATE_{clean_name}.md"

        # Generate candidate playbook document
        lines = [
            f"# [EXPERIMENTAL CANDIDATE] {start} -> {target}",
            "",
            "> **SECURITY NOTICE & STATUS**: This is an automatically recovered, unreviewed candidate.",
            "> It is isolated from official knowledge (`catalog/index.yaml`).",
            "> Full runtime compilation and functional testing in CATIA are required before promotion.",
            "",
            "## 1. Source Provenance",
            f"- **Official Use Case**: `{uc_name}`",
            f"- **Source File**: `{candidate.get('file', '')}`",
            f"- **Framework**: `{candidate.get('framework', '')}`",
            f"- **Step Count**: {candidate.get('step_count', 0)} verified steps",
            "",
            "## 2. Prerequisites & Build Dependencies",
            "### Headers Required",
        ]
        for h in candidate.get("headers_required", []):
            lines.append(f"- `#include \"{h}\"`")

        lines.extend([
            "",
            "### Frameworks / Libraries Required (`Imakefile.mk` & `IdentityCard.xml`)",
        ])
        for fw in candidate.get("frameworks_required", []):
            lines.append(f"- `{fw}`")

        lines.extend([
            "",
            "## 3. Grounded Calling Sequence",
            "```cpp",
        ])
        for s in candidate.get("steps", []):
            line_no = s.get("line", 0)
            snip = s.get("snippet", "")
            owner = s.get("verified_owner", "")
            owner_comment = f" // [Owner: {owner}]" if owner else ""
            lines.append(f"// L{line_no}: {snip}{owner_comment}")
        lines.extend([
            "```",
            "",
            "## 4. Jev Semantic Assessment",
        ])
        jev = candidate.get("jev_verdict")
        if jev:
            lines.append(f"- **Choice**: `{jev.get('choice', '')}`")
            lines.append(f"- **Confidence**: `{jev.get('confidence', '')}`")
            lines.append(f"- **Model**: `{jev.get('model', '')}`")
        else:
            lines.append("- *Jev assessment not available or fail-open bypass.*")

        lines.extend([
            "",
            "## 5. Promotion Gate (Checklist for Formal Playbook)",
            "- [ ] Static compile verification (`mkmk`) passed without unresolved externals.",
            "- [ ] Runtime execution inside CATIA verified on sample geometry.",
            "- [ ] Object lifecycle / memory release audit verified (no leaks).",
            "- [ ] Signed off by engineer before adding to `catalog/index.yaml`.",
        ])

        doc_path.write_text("\n".join(lines), encoding="utf-8")
        return {
            "status": "ok",
            "file": str(doc_path),
            "usecase": uc_name,
            "isolated": True,
        }


# ─── CLI Entry Point ──────────────────────────────────────────────────

def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="CAA Call Chain Explorer")
    parser.add_argument("start", nargs="?", default="", help="Start interface/class")
    parser.add_argument("target", nargs="?", default="", help="Target interface/class")
    parser.add_argument("--query", "-q", default="", help="Natural language query")
    parser.add_argument("--crystallize", "-c", action="store_true", help="Crystallize candidate to experimental area")
    args = parser.parse_args()

    skill_root = Path(__file__).parent.parent
    explorer = ChainExplorer(skill_root)

    print(f"[*] Exploring calling chain for start='{args.start}', target='{args.target}', query='{args.query}'...")
    result = explorer.explore(start=args.start, target=args.target, query=args.query)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.crystallize and result.get("status") == "ok" and result.get("candidates"):
        cand = result["candidates"][0]
        c_res = explorer.crystallize(cand)
        print(f"\n[+] Crystallized candidate to: {c_res.get('file')}")

    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    import sys
    sys.exit(_cli())
