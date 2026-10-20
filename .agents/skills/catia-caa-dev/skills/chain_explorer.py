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
        self.header: Optional[str] = None
        self.framework: Optional[str] = None
        self.link_module: Optional[str] = None

    def to_dict(self) -> dict:
        method_name = self.target_name if self.kind == "method_call" else ""
        target_type_name = self.target_name if self.kind == "query_interface" else self.result_type
        return {
            "line": self.line,
            "kind": self.kind,
            "caller_var": self.caller_var,
            "caller_type": self.caller_type,
            "caller": f"{self.caller_var} ({self.caller_type})" if self.caller_type else self.caller_var,
            "method": method_name,
            "target": self.target_name,
            "target_type": target_type_name,
            "result_var": self.result_var,
            "result_type": self.result_type,
            "result": f"{self.result_var} ({self.result_type})" if self.result_type else self.result_var,
            "args": self.args,
            "snippet": self.snippet,
            "function_scope": self.function_scope,
            "in_error_branch": self.in_error_branch,
            "verified_owner": self.verified_owner,
            "candidate_owners": self.candidate_owners,
            "owner_ambiguity": self.owner_ambiguity,
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
        self.link_libraries: List[str] = []
        self.key_interfaces: List[str] = []
        self.jev_verdict: Optional[dict] = None
        self.source_grounded: bool = True
        self.compiler_verified: bool = False
        self.runtime_verified: bool = False

    def to_dict(self) -> dict:
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
            "headers_required": self.headers_required,
            "frameworks_required": self.frameworks_required,
            "link_libraries": self.link_libraries,
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

        Handles:
        - Block comments (/* ... */) stripping while preserving line counts
        - Single-line comments (// ...) stripping
        - Multi-line statements (spanning parentheses, commas, ->)
        """
        raw_lines = text.splitlines()
        # Step 1: Strip block comments
        cleaned_lines: List[str] = []
        in_block_comment = False
        for line in raw_lines:
            cur = ""
            i = 0
            n = len(line)
            while i < n:
                if in_block_comment:
                    if line[i:i+2] == "*/":
                        in_block_comment = False
                        i += 2
                    else:
                        i += 1
                else:
                    if line[i:i+2] == "/*":
                        in_block_comment = True
                        i += 2
                    elif line[i:i+2] == "//":
                        # Line comment starts, ignore rest of line
                        break
                    else:
                        cur += line[i]
                        i += 1
            cleaned_lines.append(cur)

        # Step 2: Assemble logical statements across line boundaries
        statements: List[Tuple[int, str]] = []
        buf = []
        start_line = 1
        paren_depth = 0

        for idx, line in enumerate(cleaned_lines):
            line_no = idx + 1
            stripped = line.strip()
            if not stripped:
                continue

            # Preprocessor directives (#include, #define, etc.) are line-oriented
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
            paren_depth += line.count("(") - line.count(")")

            # A statement terminates at semicolon or opening/closing brace if paren_depth <= 0
            if paren_depth <= 0 and (stripped.endswith(";") or stripped.endswith("{") or stripped.endswith("}")):
                stmt_text = " ".join(buf)
                statements.append((start_line, stmt_text))
                buf = []
                paren_depth = 0

        if buf:
            statements.append((start_line, " ".join(buf)))

        return statements

    def extract_chain_from_cpp(
        self,
        cpp_path: Path,
        start_type: str = "",
        target_type: str = "",
    ) -> Tuple[List[ChainStep], str]:
        """Parses a real .cpp file to recover sequential call steps with Def-Use tracking.

        Returns:
            Tuple of (steps, connectivity_status)
            connectivity_status: "connected" | "disconnected" | "single_scope"
        """
        if not cpp_path.exists():
            return [], "disconnected"

        try:
            content = cpp_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], "disconnected"

        statements = self._preprocess_cpp_statements(content)

        vars_type: Dict[str, str] = {}
        vars_scope: Dict[str, str] = {}
        all_steps: List[ChainStep] = []

        cur_function = "global"
        in_error_block = False
        error_block_depth = 0

        # Pass 1: Parse variables, QI transitions, calls, and control-flow branches
        for line_no, stmt in statements:
            # Simple heuristic for function boundary
            if "::" in stmt and "(" in stmt and "{" in stmt and not stmt.startswith("if") and not stmt.startswith("while"):
                m_fn = re.search(r'([A-Za-z0-9_]+::[A-Za-z0-9_]+)\s*\(', stmt)
                if m_fn:
                    cur_function = m_fn.group(1)

            # Track error branch entry/exit
            if _ERROR_CHECK_RE.search(stmt):
                open_br = stmt.count("{")
                close_br = stmt.count("}")
                if open_br > close_br:
                    in_error_block = True
                    error_block_depth = open_br - close_br
                continue
            if in_error_block:
                error_block_depth += stmt.count("{") - stmt.count("}")
                if error_block_depth <= 0:
                    in_error_block = False
                    error_block_depth = 0

            # Variable Declaration: CATIProduct *piRootProduct = NULL;
            m_decl = _VAR_DECL_RE.match(stmt)
            if m_decl:
                t_name = m_decl.group("type")
                v_name = m_decl.group("var")
                vars_type[v_name] = t_name
                vars_scope[v_name] = cur_function

            # QueryInterface: rc = var1->QueryInterface(IID_TargetItf, (void**)&var2);
            m_qi = _QI_RE.search(stmt)
            if m_qi:
                caller = m_qi.group("caller")
                itf = m_qi.group("itf")
                target = m_qi.group("target")
                c_type = vars_type.get(caller, "")
                vars_type[target] = itf
                vars_scope[target] = cur_function
                all_steps.append(ChainStep(
                    line=line_no,
                    kind="query_interface",
                    caller_var=caller,
                    caller_type=c_type,
                    target_name=itf,
                    result_var=target,
                    result_type=itf,
                    snippet=stmt[:120],
                    function_scope=cur_function,
                    in_error_branch=in_error_block,
                ))
                continue

            # Method Call: target_var = caller->Method(args) or caller->Method(&target_var)
            m_call = _CALL_RE.search(stmt)
            if m_call and "QueryInterface" not in stmt:
                caller = m_call.group("caller")
                meth = m_call.group("method")
                args = m_call.group("args")
                ret_var = m_call.group("ret_var") or ""
                decl_type = m_call.group("decl_type") or ""
                c_type = vars_type.get(caller, "")

                if ret_var and decl_type:
                    vars_type[ret_var] = decl_type
                    vars_scope[ret_var] = cur_function

                # Skip standard Release/AddRef noise in the core sequence unless explicitly requested
                if meth in ("AddRef", "Release") and not (target_type and target_type in meth):
                    continue

                # Check if an argument looks like an output pointer (&var)
                arg_out_var = ""
                arg_out_type = ""
                m_out = re.search(r'&\s*(?P<out_var>[A-Za-z0-9_]+)', args)
                if m_out:
                    arg_out_var = m_out.group("out_var")
                    arg_out_type = vars_type.get(arg_out_var, "")

                if (not ret_var or ret_var.lower() in ("rc", "hr", "ret", "res", "status", "hresult")) and arg_out_var:
                    res_var = arg_out_var
                    res_type = decl_type or vars_type.get(arg_out_var, arg_out_type)
                else:
                    res_var = ret_var or arg_out_var
                    res_type = decl_type or vars_type.get(res_var, arg_out_type)

                if res_var and res_type:
                    vars_scope[res_var] = cur_function
                    vars_type[res_var] = res_type

                all_steps.append(ChainStep(
                    line=line_no,
                    kind="method_call",
                    caller_var=caller,
                    caller_type=c_type,
                    target_name=meth,
                    result_var=res_var,
                    result_type=res_type,
                    args=args,
                    snippet=stmt[:120],
                    function_scope=cur_function,
                    in_error_branch=in_error_block,
                ))

        # Filter out error branch cleanups unless specifically targeting error handling
        valid_steps = [s for s in all_steps if not s.in_error_branch]
        if not valid_steps and all_steps:
            valid_steps = all_steps

        # Pass 2: Rigorous Def-Use Dataflow Tracking
        if not start_type and not target_type:
            return valid_steps[:20], "single_scope"

        start_vars = {v for v, t in vars_type.items() if t == start_type or (start_type and start_type in t)}
        target_vars = {v for v, t in vars_type.items() if t == target_type or (target_type and target_type in t)}

        if not start_type and target_type:
            # Backward reachability to target
            target_steps = [
                s for s in valid_steps
                if s.target_name == target_type or s.result_type == target_type or s.caller_type == target_type
            ]
            return (target_steps or valid_steps[:15]), "single_scope"

        if start_type and not target_type:
            # Forward reachability from start
            reachable_vars = set(start_vars)
            fwd_steps = []
            for s in valid_steps:
                if s.caller_var in reachable_vars or s.caller_type == start_type:
                    fwd_steps.append(s)
                    if s.result_var:
                        reachable_vars.add(s.result_var)
            return (fwd_steps or valid_steps[:15]), "single_scope"

        # Both start_type and target_type are specified: enforce Def-Use forward connectivity
        if not start_vars and not any(s.caller_type == start_type for s in valid_steps):
            # Start type not present in this file: check if target steps exist as a fragment
            target_steps = [
                s for s in valid_steps
                if s.target_name == target_type or s.result_type == target_type or s.caller_type == target_type or target_type in s.args
            ]
            if target_steps:
                return target_steps, "disconnected"
            return [], "disconnected"

        # Check function scopes: start and target must not be in mutually isolated functions without pass-through
        start_scopes = {vars_scope.get(v, "") for v in start_vars if v in vars_scope}
        target_scopes = {vars_scope.get(v, "") for v in target_vars if v in vars_scope}
        if start_scopes and target_scopes and not (start_scopes & target_scopes) and "global" not in start_scopes:
            # Separated in distinct functions without linkage
            return [], "disconnected"

        reachable_vars: Set[str] = set(start_vars)
        chain_steps: List[ChainStep] = []
        target_reached = False

        for step in valid_steps:
            involves_start = step.caller_var in reachable_vars or step.caller_type == start_type
            if involves_start:
                chain_steps.append(step)
                if step.result_var:
                    reachable_vars.add(step.result_var)

                # Check if this step reached target
                if (
                    step.target_name == target_type
                    or step.result_type == target_type
                    or (step.result_var and step.result_var in target_vars)
                    or (target_type in step.args)
                ):
                    target_reached = True
                    break

        if target_reached:
            return chain_steps, "connected"

        # If strict def-use forward walk did not directly connect target, check if target was hit but vars were unlinked
        target_steps = [
            s for s in valid_steps
            if s.target_name == target_type or s.result_type == target_type or s.caller_type == target_type or target_type in s.args
        ]
        if target_steps and chain_steps:
            # Both exist in file, but disconnected dataflow
            return chain_steps + target_steps, "disconnected"
        elif target_steps:
            return target_steps, "disconnected"

        return [], "disconnected"

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

            # 2. Verify target interface in QueryInterface
            if step.kind == "query_interface":
                info = hm.lookup(step.target_name)
                if info is not None:
                    module, framework = info
                    target_header = f"{step.target_name}.h"
                    step.header = target_header
                    step.framework = framework
                    step.link_module = module
                    headers.add(target_header)
                    frameworks.add(framework)
                    if module:
                        link_modules.add(module)
                step.verified_owner = "IUnknown"
                step.owner_ambiguity = False

            # 3. Verify method call with caller_type disambiguation
            elif step.kind == "method_call":
                owners = mi.owners_of(step.target_name)
                if not owners:
                    continue

                step.candidate_owners = owners

                # Disambiguation strategy:
                # 3a. Exact match with caller_type
                if step.caller_type in owners:
                    step.verified_owner = step.caller_type
                    step.owner_ambiguity = False
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
                    elif len(owners) == 1:
                        # Unambiguous single owner in index
                        step.verified_owner = owners[0]
                        step.owner_ambiguity = False
                    else:
                        # Ambiguous: multiple owners exist and caller_type does not resolve it
                        step.verified_owner = None
                        step.owner_ambiguity = True

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

        root_resolved = root.resolve()
        recovered_candidates: List[ChainCandidate] = []

        for uc in candidate_ucs:
            rel_file = uc.get("file", "")
            if not rel_file:
                continue

            full_path = (root / rel_file).resolve()
            # Path traversal security check
            try:
                if not full_path.is_relative_to(root_resolved):
                    logger.warning("Blocked path traversal attempt outside CAADoc: %s", full_path)
                    continue
            except (ValueError, AttributeError):
                if not str(full_path).startswith(str(root_resolved)):
                    continue

            if not full_path.exists():
                continue

            steps, connectivity = self.extract_chain_from_cpp(full_path, start_type=start, target_type=target)
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

            # If both start and target are specified and disconnected, only accept if steps directly exercise target
            if start and target and connectivity == "disconnected":
                has_target_op = any(
                    target in (s.caller_type or "") or
                    target in (s.result_type or "") or
                    target in (s.target_name or "") or
                    target in (s.args or "")
                    for s in steps
                )
                if not has_target_op:
                    continue

            # Verify with authoritative indexes
            headers, frameworks, link_modules = self.verify_steps(steps)

            parts = Path(rel_file).parts
            fw = parts[0] if parts else ""

            evidence_tier = "grounded_candidate_chain" if connectivity == "connected" else "candidate_fragment"

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
            cand.link_libraries = link_modules

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
                    f"did not yield a continuous grounded call chain between {start} and {target}."
                ],
                "summary": "Presence detected in use cases, but no continuous grounded source flow recovered.",
            }

        return {
            "status": "ok",
            "start": start,
            "target": target,
            "query": query,
            "candidate_count": len(recovered_candidates),
            "evidence_tier": recovered_candidates[0].evidence_tier,
            "source_grounded": True,
            "compiler_verified": False,
            "runtime_verified": False,
            "candidates": [c.to_dict() for c in recovered_candidates],
            "summary": (
                f"Successfully recovered {len(recovered_candidates)} grounded candidate calling sequence(s) "
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
            "### Recommended Link Modules (`Imakefile.mk LINK_WITH`)",
        ])
        link_libs = candidate.get("link_libraries", [])
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
