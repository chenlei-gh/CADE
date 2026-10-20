"""
ChainExplorer — Evidence-Grounded CAA Call Chain Recovery
==========================================================
Explores and recovers grounded C++ calling sequences for unknown or uncovered
CAA development requirements directly from Dassault official CAADoc use-case
sources (*.edu/*/src/*.cpp).

Core Principles (CADE Architecture & Governance):
1. Evidence-Grounded: Every call step MUST map to a concrete line in an official
   use case (.cpp), with verified line numbers and source snippets.
2. Authority Verification: Method ownership and interface headers MUST be validated
   against MethodIndex and HeaderMap. Pure regex tokens never become truth.
3. Def-Use Dataflow Rigor: Call steps must be connected by explicit variable def-use
   chains or QueryInterface transitions. Unconnected fragments must NEVER be
   claimed as verified call chains.
4. Non-Verified Candor: Static extraction and index checks prove source grounding,
   NOT compiler or runtime correctness. The evidence tier is explicitly labeled
   as "grounded_candidate_chain" or "candidate_fragment", NEVER "verified".
5. Method Owner Disambiguation: Multiple method owners are disambiguated by caller_type
   inheritance, NEVER by arbitrary owners[0] selection.
6. Jev Reviewer Role: Jev (TypeSafe System One) provides semantic intent matching
   and candidate ranking. Jev NEVER invents or validates API existence facts.
7. Clean Rejection: When source evidence is missing or discontinuous, the explorer
   MUST return status="insufficient_evidence" and refuse to fabricate a path.
8. Controlled Crystallization: Candidates are stored in an isolated experimental
   staging area (knowledge/experimental/), without overwriting existing files and
   NEVER polluting official catalog/index.yaml.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Regular expressions for C++ source stream parsing
_VAR_DECL_RE = re.compile(
    r'^\s*(?P<type>CAT[A-Za-z0-9_]+)(?:_var\b\s*|\s*\*|\*\s*)\s*(?P<var>[A-Za-z0-9_]+)'
)

_QI_RE = re.compile(
    r'(?P<caller>[A-Za-z0-9_]+)\s*(?:->|\.)\s*QueryInterface\s*\(\s*(?:IID_)?(?P<itf>CAT[A-Za-z0-9_]+)\s*,\s*(?:\([^)]+\)\s*)?&?\s*(?P<target>[A-Za-z0-9_]+)'
)

_CALL_RE = re.compile(
    r'(?:(?:(?P<decl_type>CAT[A-Za-z0-9_]+)(?:_var\b\s*|\s*\*|\*\s*)\s*)?(?P<ret_var>[A-Za-z0-9_]+)\s*=\s*)?(?P<caller>[A-Za-z0-9_]+)\s*(?:->|\.)\s*(?P<method>[A-Z][A-Za-z0-9_]{2,})\s*\((?P<args>[^)]*)\)'
)

_IDENTIFIER_RE = re.compile(r'CAT[A-Za-z0-9_]+')

_ERROR_CHECK_RE = re.compile(
    r'if\s*\(\s*(?:FAILED\s*\([^)]+\)|!\s*[A-Za-z0-9_]+|[A-Za-z0-9_]+\s*!=\s*(?:S_OK|NULL|0)|SUCCEEDED\s*\([^)]+\)\s*==\s*FALSE)',
    re.IGNORECASE
)

_HRESULT_STATUS_RE = re.compile(
    r'\b(?:FAILED|SUCCEEDED)\s*\(\s*(?P<status>[A-Za-z0-9_]+)\s*\)'
)

_UNSUPPORTED_CPP_RE = re.compile(
    r'(?:template\s*<|\boperator\s*\(|#\s*(?:define|undef|if|ifdef|ifndef|elif|else)\b|\bgoto\b|\[[^\]]*\]\s*\([^\)]*\)\s*\{|R"[^(]*\()',
    re.IGNORECASE
)

_STATUS_VARS = {"rc", "hr", "ret", "res", "status", "hresult"}

# (method, 0-based argument index of the proven out-parameter).
# Name-only matching is not an output contract. Index 0 is the first argument,
# never "the first CAT* token". Official B28 use is
# GetSpecContainer(pIContainerOnSpecContainer): the sole argument is the out slot.
_KNOWN_CAA_OUT_SIGNATURES = {
    ("GetSpecContainer", 0),
    ("GetRootProduct", 0),
    ("GetActiveSheet", 0),
}

# Single-line unbraced control-flow statement. The body is not a proven main-path step.
_UNBRACED_CTRL_RE = re.compile(
    r'^\s*(?:if|else\s+if|else|while|for|switch)\b',
    re.IGNORECASE
)

_STRINGISH_RE = re.compile(
    r'R"[^(]*\(.*?\)[^"]*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
    re.DOTALL,
)

# (function_scope, lexical_scope_id, variable, definition_id)
# Scope-isolated and versioned Def-Use tracking.
DefKey = Tuple[str, int, str, int]


def _is_safe_subpath(child: Path, parent: Path) -> bool:
    """Verifies that child path is strictly inside parent directory using path parts."""
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except (ValueError, AttributeError):
        c_parts = child.resolve().parts
        p_parts = parent.resolve().parts
        return len(c_parts) >= len(p_parts) and c_parts[:len(p_parts)] == p_parts


def _directed_types(text: str) -> Optional[Tuple[str, str]]:
    """Return (start, target) only when the text states a direction."""
    request = text or ""
    m_from_to = re.search(
        r'(?:从|from)\s*(CAT[A-Za-z0-9_]+)\s*(?:到|至|to|获取|提取|转为|转换到)\s*(CAT[A-Za-z0-9_]+)',
        request,
        re.IGNORECASE,
    )
    if m_from_to:
        return m_from_to.group(1), m_from_to.group(2)
    m_get_from = re.search(
        r'(?:获取|得到|创建|查询|get|retrieve|create)\s*(CAT[A-Za-z0-9_]+)\s*(?:从|通过|via|from)\s*(CAT[A-Za-z0-9_]+)',
        request,
        re.IGNORECASE,
    )
    if m_get_from:
        return m_get_from.group(2), m_get_from.group(1)
    m_arrow = re.search(
        r'\b(CAT[A-Za-z0-9_]+)\s*(?:到|->|to)\s*(CAT[A-Za-z0-9_]+)\b',
        request,
        re.IGNORECASE,
    )
    if m_arrow:
        return m_arrow.group(1), m_arrow.group(2)
    return None


def _exact_type(left: str, right: str) -> bool:
    """Exact type equality. Substring containment is never a type match."""
    return bool(left) and bool(right) and left == right


def _normalize_type(name: str) -> str:
    """Drop pointer/reference/smart-pointer spelling without accepting substrings."""
    text = (name or "").strip()
    text = re.sub(r"\b(?:const|volatile)\b", "", text)
    text = text.replace("*", " ").replace("&", " ")
    text = re.sub(r"_var\b", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def _is_status_var(name: str) -> bool:
    return (name or "").lower() in _STATUS_VARS


def _mask_stringish(text: str) -> str:
    """Replace string and char literals so delimiters inside them do not count."""
    return _STRINGISH_RE.sub(lambda m: " " * len(m.group(0)), text or "")


def _count_delim(text: str, delim: str) -> int:
    """Count one delimiter after string/char literals are masked.

    Character equality, not substring count: "}" contains "{" , so
    str.count("{") would treat every close brace as an open brace.
    """
    if not delim:
        return 0
    return sum(1 for ch in _mask_stringish(text) if ch == delim)


def _code_delim_delta(text: str, open_ch: str, close_ch: str) -> int:
    return _count_delim(text, open_ch) - _count_delim(text, close_ch)


def _known_out_arg(method: str, args: str, lookup) -> str:
    """Return the out-parameter only when the call matches the known arity.

    Index 0 means the first argument of a one-argument call, not the first CAT*
    token and not "argument 0 of a longer call". Extra arguments mean the call
    does not match the proven signature, so no output edge is invented.
    """
    tokens = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', args or "")
    for meth, index in _KNOWN_CAA_OUT_SIGNATURES:
        if meth != method:
            continue
        if index >= len(tokens) or len(tokens) != index + 1:
            return ""
        tok = tokens[index]
        tok_type, _tok_def = lookup(tok)
        if tok_type.startswith("CAT") and not _is_status_var(tok):
            return tok
        return ""
    return ""


def _step_mentions_type(step: "ChainStep", type_name: str) -> bool:
    """Exact type/symbol hit. Never a substring of a longer identifier."""
    wanted = _normalize_type(type_name)
    if not wanted:
        return False
    if step.kind == "query_interface" and _exact_type(step.target_name, wanted):
        return True
    if _exact_type(_normalize_type(step.caller_type), wanted):
        return True
    if _exact_type(_normalize_type(step.result_type), wanted):
        return True
    if _exact_type(step.target_name, wanted):
        return True
    return False


def _strip_cpp_comments(text: str) -> List[str]:
    """Strip comments without treating comment markers inside string literals.

    Supported subset: ordinary string/char literals, // and /* */ comments.
    Raw strings, macros that hide braces, and templates are out of scope and
    must be flagged by the caller instead of treated as proven control flow.
    """
    lines: List[str] = []
    in_block = False
    in_string = False
    string_quote = ""
    escape = False
    for line in text.splitlines():
        out = []
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            nxt = line[i + 1] if i + 1 < n else ""
            if in_block:
                if ch == "*" and nxt == "/":
                    in_block = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                out.append(ch)
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == string_quote:
                    in_string = False
                i += 1
                continue
            if ch in ("\"", "'"):
                in_string = True
                string_quote = ch
                out.append(ch)
                i += 1
                continue
            if ch == "/" and nxt == "/":
                break
            if ch == "/" and nxt == "*":
                in_block = True
                i += 2
                continue
            out.append(ch)
            i += 1
        lines.append("".join(out))
    return lines


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
        function_scope: str = "",
        in_error_branch: bool = False,
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
        self.function_scope = function_scope
        self.in_error_branch = in_error_branch
        self.verified_owner: Optional[str] = None
        self.candidate_owners: List[str] = []
        self.owner_ambiguity: bool = False
        # method ownership only: verified | ambiguous | unindexed | not_applicable
        self.ownership_status: str = "unindexed"
        # query_interface facts are separate and never collapsed into ownership_status
        self.qi_convention: str = ""  # "IUnknown" when the call shape is QueryInterface
        self.header_index_status: str = "not_applicable"  # hit | miss | not_applicable
        self.call_success_status: str = "not_observed"  # not_observed | succeeded_check | failed_check | unknown
        self.header: Optional[str] = None
        self.framework: Optional[str] = None
        self.link_module: Optional[str] = None
        self.caller_def: Optional[DefKey] = None
        self.result_def: Optional[DefKey] = None
        self.lexical_scope: int = 0

    def to_dict(self) -> dict:
        method_name = self.target_name if self.kind == "method_call" else ""
        target_type_name = self.target_name if self.kind == "query_interface" else self.result_type
        return {
            "line": self.line,
            "kind": self.kind,
            "caller_var": self.caller_var,
            "caller_type": self.caller_type,
            "caller": f"{self.caller_var} ({self.caller_type})" if self.caller_type else self.caller_var,
            "caller_def": list(self.caller_def) if self.caller_def else None,
            "method": method_name,
            "target": self.target_name,
            "target_type": target_type_name,
            "result_var": self.result_var,
            "result_type": self.result_type,
            "result": f"{self.result_var} ({self.result_type})" if self.result_type else self.result_var,
            "result_def": list(self.result_def) if self.result_def else None,
            "args": self.args,
            "snippet": self.snippet,
            "function_scope": self.function_scope,
            "lexical_scope": self.lexical_scope,
            "in_error_branch": self.in_error_branch,
            "verified_owner": self.verified_owner,
            "candidate_owners": self.candidate_owners,
            "owner_ambiguity": self.owner_ambiguity,
            "ownership_status": self.ownership_status,
            "qi_convention": self.qi_convention,
            "header_index_status": self.header_index_status,
            "call_success_status": self.call_success_status,
            "header": self.header,
            "framework": self.framework,
            "link_module": self.link_module,
        }


class ChainCandidate:
    """A candidate calling sequence recovered from one official use case."""

    def __init__(
        self,
        usecase: str,
        file: str,
        framework: str,
        start_type: str,
        target_type: str,
        steps: List[ChainStep],
        connectivity_status: str = "connected",  # "connected" | "disconnected" | "single_scope"
        evidence_tier: str = "grounded_candidate_chain",  # "grounded_candidate_chain" | "candidate_fragment"
    ):
        self.usecase = usecase
        self.file = file
        self.framework = framework
        self.start_type = start_type
        self.target_type = target_type
        self.steps = steps
        self.connectivity_status = connectivity_status
        self.evidence_tier = evidence_tier
        self.headers_required: List[str] = []
        self.frameworks_required: List[str] = []
        self.modules_from_header_map: List[str] = []
        self.link_libraries: List[str] = []  # non-authoritative alias of modules_from_header_map
        self.link_libraries_authority: str = "header_map_module_not_link_with"
        self.key_interfaces: List[str] = []
        self.jev_verdict: Optional[dict] = None
        self.source_grounded: bool = True
        self.compiler_verified: bool = False
        self.runtime_verified: bool = False
        self.source_sha256: str = ""
        self.source_mtime: str = ""
        self.source_path: str = ""
        self.index_sha256: str = ""
        self.index_schema: str = ""
        self.index_consistency: str = "unknown"  # consistent | stale | unknown
        self.parse_status: str = "ok"  # ok | unsupported_syntax | unparsed

    def to_dict(self) -> dict:
        verified_count = sum(1 for s in self.steps if s.ownership_status == "verified")
        ambiguous_count = sum(1 for s in self.steps if s.ownership_status == "ambiguous")
        unindexed_count = sum(1 for s in self.steps if s.ownership_status == "unindexed")
        return {
            "usecase": self.usecase,
            "file": self.file,
            "framework": self.framework,
            "start_type": self.start_type,
            "target_type": self.target_type,
            "step_count": len(self.steps),
            "connectivity_status": self.connectivity_status,
            "evidence_tier": self.evidence_tier,
            "source_grounded": self.source_grounded,
            "compiler_verified": self.compiler_verified,
            "runtime_verified": self.runtime_verified,
            "source_sha256": self.source_sha256,
            "source_mtime": self.source_mtime,
            "source_path": self.source_path,
            "headers_required": self.headers_required,
            "frameworks_required": self.frameworks_required,
            "modules_from_header_map": self.modules_from_header_map,
            "link_libraries": self.link_libraries,
            "link_libraries_authority": self.link_libraries_authority,
            "link_libraries_note": (
                "link_libraries is a non-authoritative alias of modules_from_header_map. "
                "It is not a verified Imakefile.mk LINK_WITH list."
            ),
            "index_sha256": self.index_sha256,
            "index_schema": self.index_schema,
            "index_consistency": self.index_consistency,
            "parse_status": self.parse_status,
            "verified_steps_count": verified_count,
            "ambiguous_steps_count": ambiguous_count,
            "unindexed_steps_count": unindexed_count,
            "key_interfaces": self.key_interfaces,
            "steps": [s.to_dict() for s in self.steps],
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
            except Exception as e:
                logger.debug("CAADoc auto-detection failed: %s", e)
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

    def _preprocess_cpp_statements(self, text: str) -> List[Tuple[int, str]]:
        """Preprocesses C++ source into a stream of logical statements with line numbers.

        Comment markers inside ordinary string/char literals are preserved.
        Templates, raw strings, goto, and macros that hide braces are out of
        scope; the caller must downgrade evidence instead of treating them as
        proven flow. Brace and parenthesis depth ignore string/char literals.
        """
        cleaned_lines = _strip_cpp_comments(text)

        statements: List[Tuple[int, str]] = []
        buf: List[str] = []
        start_line = 1
        paren_depth = 0

        for idx, line in enumerate(cleaned_lines):
            line_no = idx + 1
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("#"):
                if buf:
                    statements.append((start_line, " ".join(buf)))
                    buf = []
                    paren_depth = 0
                statements.append((line_no, stripped))
                continue

            if not buf:
                start_line = line_no

            buf.append(stripped)
            paren_depth += _code_delim_delta(stripped, "(", ")")

            if paren_depth <= 0 and (
                stripped.endswith(";") or stripped.endswith("{") or stripped.endswith("}")
            ):
                statements.append((start_line, " ".join(buf)))
                buf = []
                paren_depth = 0

        if buf:
            statements.append((start_line, " ".join(buf)))

        return statements

    def _index_fingerprint(self) -> Tuple[str, str]:
        """Fingerprint the loaded use-case index payload, not just its path."""
        try:
            payload = self.retrieval.usecase_index or {}
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            return hashlib.sha256(raw).hexdigest(), str(meta.get("schema", ""))
        except Exception:
            return "", ""

    def _bind_source(self, cpp_path: Path) -> Tuple[str, str, str]:
        """Read source once and hash those exact bytes."""
        data = cpp_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        text = data.decode("utf-8", errors="replace")
        mtime = datetime.fromtimestamp(
            cpp_path.stat().st_mtime, timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        return text, digest, mtime

    def extract_chain_from_cpp(
        self,
        cpp_path: Path,
        start_type: str = "",
        target_type: str = "",
        source_text: str = "",
    ) -> Tuple[List[ChainStep], str, str]:
        """Recover sequential call steps with lexical-scoped Def-Use tracking.

        Returns:
            (steps, connectivity_status, parse_status)
            connectivity_status: connected | disconnected | single_scope
            parse_status: ok | unsupported_syntax | unparsed

        Reachability is tracked via DefKey = (function_scope, lexical_scope_id, variable, definition_id).
        A scope stack manages nested blocks and inner-variable shadowing. Exiting a
        block revokes live reachability for variables declared inside it.
        Reassignment to NULL or non-proven objects drops the live definition.
        Out-parameters are recognized only via explicit '&' or a signature-constrained
        CAA out-API (method name plus parameter index). Cross-function parameter and
        return edges are not inferred by this scanner.
        """
        start_type = _normalize_type(start_type)
        target_type = _normalize_type(target_type)
        if not source_text:
            if not cpp_path.exists():
                return [], "disconnected", "unparsed"
            try:
                source_text = cpp_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return [], "disconnected", "unparsed"

        parse_status = "unsupported_syntax" if _UNSUPPORTED_CPP_RE.search(source_text) else "ok"

        statements = self._preprocess_cpp_statements(source_text)

        # Lexical scope stack: list of dicts mapping var -> (normalized_type, def_id, scope_id)
        # Scope 0 is global
        scope_stack: List[Dict[str, Tuple[str, int, int]]] = [{}]
        scope_id_stack: List[int] = [0]
        scope_counter = 0
        def_id_counter = 0

        live_reachable: Set[DefKey] = set()
        all_steps: List[ChainStep] = []
        candidate_chain_steps: List[ChainStep] = []

        cur_function = "global"
        in_error_block = False
        error_block_depth = 0
        brace_depth = 0
        function_brace_depth = 0
        target_reached = False

        def _bump(var: str, type_name: str) -> DefKey:
            nonlocal def_id_counter
            def_id_counter += 1
            cur_scope_id = scope_id_stack[-1]
            norm_type = _normalize_type(type_name)
            scope_stack[-1][var] = (norm_type, def_id_counter, cur_scope_id)
            return (cur_function, cur_scope_id, var, def_id_counter)

        def _lookup(var: str) -> Tuple[str, Optional[DefKey]]:
            if not var:
                return "", None
            for idx in range(len(scope_stack) - 1, -1, -1):
                entry = scope_stack[idx].get(var)
                if entry:
                    t_name, d_id, s_id = entry
                    fn = cur_function if idx > 0 else "global"
                    return t_name, (fn, s_id, var, d_id)
            return "", None

        entered_function = False

        def _leave_function_if_closed(opened_and_still_open: bool) -> None:
            nonlocal cur_function, function_brace_depth
            if opened_and_still_open:
                return
            if cur_function != "global" and brace_depth <= function_brace_depth:
                cur_function = "global"
                function_brace_depth = 0

        def _enter_function(stmt: str, open_braces: int) -> None:
            nonlocal cur_function, function_brace_depth, entered_function
            head = stmt.strip()
            # A control-flow header is not a function. Do not reject a function
            # whose body begins with if/while/for on the same logical statement.
            if re.match(r'(?:if|while|for|switch|catch)\b', head):
                return
            m_fn = re.search(
                r'(?:^|[\s*>])(?P<name>(?:[A-Za-z_][A-Za-z0-9_]*::)?[A-Za-z_][A-Za-z0-9_]*)\s*\(',
                stmt,
            )
            if not m_fn or "{" not in stmt:
                return
            name = m_fn.group("name")
            if name in ("if", "while", "for", "switch", "catch"):
                return
            cur_function = name
            # Threshold is the depth before this statement's braces. The opening
            # statement must not exit immediately; a later close that returns to
            # this depth does. Comparing against the post-open depth with <= exits
            # on entry and drops every body statement back to global.
            function_brace_depth = brace_depth
            entered_function = True

            # Function arguments are registered in the current function-level scope
            params = stmt[m_fn.end():]
            for pm in re.finditer(
                r'\b(?P<type>CAT[A-Za-z0-9_]+)(?:_var\b|\s*\*)\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)',
                params,
            ):
                param_def = _bump(pm.group("var"), pm.group("type"))
                if start_type and _exact_type(_normalize_type(pm.group("type")), start_type):
                    live_reachable.add(param_def)

        for line_no, stmt in statements:
            open_br = _count_delim(stmt, "{")
            close_br = _count_delim(stmt, "}")
            if open_br and close_br and open_br == close_br:
                # Balanced braces inside one statement are not a function boundary.
                # Keep the net delta for scope push/pop below.
                pass

            # Manage lexical scopes per brace
            for _ in range(open_br):
                scope_counter += 1
                scope_stack.append({})
                scope_id_stack.append(scope_counter)

            if open_br and "(" in stmt:
                _enter_function(stmt, open_br)

            if _ERROR_CHECK_RE.search(stmt) and "{" in stmt and open_br > close_br:
                in_error_block = True
                error_block_depth = brace_depth + open_br - close_br
            elif in_error_block and brace_depth + open_br - close_br < error_block_depth:
                in_error_block = False
                error_block_depth = 0

            # Unbraced control-flow bodies are not proven main-path steps.
            is_unbraced_ctrl = bool(_UNBRACED_CTRL_RE.match(stmt) and "{" not in stmt)
            step_in_error = in_error_block or is_unbraced_ctrl

            cur_lexical_scope = scope_id_stack[-1]

            stripped_stmt = stmt.strip()
            if stripped_stmt.startswith("#"):
                if stripped_stmt.startswith("#define") or stripped_stmt.startswith("#undef"):
                    parse_status = "unsupported_syntax"
                # Handle scope closures before continuing
                for _ in range(close_br):
                    if len(scope_stack) > 1:
                        popped_vars = scope_stack.pop()
                        scope_id_stack.pop()
                        for v, (_, d_id, s_id) in popped_vars.items():
                            live_reachable.discard((cur_function, s_id, v, d_id))
                brace_depth += open_br - close_br
                continue

            # Reassignment without declaration: piProduct = NULL; kills live reachability
            m_redef = re.match(
                r'^\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?![A-Za-z_][A-Za-z0-9_]*\s*(?:->|\.))',
                stmt,
            )
            if m_redef and "->" not in stmt.split("=", 1)[0]:
                var_name = m_redef.group("var")
                prev_type, prev_def = _lookup(var_name)
                if prev_type and prev_def:
                    live_reachable.discard(prev_def)
                    # Assigning to NULL/0/status creates a new dead def, not a live start object
                    _bump(var_name, prev_type)

            # Declaration: CATIProduct *piProduct = NULL;
            m_decl = _VAR_DECL_RE.match(stmt)
            if m_decl and "->" not in stmt.split("=", 1)[0]:
                d_type = m_decl.group("type")
                d_var = m_decl.group("var")
                decl_def = _bump(d_var, d_type)
                # Seed live_reachable ONLY when the declaration is reached in temporal sequence
                if start_type and _exact_type(_normalize_type(d_type), start_type):
                    live_reachable.add(decl_def)

            # QueryInterface pattern. Match the original statement so capture spans
            # stay aligned. Literals are stripped only when selecting an out-parameter.
            m_qi = _QI_RE.search(stmt)
            if m_qi:
                caller = m_qi.group("caller")
                itf = _normalize_type(m_qi.group("itf"))
                target = m_qi.group("target")
                c_type, caller_def = _lookup(caller)
                result_def = _bump(target, itf)

                step = ChainStep(
                    line=line_no,
                    kind="query_interface",
                    caller_var=caller,
                    caller_type=c_type,
                    target_name=itf,
                    result_var=target,
                    result_type=itf,
                    snippet=stmt[:160],
                    function_scope=cur_function,
                    in_error_branch=step_in_error,
                )
                step.caller_def = caller_def
                step.result_def = result_def
                step.lexical_scope = cur_lexical_scope
                step.qi_convention = "IUnknown"
                step.call_success_status = "not_observed"
                all_steps.append(step)

                if not step_in_error and caller_def in live_reachable:
                    candidate_chain_steps.append(step)
                    live_reachable.add(result_def)
                    if target_type and _exact_type(itf, target_type):
                        target_reached = True
                        break

                # Handle scope closures for this statement
                for _ in range(close_br):
                    if len(scope_stack) > 1:
                        popped_vars = scope_stack.pop()
                        scope_id_stack.pop()
                        for v, (_, d_id, s_id) in popped_vars.items():
                            live_reachable.discard((cur_function, s_id, v, d_id))
                brace_depth += open_br - close_br
                _leave_function_if_closed(entered_function and open_br > close_br)
                entered_function = False
                continue

            # Method call pattern
            m_call = _CALL_RE.search(stmt)
            if m_call and "QueryInterface" not in stmt:
                caller = m_call.group("caller")
                meth = m_call.group("method")
                args = m_call.group("args") or ""
                ret_var = m_call.group("ret_var") or ""
                decl_type = _normalize_type(m_call.group("decl_type") or "")
                c_type, caller_def = _lookup(caller)

                if meth not in ("AddRef", "Release"):
                    arg_out_var = ""
                    # 1. Explicit address-of (&var) indicates out-pointer
                    m_out = re.search(r'&\s*(?P<out_var>[A-Za-z_][A-Za-z0-9_]*)', args)
                    if m_out:
                        arg_out_var = m_out.group("out_var")
                    else:
                        # 2. Signature-constrained out-API: method + parameter index.
                        # Mask literals first so a string is not an out-parameter.
                        arg_out_var = _known_out_arg(meth, _mask_stringish(args), _lookup)

                    if (not ret_var or _is_status_var(ret_var)) and arg_out_var:
                        res_var = arg_out_var
                        prior_type, _prior_def = _lookup(arg_out_var)
                        res_type = decl_type or prior_type
                    else:
                        res_var = ret_var
                        prior_type, _prior_def = _lookup(ret_var) if ret_var else ("", None)
                        res_type = decl_type or prior_type

                    result_def = None
                    if res_var and res_type and not _is_status_var(res_var):
                        result_def = _bump(res_var, res_type)

                    step = ChainStep(
                        line=line_no,
                        kind="method_call",
                        caller_var=caller,
                        caller_type=c_type,
                        target_name=meth,
                        result_var=res_var if not _is_status_var(res_var) else "",
                        result_type=res_type,
                        args=args,
                        snippet=stmt[:160],
                        function_scope=cur_function,
                        in_error_branch=step_in_error,
                    )
                    step.caller_def = caller_def
                    step.result_def = result_def
                    step.lexical_scope = cur_lexical_scope
                    step.call_success_status = "not_observed"
                    all_steps.append(step)

                    if not step_in_error and caller_def in live_reachable:
                        candidate_chain_steps.append(step)
                        if result_def:
                            live_reachable.add(result_def)
                        if target_type and (
                            _exact_type(res_type, target_type)
                            or (_exact_type(c_type, target_type) and caller_def in live_reachable)
                        ):
                            target_reached = True
                            break

            # Handle scope closures at the end of each statement
            for _ in range(close_br):
                if len(scope_stack) > 1:
                    popped_vars = scope_stack.pop()
                    scope_id_stack.pop()
                    for v, (_, d_id, s_id) in popped_vars.items():
                        live_reachable.discard((cur_function, s_id, v, d_id))
            brace_depth += open_br - close_br
            _leave_function_if_closed(entered_function and open_br > close_br)
            entered_function = False

        valid_steps = [s for s in all_steps if not s.in_error_branch]
        if not valid_steps:
            return [], "disconnected", parse_status

        if parse_status != "ok":
            # Unsupported syntax cannot form a proven connected chain.
            if target_type:
                hits = [s for s in valid_steps if _step_mentions_type(s, target_type)]
                return hits[:8], "disconnected", parse_status
            return [], "disconnected", parse_status

        def _exact_steps(type_name: str) -> List[ChainStep]:
            return [s for s in valid_steps if _step_mentions_type(s, type_name)]

        if not start_type and not target_type:
            return valid_steps[:20], "single_scope", parse_status

        if not start_type and target_type:
            hits = _exact_steps(target_type)
            return (hits or valid_steps[:15]), "single_scope", parse_status

        if start_type and not target_type:
            return (candidate_chain_steps or valid_steps[:15]), "single_scope", parse_status

        # Both start and target specified
        if target_reached and candidate_chain_steps:
            scopes = {s.function_scope for s in candidate_chain_steps}
            if len(scopes) == 1 and "global" not in scopes:
                return candidate_chain_steps, "connected", parse_status
            return candidate_chain_steps, "disconnected", parse_status

        # Prefer the walk that was actually attempted. Returning every valid
        # step from other functions makes a refused splice look like one chain.
        # If the walk produced nothing, keep the start-side steps so a refused
        # out-parameter can still be inspected. Status stays disconnected.
        if candidate_chain_steps:
            return candidate_chain_steps, "disconnected", parse_status
        start_side = [
            s for s in valid_steps
            if s.caller_type == start_type or s.result_type == start_type
        ]
        return start_side[:8], "disconnected", parse_status

    def verify_steps(self, steps: List[ChainStep]) -> Tuple[List[str], List[str], List[str]]:
        """Validates steps against MethodIndex and HeaderMap with caller_type disambiguation.

        Returns:
            Tuple of (headers, frameworks, link_libraries)
        """
        hm = self.retrieval.header_map
        mi = self.retrieval.method_index

        headers: Set[str] = set()
        frameworks: Set[str] = set()
        link_modules: Set[str] = set()

        for step in steps:
            # 1. Verify caller type
            if step.caller_type and step.caller_type != "?":
                info = hm.lookup(step.caller_type)
                if info is not None:
                    module, framework = info
                    step.header = f"{step.caller_type}.h"
                    step.framework = framework
                    step.link_module = module
                    headers.add(step.header)
                    frameworks.add(framework)
                    if module:
                        link_modules.add(module)

            # 2. QueryInterface: convention, header hit, and success are distinct facts.
            if step.kind == "query_interface":
                step.qi_convention = "IUnknown"
                step.ownership_status = "not_applicable"
                step.verified_owner = None
                step.owner_ambiguity = False
                step.call_success_status = step.call_success_status or "not_observed"
                info = hm.lookup(step.target_name)
                if info is not None:
                    module, framework = info
                    target_header = f"{step.target_name}.h"
                    step.header = target_header
                    step.framework = framework
                    step.link_module = module
                    step.header_index_status = "hit"
                    headers.add(target_header)
                    frameworks.add(framework)
                    if module:
                        link_modules.add(module)
                else:
                    step.header_index_status = "miss"

            # 3. Verify method call with caller_type disambiguation
            elif step.kind == "method_call":
                owners = mi.owners_of(step.target_name)
                if not owners:
                    step.verified_owner = None
                    step.owner_ambiguity = False
                    step.ownership_status = "unindexed"
                    continue

                step.candidate_owners = owners

                # Disambiguation strategy:
                # 3a. Exact match with caller_type
                if step.caller_type in owners:
                    step.verified_owner = step.caller_type
                    step.owner_ambiguity = False
                    step.ownership_status = "verified"
                else:
                    # 3b. Check inheritance: does caller_type inherit from one of the owners?
                    matched_ancestor = None
                    if step.caller_type:
                        try:
                            ancestors = mi.ancestors_of(step.caller_type)
                            for o in owners:
                                if o in ancestors:
                                    matched_ancestor = o
                                    break
                        except Exception:
                            pass

                    if matched_ancestor:
                        step.verified_owner = matched_ancestor
                        step.owner_ambiguity = False
                        step.ownership_status = "verified"
                    elif len(owners) == 1:
                        # Single owner in index: verified only if caller_type matches owner
                        if step.caller_type and _exact_type(step.caller_type, owners[0]):
                            step.verified_owner = owners[0]
                            step.owner_ambiguity = False
                            step.ownership_status = "verified"
                        else:
                            step.verified_owner = owners[0]
                            step.owner_ambiguity = False
                            step.ownership_status = "single_candidate_unverified_caller"
                    else:
                        # Ambiguous: multiple owners exist and caller_type does not resolve it
                        step.verified_owner = None
                        step.owner_ambiguity = True
                        step.ownership_status = "ambiguous"

                # Lookup header & framework for verified owner (or first candidate if unambiguous)
                owner_for_lookup = step.verified_owner or (owners[0] if not step.owner_ambiguity else None)
                if owner_for_lookup:
                    owner_info = hm.lookup(owner_for_lookup)
                    if owner_info is not None:
                        module, framework = owner_info
                        owner_hdr = f"{owner_for_lookup}.h"
                        headers.add(owner_hdr)
                        frameworks.add(framework)
                        if module:
                            link_modules.add(module)

        return sorted(headers), sorted(frameworks), sorted(link_modules)

    def explore(
        self,
        start: str = "",
        target: str = "",
        query: str = "",
        max_candidates: int = 3,
    ) -> dict:
        """End-to-end exploration of official call chains for a development requirement.

        Guarantees:
        - If grounded source evidence is recovered, returns status="ok" with static-checked steps.
        - If evidence is missing, returns status="insufficient_evidence" with gaps.
        - Incorporates Jev System One semantic review when enabled.
        - NEVER claims compiler or runtime verification.
        """
        # Direction is inferred only from an explicit relation. Identifier order is not a direction.
        if query and (not start or not target):
            directed = _directed_types(query)
            if directed:
                if not start:
                    start = directed[0]
                if not target:
                    target = directed[1]
            elif not target:
                ids = self.extract_identifiers(query)
                if len(ids) == 1:
                    target = ids[0]

        # Step 1: Candidate Discovery
        candidate_ucs = self.find_candidate_usecases(
            start=start, target=target, query=query, limit=10
        )

        # If a specific target is specified, candidate use cases MUST mention the target.
        # File name substring is only used for ranking/sorting, NEVER as target presence fact.
        if target:
            candidate_ucs = [
                uc for uc in candidate_ucs
                if target in uc.get("interfaces", [])
                or target in uc.get("symbols", [])
                or target in uc.get("methods", [])
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

        root_resolved = root.resolve()
        recovered_candidates: List[ChainCandidate] = []
        scan_limit = max(len(candidate_ucs), max_candidates)

        for uc in candidate_ucs[:scan_limit]:
            rel_file = uc.get("file", "")
            if not rel_file:
                continue

            full_path = (root / rel_file).resolve()
            # Path traversal security check using strict path parts
            if not _is_safe_subpath(full_path, root_resolved):
                logger.warning("Blocked path traversal attempt outside CAADoc: %s", full_path)
                continue

            if not full_path.exists():
                continue

            try:
                source_text, source_sha, source_mtime = self._bind_source(full_path)
            except OSError:
                continue
            steps, connectivity, parse_status = self.extract_chain_from_cpp(
                full_path,
                start_type=start,
                target_type=target,
                source_text=source_text,
            )
            if not steps:
                continue

            # Exact type/symbol only. A longer name that merely contains the
            # target string is not a hit.
            if target and not any(_step_mentions_type(s, target) for s in steps):
                continue

            if start and target and connectivity != "connected":
                if not any(_step_mentions_type(s, target) for s in steps):
                    continue

            # Verify with authoritative indexes
            headers, frameworks, link_modules = self.verify_steps(steps)

            parts = Path(rel_file).parts
            fw = parts[0] if parts else ""

            unresolved = any(s.ownership_status == "ambiguous" for s in steps)
            if connectivity == "connected" and parse_status == "ok" and not unresolved:
                evidence_tier = "grounded_candidate_chain"
            else:
                evidence_tier = "candidate_fragment"
                if connectivity == "connected":
                    connectivity = "disconnected"

            cand = ChainCandidate(
                usecase=uc.get("name", ""),
                file=rel_file,
                framework=fw,
                start_type=start,
                target_type=target,
                steps=steps,
                connectivity_status=connectivity,
                evidence_tier=evidence_tier,
            )
            cand.headers_required = headers
            cand.frameworks_required = frameworks
            cand.modules_from_header_map = link_modules
            cand.link_libraries = list(link_modules)
            cand.link_libraries_authority = "header_map_module_not_link_with"
            cand.parse_status = parse_status
            cand.source_sha256 = source_sha
            cand.source_mtime = source_mtime
            cand.source_path = str(full_path)
            index_sha, index_schema = self._index_fingerprint()
            cand.index_sha256 = index_sha
            cand.index_schema = index_schema
            meta = self.retrieval.usecase_index.get("meta", {}) if self.retrieval.usecase_index else {}
            indexed_root = str(meta.get("caadoc_root", ""))
            cand.index_consistency = (
                "root_matched_metadata_unverified"
                if indexed_root and Path(indexed_root).resolve() == root_resolved and index_sha
                else "unknown"
            )

            # Collect key interfaces for Jev and downstream inspection
            key_ifaces: List[str] = []
            for s in steps:
                for candidate_name in (s.caller_type, s.result_type, s.target_name):
                    if candidate_name and candidate_name.startswith("CAT") and candidate_name not in key_ifaces:
                        key_ifaces.append(candidate_name)
            cand.key_interfaces = key_ifaces

            # Optional: Jev Semantic Review
            try:
                from jev_judge import judge_chain_relevance
                verdict = judge_chain_relevance(query or f"{start} to {target}", cand.to_dict())
                if verdict:
                    cand.jev_verdict = verdict
            except Exception as e:
                logger.debug("Jev review skipped: %s", e)

            recovered_candidates.append(cand)
            connected_count = sum(
                1 for c in recovered_candidates
                if c.connectivity_status == "connected" and c.parse_status == "ok"
            )
            if connected_count >= max_candidates:
                break

        recovered_candidates.sort(
            key=lambda c: (
                0 if c.connectivity_status == "connected" and c.parse_status == "ok" else 1,
                0 if c.evidence_tier == "grounded_candidate_chain" else 1,
                0 if c.parse_status == "ok" else 1,
            )
        )
        recovered_candidates = recovered_candidates[:max_candidates]

        if not recovered_candidates:
            return {
                "status": "insufficient_evidence",
                "start": start,
                "target": target,
                "query": query,
                "candidates": [],
                "missing_evidence": [
                    f"Matched use cases ({[c['name'] for c in candidate_ucs[:3]]}) "
                    f"did not yield a continuous grounded call chain between {start} and {target}."
                ],
                "summary": "Presence detected in use cases, but no continuous grounded source flow recovered.",
            }

        best_tier = recovered_candidates[0].evidence_tier if recovered_candidates else "insufficient_evidence"
        tier_label = "grounded candidate calling sequence(s)" if best_tier == "grounded_candidate_chain" else "candidate code fragment(s) (unconnected dataflow)"
        return {
            "status": "ok",
            "start": start,
            "target": target,
            "query": query,
            "candidate_count": len(recovered_candidates),
            "evidence_tier": best_tier,
            "source_grounded": True,
            "compiler_verified": False,
            "runtime_verified": False,
            "candidates": [c.to_dict() for c in recovered_candidates],
            "summary": (
                f"Successfully recovered {len(recovered_candidates)} {tier_label} "
                f"(static-checked, not compiler-verified) from official CAADoc samples for {start or 'query'} -> {target or 'target'}."
            ),
        }

    def crystallize(
        self,
        candidate: dict,
        output_dir: Optional[Path] = None,
        overwrite: bool = False,
    ) -> dict:
        """Crystallizes a recovered call chain into an isolated candidate playbook draft.

        Security Contract:
        - NEVER writes to playbooks/ or updates catalog/index.yaml directly.
        - Files are placed in knowledge/experimental/ with strict candidate headers.
        - Protects against accidental overwrites when overwrite=False.
        """
        if output_dir is None:
            output_dir = self.skill_root / "knowledge" / "experimental"
        output_dir.mkdir(parents=True, exist_ok=True)

        uc_name = candidate.get("usecase", "unnamed_candidate")
        start = candidate.get("start_type", "Start")
        target = candidate.get("target_type", "Target")
        clean_name = re.sub(r'[^A-Za-z0-9_]+', '_', f"{start}_{target}_{uc_name}").strip('_')

        base_file_name = f"CANDIDATE_{clean_name}.md"
        doc_path = output_dir / base_file_name

        if doc_path.exists() and not overwrite:
            # Avoid clobbering existing human edits on candidates
            counter = 2
            while True:
                candidate_path = output_dir / f"CANDIDATE_{clean_name}_v{counter}.md"
                if not candidate_path.exists():
                    doc_path = candidate_path
                    break
                counter += 1

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Generate candidate playbook document
        lines = [
            f"# [EXPERIMENTAL CANDIDATE] {start} -> {target}",
            "",
            "> **SECURITY NOTICE & STATUS**: This is an automatically recovered, unreviewed candidate.",
            "> It is isolated from official knowledge (`catalog/index.yaml`).",
            "> Full runtime compilation and functional testing in CATIA are required before promotion.",
            "",
            "## 1. Source Provenance & Fingerprint",
            f"- **Generated At**: `{now_str}`",
            f"- **Official Use Case**: `{uc_name}`",
            f"- **Source File**: `{candidate.get('file', '')}`",
            f"- **Framework**: `{candidate.get('framework', '')}`",
            f"- **Step Count**: {candidate.get('step_count', 0)} static-checked steps",
            f"- **Connectivity**: `{candidate.get('connectivity_status', 'connected')}`",
            f"- **Evidence Tier**: `{candidate.get('evidence_tier', 'grounded_candidate_chain')}`",
            f"- **Source SHA256**: `{candidate.get('source_sha256', 'unknown')}`",
            f"- **Source MTime**: `{candidate.get('source_mtime', 'unknown')}`",
            f"- **Index SHA256**: `{candidate.get('index_sha256', 'unknown')}`",
            f"- **Index Consistency**: `{candidate.get('index_consistency', 'unknown')}`",
            f"- **Parse Status**: `{candidate.get('parse_status', 'unknown')}`",
            f"- **Verified Steps**: {candidate.get('verified_steps_count', 0)}",
            f"- **Ambiguous Steps**: {candidate.get('ambiguous_steps_count', 0)}",
            f"- **Unindexed Steps**: {candidate.get('unindexed_steps_count', 0)}",
            "",
            "## 2. Prerequisites & Build Dependencies",
            "### Headers Required (`#include`)",
        ]
        for h in candidate.get("headers_required", []):
            lines.append(f"- `#include \"{h}\"`")

        lines.extend([
            "",
            "### Frameworks Required (`IdentityCard.xml`)",
        ])
        for fw in candidate.get("frameworks_required", []):
            lines.append(f"- `<prereq name=\"{fw}\"/>`")

        lines.extend([
            "",
            "### Modules From HeaderMap (not verified LINK_WITH)",
            "> `link_libraries` in the machine payload is a non-authoritative alias of these module names.",
            "> HeaderMap proves which module owns a header. It does not prove the Imakefile.mk `LINK_WITH` list.",
        ])
        link_libs = candidate.get("modules_from_header_map") or candidate.get("link_libraries", [])
        if link_libs:
            for lib in link_libs:
                lines.append(f"- `{lib}`")
        else:
            lines.append("- *(Link modules derived from HeaderMap or workspace inspection)*")

        lines.extend([
            "",
            "## 3. Grounded Calling Sequence (Static Source Slice)",
            "```cpp",
        ])
        for s in candidate.get("steps", []):
            line_no = s.get("line", 0)
            snip = s.get("snippet", "")
            owner = s.get("verified_owner", "")
            amb = s.get("owner_ambiguity", False)
            if amb:
                cands = ",".join(s.get("candidate_owners", []))
                owner_comment = f" // [Owner ambiguous: {cands}]"
            elif owner:
                owner_comment = f" // [Owner: {owner}]"
            else:
                owner_comment = ""
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
            "evidence_tier": candidate.get("evidence_tier", "grounded_candidate_chain"),
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
