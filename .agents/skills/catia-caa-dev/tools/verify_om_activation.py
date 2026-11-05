#!/usr/bin/env python3
"""
Object Modeler DataExtension Trigger & Runtime Evidence Verification Driver
=============================================================================
Unified Driver for P0-2 Verification:
- Line B: Official Use Case AST & DICO Parser (Real CAAMmrMeasureSet verification)
- Line C: B28 System Dictionary Recursive Conflict Scanner & Priority Analysis
- Line D: End-to-End L0~L5 Layered Evidence Capture with 4-Factor Probe Contract
          (Exact DLL path matching, Nonce/PID/Component/Freshness probe verification)
"""

import os
import sys
import re
import glob
import json
import math
import uuid
import time
import argparse
import pathlib
import threading
from typing import Dict, Any, List, Optional, Tuple

SKILL_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from env import CAAEnvironment
from runtime_view import check_runtime_view_l0, check_runtime_view_l1, _verify_pe_file, _verify_dico_syntax
from run import (
    identify_target_cnext,
    verify_module_loaded,
    get_processes_snapshot_win32,
    get_process_loaded_modules,
    run_catia_macro,
)


def _to_short_path(path_str: str) -> str:
    """Convert path to 8.3 short path on Windows to avoid mkrun argument truncation."""
    if sys.platform != "win32" or not path_str:
        return str(path_str)
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        res = ctypes.windll.kernel32.GetShortPathNameW(str(path_str), buf, len(buf))
        if res and res < len(buf):
            return buf.value
    except Exception:
        pass
    return str(path_str)


class OMActivationDriver:
    """
    Unified Verification Driver for Object Modeler DataExtension activation.
    Covers Preflight, Recursive Conflict Analysis, Official AST Parsing, and 4-Factor Probe Contract.
    """

    DEFAULT_B28_ROOT = r"C:\Program Files\Dassault Systemes\B28"
    DEFAULT_COMPONENT = "CAAMmrMeasureSet"
    DEFAULT_INTERFACE = "CATI3DGeoVisu"
    DEFAULT_MODULE = "AcceptanceMod"
    DEFAULT_FRAMEWORK = "AcceptanceFw"

    def __init__(
        self,
        b28_root: Optional[str] = None,
        workspace_path: Optional[str] = None,
        target_component: str = DEFAULT_COMPONENT,
        target_interface: str = DEFAULT_INTERFACE,
        target_module: str = DEFAULT_MODULE,
        target_framework: str = DEFAULT_FRAMEWORK,
    ):
        self.b28_root = pathlib.Path(b28_root or self._detect_b28_root())
        self.workspace_path = pathlib.Path(workspace_path) if workspace_path else None
        self.target_component = target_component
        self.target_interface = target_interface
        self.target_module = target_module
        self.target_framework = target_framework

    def _detect_b28_root(self) -> str:
        caa_env = CAAEnvironment()
        try:
            caa_env.load_config()
            inst = caa_env.get_catia_install_path()
            if inst and os.path.isdir(inst):
                return inst
        except Exception:
            pass
        return self.DEFAULT_B28_ROOT

    # ── Line C: System Dictionary Recursive Conflict & Priority Analysis ─
    def check_system_dictionary_conflict(self) -> Dict[str, Any]:
        """
        Recursively scan all B28 system dictionaries under win_b64/code/dictionary.
        Tracks unreadable files and unreadable directories via onerror callback.
        Avoids unverified priority claims.
        """
        dico_dir = self.b28_root / "win_b64" / "code" / "dictionary"
        matches = []
        unreadable_files = []
        unreadable_directories = []
        total_discovered = 0
        scanned_success = 0

        def on_walk_error(err: OSError):
            unreadable_directories.append({
                "path": str(getattr(err, "filename", err)),
                "error": str(err),
            })

        if dico_dir.is_dir():
            for root, _, files in os.walk(dico_dir, onerror=on_walk_error):
                for f in files:
                    if f.endswith(".dico") or f.endswith(".dic"):
                        total_discovered += 1
                        file_path = os.path.join(root, f)
                        try:
                            with open(file_path, "r", encoding="latin-1", errors="strict") as fp:
                                for line_no, raw_line in enumerate(fp, start=1):
                                    line = raw_line.strip()
                                    if not line or line.startswith("#"):
                                        continue
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[0] == self.target_component:
                                        matches.append({
                                            "file": os.path.relpath(file_path, dico_dir),
                                            "line": line_no,
                                            "entry": line,
                                            "component": parts[0],
                                            "interface": parts[1],
                                            "library": parts[2] if len(parts) >= 3 else "",
                                        })
                            scanned_success += 1
                        except Exception as e:
                            unreadable_files.append({
                                "file": os.path.relpath(file_path, dico_dir),
                                "error": str(e),
                            })

        interface_matches = [m for m in matches if m.get("interface") == self.target_interface]
        has_conflict = len(interface_matches) > 0
        read_complete = (
            total_discovered > 0
            and len(unreadable_files) == 0
            and len(unreadable_directories) == 0
        )

        analysis = {
            "recursive_scan_enabled": True,
            "total_dictionaries_discovered": total_discovered,
            "scanned_dictionaries_success": scanned_success,
            "unreadable_files_count": len(unreadable_files),
            "unreadable_files": unreadable_files,
            "unreadable_directories_count": len(unreadable_directories),
            "unreadable_directories": unreadable_directories,
            "scan_completeness_rate": round(scanned_success / total_discovered, 4) if (total_discovered and len(unreadable_directories) == 0) else 0.0,
            "target_component": self.target_component,
            "target_interface": self.target_interface,
            "total_component_registrations": len(matches),
            "exact_interface_conflicts": len(interface_matches),
            "conflict_entries": interface_matches,
            "has_system_conflict": has_conflict,
            # Only declare exclusive when both directory walk and file reads completed with zero errors
            "exclusive_mapping_in_scanned_dictionaries": (not has_conflict) if read_complete else False,
            "precedence_status": "UNTESTED_HYPOTHESIS",
            "precedence_note": (
                "CAA V5 documentation states CATDictionaryPath is evaluated from left to right. "
                "However, until a real two-way override experiment is performed with identical tokens in distinct dirs, "
                "search precedence remains an UNTESTED_HYPOTHESIS rather than proven runtime behavior."
            ),
        }
        return analysis

    # ── Line B: Official Use Case AST & DICO Parser ───────────────────────
    @classmethod
    def verify_blueprint_contract(
        cls,
        parsed_cpp: Dict[str, Any],
        parsed_dico: Dict[str, Any],
        target_component: str = "CAAMmrMeasureSet",
        target_interface: str = "CATI3DGeoVisu",
        expected_base_class: str = "CATExtIVisu",
    ) -> bool:
        """
        Pure verification function enforcing genuine CAA Object Modeler contract:
        1. C++ AST was successfully parsed;
        2. extension_type is strictly 'DataExtension';
        3. target_late_type matches target_component;
        4. tie_interface matches target_interface;
        5. base_class matches expected_base_class;
        6. DICO contains at least one matching entry mapping (component, interface).
        """
        if not parsed_cpp.get("parsed", False):
            return False
        if parsed_cpp.get("extension_type") != "DataExtension":
            return False
        if parsed_cpp.get("target_late_type") != target_component:
            return False
        if parsed_cpp.get("tie_interface") != target_interface:
            return False
        if parsed_cpp.get("base_class") != expected_base_class:
            return False
        dico_entry_match = False
        for entry in parsed_dico.get("matching_entries", []):
            if isinstance(entry, dict):
                comp = entry.get("component")
                iface = entry.get("interface")
                if comp == target_component and iface == target_interface:
                    dico_entry_match = True
                    break
        return bool(dico_entry_match)

    def inspect_official_usecase(
        self,
        cpp_path_override: Optional[pathlib.Path] = None,
        dico_path_override: Optional[pathlib.Path] = None,
    ) -> Dict[str, Any]:
        """
        Verify the existence and parse genuine Dassault official CAAMechanicalModeler.edu assets:
        - CAAMmrMultiMeasureAndMeasureSet.CATPart (real model containing CAAMmrMeasureSet)
        - CAAEMmrMeasureSetVisu.cpp (parsed via regex for CATImplementClass and TIE_)
        - CAAMechanicalModeler.edu.dico (parsed for exact matching entries)
        """
        edu_dir = self.b28_root / "CAADoc" / "CAAMechanicalModeler.edu"
        catpart = edu_dir / "InputData" / "CAAMmrMultiMeasureAndMeasureSet.CATPart"
        cpp_src = cpp_path_override or (edu_dir / "CAAMmrMultiMeasureAndMeasureSet.m" / "src" / "CAAEMmrMeasureSetVisu.cpp")
        dico_src = dico_path_override or (edu_dir / "CAAMechanicalModelerEduRscCNext.m" / "src" / "CNext" / "code" / "dictionary" / "CAAMechanicalModeler.edu.dico")

        parsed_cpp = {
            "parsed": False,
            "extension_class": None,
            "extension_type": None,
            "base_class": None,
            "target_late_type": None,
            "tie_interface": None,
        }

        if cpp_src.is_file():
            try:
                cpp_text = cpp_src.read_text(encoding="utf-8", errors="ignore")
                tie_m = re.search(r"TIE_(\w+)\s*\(\s*(\w+)\s*\)", cpp_text)
                impl_m = re.search(
                    r"CATImplementClass\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)",
                    cpp_text,
                )
                if tie_m:
                    parsed_cpp["tie_interface"] = tie_m.group(1)
                if impl_m:
                    parsed_cpp["extension_class"] = impl_m.group(1)
                    parsed_cpp["extension_type"] = impl_m.group(2)
                    parsed_cpp["base_class"] = impl_m.group(3)
                    parsed_cpp["target_late_type"] = impl_m.group(4)
                parsed_cpp["parsed"] = bool(tie_m and impl_m)
            except Exception as e:
                parsed_cpp["parse_error"] = str(e)

        parsed_dico = {
            "parsed": False,
            "matching_entries": [],
        }

        if dico_src.is_file():
            try:
                for line in dico_src.read_text(encoding="latin-1", errors="ignore").splitlines():
                    clean_line = line.strip()
                    if not clean_line or clean_line.startswith("#"):
                        continue
                    tokens = clean_line.split()
                    if len(tokens) >= 3 and tokens[0] == self.target_component and tokens[1] == self.target_interface:
                        parsed_dico["matching_entries"].append({
                            "raw_entry": clean_line,
                            "component": tokens[0],
                            "interface": tokens[1],
                            "library": tokens[2],
                        })
                parsed_dico["parsed"] = len(parsed_dico["matching_entries"]) > 0
            except Exception as e:
                parsed_dico["parse_error"] = str(e)

        # Cross-validate parsed AST against target specifications via dedicated blueprint verifier
        cpp_late_type = parsed_cpp.get("target_late_type")
        cpp_iface = parsed_cpp.get("tie_interface")
        cpp_ext_type = parsed_cpp.get("extension_type")
        cpp_base_class = parsed_cpp.get("base_class")

        blueprint_verified = self.verify_blueprint_contract(
            parsed_cpp=parsed_cpp,
            parsed_dico=parsed_dico,
            target_component=self.target_component,
            target_interface=self.target_interface,
        )

        return {
            "edu_directory_exists": edu_dir.is_dir(),
            "catpart_model_exists": catpart.is_file(),
            "catpart_path": str(catpart) if catpart.is_file() else None,
            "official_cpp_source_exists": cpp_src.is_file(),
            "official_dico_exists": dico_src.is_file(),
            "parsed_cpp_ast": parsed_cpp,
            "parsed_dico": parsed_dico,
            "official_blueprint_verified": blueprint_verified,
            "target_component_verified_from_ast": cpp_late_type,
            "target_interface_verified_from_ast": cpp_iface,
            "extension_type_verified": parsed_cpp.get("extension_type"),
            "catpart_content_status": "FILE_EXISTS_REQUIRES_CATIA_SESSION_FOR_TOPOLOGY",
        }

    # ── Line D: Layered Evidence Matrix with 4-Factor Probe Contract ─────
    def evaluate_layered_evidence(
        self,
        runtime_ws: pathlib.Path,
        cnext_pid: Optional[int] = None,
        loaded_modules: Optional[List[str]] = None,
        probe_log_file: Optional[pathlib.Path] = None,
        query_interface_hr: Optional[int] = None,
        expected_nonce: Optional[str] = None,
        expected_cnext_pid: Optional[int] = None,
        session_start_time: Optional[float] = None,
        cnext_identity: Optional[Tuple[str, Optional[int], Dict[str, Any]]] = None,
        launcher_pid: Optional[int] = None,
        t_start: Optional[float] = None,
        baseline_pids: Optional[set] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate L0 through L5 evidence status according to formal CADE contracts.
        L2 & L3 reuse unified run.py infrastructure (identify_target_cnext, verify_module_loaded).
        L4 strictly refuses unverified integer query_interface_hr and remains UNKNOWN until
        authentic in-session QueryInterface caller proof is established.
        """
        # L0: Physical Runtime View (delegated to runtime_view.check_runtime_view_l0)
        rt_l0 = check_runtime_view_l0(runtime_ws)
        rt_bin = runtime_ws / "win_b64" / "code" / "bin"
        rt_dico_dir = runtime_ws / "win_b64" / "code" / "dictionary"
        l0_ok = (rt_l0.get("status") == "PASS") and rt_bin.is_dir() and rt_dico_dir.is_dir()
        l0_res = {
            "level": "L0",
            "status": "PASS" if l0_ok else "FAIL",
            "check": "runtime_view_structure",
            "evidence": {
                "workspace": str(runtime_ws),
                "runtime_view_l0_status": rt_l0.get("status"),
                "bin_dir_exists": rt_bin.is_dir(),
                "dictionary_dir_exists": rt_dico_dir.is_dir(),
                "source": "runtime_view.check_runtime_view_l0",
            }
        }

        # L1: Static Assets (delegated to runtime_view.check_runtime_view_l1)
        dll_name = f"{self.target_module}.dll"
        target_dll = rt_bin / dll_name
        dico_file = rt_dico_dir / f"{self.target_framework}.dico"
        rt_l1 = check_runtime_view_l1(runtime_ws, target_module=self.target_module)

        pe_ok = _verify_pe_file(target_dll) if target_dll.is_file() else False
        dico_ok = False
        dico_count = 0
        if dico_file.is_file():
            dico_res = _verify_dico_syntax(dico_file, self.target_module)
            if isinstance(dico_res, dict):
                dico_ok = bool(dico_res.get("valid_syntax") and (
                    dico_res.get("mentions_target_module") is not False
                ))
                dico_count = dico_res.get("entry_count", 0)
            elif isinstance(dico_res, (tuple, list)):
                dico_ok = bool(dico_res[0])
                dico_count = dico_res[1] if len(dico_res) > 1 else 0

        l1_ok = (rt_l1.get("status") == "PASS") and pe_ok and dico_ok
        l1_res = {
            "level": "L1",
            "status": "PASS" if l1_ok else "FAIL",
            "check": "static_binary_assets",
            "evidence": {
                "runtime_view_l1_status": rt_l1.get("status"),
                "dll_path": str(target_dll),
                "dll_pe_valid": pe_ok,
                "dico_path": str(dico_file),
                "dico_syntax_valid": dico_ok,
                "dico_entries_count": dico_count,
                "source": "runtime_view.check_runtime_view_l1",
            }
        }

        # L2: Target Process Identity (Unified with run.py identify_target_cnext)
        l2_status = "NOT_RUN"
        l2_evidence = {}
        effective_pid = cnext_pid

        if cnext_identity is not None:
            l2_status, l2_pid, l2_ev = cnext_identity
            effective_pid = l2_pid
            l2_evidence = dict(l2_ev)
            l2_evidence["cnext_pid"] = l2_pid
            l2_evidence["source"] = "run.identify_target_cnext"
        elif launcher_pid is not None or t_start is not None:
            l2_status, l2_pid, l2_ev = identify_target_cnext(
                launcher_pid=launcher_pid,
                t_start=t_start,
                baseline_pids=baseline_pids,
            )
            effective_pid = l2_pid
            l2_evidence = dict(l2_ev)
            l2_evidence["cnext_pid"] = l2_pid
            l2_evidence["source"] = "run.identify_target_cnext"
        elif cnext_pid is not None:
            is_valid_pid = (type(cnext_pid) is int and not isinstance(cnext_pid, bool) and cnext_pid > 0)
            l2_status = "PASS" if is_valid_pid else "FAIL"
            l2_evidence = {"cnext_pid": cnext_pid, "verified": is_valid_pid, "source": "direct_pid_input"}
        else:
            l2_status = "NOT_RUN"
            l2_evidence = {"reason": "no_cnext_identification_provided"}

        l2_res = {
            "level": "L2",
            "status": l2_status,
            "check": "target_process_identity",
            "evidence": l2_evidence,
        }

        # L3: Module Loaded with Exact Path (Unified with run.py verify_module_loaded)
        l3_status = "NOT_RUN"
        l3_evidence = {}

        if loaded_modules is None and effective_pid is not None and effective_pid > 0:
            l3_status, l3_ev = verify_module_loaded(effective_pid, target_dll)
            l3_evidence = dict(l3_ev)
            l3_evidence["source"] = "run.verify_module_loaded"
        elif loaded_modules is not None:
            norm_expected = os.path.normcase(os.path.abspath(str(target_dll)))
            exact_matched_path = None
            stray_mismatch_path = None
            for mod in loaded_modules:
                norm_mod = os.path.normcase(os.path.abspath(mod))
                if norm_mod == norm_expected:
                    exact_matched_path = mod
                    break
                elif os.path.basename(norm_mod) == os.path.basename(norm_expected):
                    stray_mismatch_path = mod

            if exact_matched_path is not None:
                l3_status = "PASS"
            else:
                l3_status = "FAIL"

            l3_evidence = {
                "expected_target_dll": str(target_dll),
                "exact_matched_path": exact_matched_path,
                "stray_mismatch_path": stray_mismatch_path,
                "exact_match_pass": bool(exact_matched_path),
                "reason": "exact_path_loaded" if exact_matched_path else (
                    "stray_dll_loaded_from_wrong_path" if stray_mismatch_path else "dll_not_loaded"
                ),
                "source": "simulated_loaded_modules",
            }
        else:
            l3_evidence = {"reason": "no_pid_or_modules_provided_for_l3"}

        l3_res = {
            "level": "L3",
            "status": l3_status,
            "check": "module_loaded_exact_path",
            "evidence": l3_evidence,
        }

        # L4: Object Modeler Resolution & Extension Activation (Strict Atomic Contract)
        # 1. Constructor Probe Verification:
        #    Requires 4 factors on SAME line: ACTION=CONSTRUCTOR_ACTIVATED, NONCE, PID, COMPONENT, plus mtime freshness.
        # 2. QueryInterface Verification:
        #    A plain integer query_interface_hr=0 passed from outside is unverified and cannot prove in-session QI.
        #    Without an authentic in-session QI probe certificate binding PID, Nonce, Interface, and S_OK,
        #    L4 Object Modeler QueryInterface activation strictly remains UNKNOWN!
        l4_status = "UNKNOWN"
        credentials_valid = False
        try:
            credentials_valid = bool(
                isinstance(expected_nonce, str)
                and bool(expected_nonce.strip())
                and type(expected_cnext_pid) is int
                and not isinstance(expected_cnext_pid, bool)
                and expected_cnext_pid > 0
                and (type(session_start_time) in (int, float))
                and not isinstance(session_start_time, bool)
                and math.isfinite(session_start_time)
                and session_start_time > 0
            )
        except Exception:
            credentials_valid = False

        probe_contract = {
            "file_exists": False,
            "credentials_provided": credentials_valid,
            "freshness_valid": False,
            "atomic_event_verified": False,
            "matched_record": None,
            "all_factors_satisfied": False,
        }

        if credentials_valid and probe_log_file and probe_log_file.is_file():
            probe_contract["file_exists"] = True
            try:
                mtime = os.path.getmtime(probe_log_file)
                if mtime >= (session_start_time - 1.0):
                    probe_contract["freshness_valid"] = True

                if probe_contract["freshness_valid"]:
                    log_lines = probe_log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for line_no, line in enumerate(log_lines, start=1):
                        pairs = {}
                        for token in line.split(";"):
                            if "=" in token:
                                k, v = token.strip().split("=", 1)
                                pairs[k.strip().upper()] = v.strip()

                        is_constructor_action = (pairs.get("ACTION") == "CONSTRUCTOR_ACTIVATED")
                        nonce_matches = (pairs.get("NONCE") == expected_nonce)
                        pid_matches = (pairs.get("PID") == str(expected_cnext_pid))
                        component_matches = (pairs.get("COMPONENT") == self.target_component)

                        if is_constructor_action and nonce_matches and pid_matches and component_matches:
                            probe_contract["atomic_event_verified"] = True
                            probe_contract["matched_record"] = {
                                "line_number": line_no,
                                "raw_line": line.strip(),
                                "action": pairs.get("ACTION"),
                                "nonce": pairs.get("NONCE"),
                                "pid": pairs.get("PID"),
                                "component": pairs.get("COMPONENT"),
                            }
                            break

                probe_contract["all_factors_satisfied"] = bool(
                    credentials_valid
                    and probe_contract["file_exists"]
                    and probe_contract["freshness_valid"]
                    and probe_contract["atomic_event_verified"]
                )
            except Exception as e:
                probe_contract["parse_error"] = str(e)

        if probe_contract["all_factors_satisfied"]:
            # Constructor was proven activated by Object Modeler.
            # But plain external integer query_interface_hr is unverified and cannot yield PASS.
            # L4 strictly remains UNKNOWN until genuine in-session QI probe certificate is established.
            l4_status = "UNKNOWN"
            l4_evidence = {
                "status": "CONSTRUCTOR_ACTIVATED_QI_UNPROVEN",
                "constructor_probe_verified": True,
                "query_interface_status": "UNKNOWN",
                "probe_details": probe_contract,
                "activated_extension": "MyVisuExtension",
                "reason": "query_interface_unverified_requires_in_session_qi_probe_certificate",
                "note": (
                    "Constructor activation probe confirmed instantiation by Object Modeler. "
                    "However, external integer query_interface_hr does not prove authentic in-session QI. "
                    "L4 strictly remains UNKNOWN until a verifiable in-session QI probe is implemented."
                ),
            }
        elif query_interface_hr is not None and query_interface_hr != 0:
            l4_status = "FAIL"
            l4_evidence = {
                "query_interface_hr": hex(query_interface_hr),
                "error_reason": "QueryInterface returned non-zero HRESULT",
                "probe_details": probe_contract,
            }
        else:
            reason = "awaiting_valid_om_trigger_and_atomic_probe_certificate"
            if not credentials_valid:
                reason = "missing_mandatory_credentials_nonce_pid_or_session_time"
            elif probe_log_file and not probe_contract["file_exists"]:
                reason = "probe_log_file_not_found"
            elif not probe_contract["freshness_valid"]:
                reason = "probe_log_stale_or_expired"
            elif not probe_contract["atomic_event_verified"]:
                reason = "no_atomic_constructor_activation_event_found"

            l4_evidence = {
                "reason": reason,
                "query_interface_hr": hex(query_interface_hr) if query_interface_hr is not None else "NOT_PROBED",
                "probe_contract": probe_contract,
                "trigger_recipe": f"pMeasureSet->QueryInterface(IID_{self.target_interface}, (void**)&piVisu)",
            }

        l4_res = {
            "level": "L4",
            "status": l4_status,
            "check": "object_modeler_dictionary_resolution_and_extension_activation",
            "evidence": l4_evidence,
        }

        l4_res = {
            "level": "L4",
            "status": l4_status,
            "check": "object_modeler_dictionary_resolution_and_extension_activation",
            "evidence": l4_evidence,
        }

        # L5: Visual Verification (Strictly Independent Reservation)
        l5_res = {
            "level": "L5",
            "status": "NOT_RUN",
            "check": "visual_verification",
            "evidence": {
                "status": "PENDING_GEOMETRIC_IMPL",
                "note": "CADE generator produces minimal valid CAT3DBagRep. Geometric visual validation will be evaluated in subsequent milestone.",
            }
        }

        return {
            "L0": l0_res,
            "L1": l1_res,
            "L2": l2_res,
            "L3": l3_res,
            "L4": l4_res,
            "L5": l5_res,
        }

    # ── Probe Code Generator ──────────────────────────────────────────────
    def generate_cpp_probe_source(self, extension_name: str = "MyVisuExtension") -> str:
        """
        Generate C++ implementation containing the 4-Factor Probe emitter.
        Emits NONCE, PID, COMPONENT, and ACTION to CADE_PROBE_FILE.
        """
        return f"""// Generated by CADE OM Activation Driver with 4-Factor Probe Contract
#include "{extension_name}.h"
#include <TIE_{self.target_interface}.h>
#include <CAT3DBagRep.h>
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

TIE_{self.target_interface}({extension_name});

CATImplementClass({extension_name}, DataExtension, CATExtIVisu, {self.target_component});

{extension_name}::{extension_name}()
{{
    // 4-Factor Probe Emission
    const char *probeFile = getenv("CADE_PROBE_FILE");
    const char *nonce = getenv("CADE_PROBE_NONCE");
    if (probeFile && probeFile[0] != '\\0') {{
        FILE *fp = fopen(probeFile, "a");
        if (fp) {{
            DWORD pid = GetCurrentProcessId();
            fprintf(fp, "ACTION=CONSTRUCTOR_ACTIVATED;NONCE=%s;PID=%lu;COMPONENT={self.target_component}\\n",
                    nonce ? nonce : "NONE", (unsigned long)pid);
            fclose(fp);
        }}
    }}
}}

{extension_name}::~{extension_name}()
{{
}}

CATRep * {extension_name}::BuildRep()
{{
    return new CAT3DBagRep();
}}
"""

    def generate_trigger_macro(
        self,
        model_path: pathlib.Path,
        output_macro_path: pathlib.Path,
    ) -> str:
        """
        Generate CATScript macro that opens the target CATPart and executes Reframe
        to trigger 3D Viewer geometric visualization pipeline and CATI3DGeoVisu resolution.
        """
        model_win_path = str(model_path).replace("/", "\\")
        macro_content = (
            'Language="VBSCRIPT"\n'
            'Sub CATMain()\n'
            '    On Error Resume Next\n'
            '    Dim docs, doc, win, viewer\n'
            '    Set docs = CATIA.Documents\n'
            f'    Set doc = docs.Open("{model_win_path}")\n'
            '    Set win = CATIA.ActiveWindow\n'
            '    If Not win Is Nothing Then\n'
            '        Set viewer = win.ActiveViewer\n'
            '        If Not viewer Is Nothing Then\n'
            '            viewer.Reframe\n'
            '        End If\n'
            '    End If\n'
            '    If Not doc Is Nothing Then\n'
            '        doc.Close\n'
            '    End If\n'
            '    CATIA.Quit\n'
            'End Sub\n'
        )
        output_macro_path.parent.mkdir(parents=True, exist_ok=True)
        output_macro_path.write_text(macro_content, encoding="utf-8")
        return macro_content

    def execute_live_activation(
        self,
        workspace_path: Optional[str] = None,
        model_path: Optional[str] = None,
        timeout: int = 60,
        runner_fn: Optional[Any] = None,
        monitor_poll_interval: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Execute Live Activation Protocol:
        Phase A: Validate and prepare isolated Runtime View and dictionary precedence.
        Phase B: Acquire official validation model (CAAMmrMultiMeasureAndMeasureSet.CATPart).
        Phase C: Generate trigger script, launch CNEXT -macro via mkrun, trigger Visu pipeline.
        Phase D: Synchronously capture PSAPI module enumeration delta (L3) and 4-factor probe log (L4),
                 then evaluate full L0~L5 layered evidence.
        """
        ws_path = pathlib.Path(workspace_path or self.workspace_path or ".")
        runtime_ws = ws_path.resolve()

        # Phase A: Verify workspace runtime view layout
        rt_bin = runtime_ws / "win_b64" / "code" / "bin"
        rt_dico_dir = runtime_ws / "win_b64" / "code" / "dictionary"
        target_dll = rt_bin / f"{self.target_module}.dll"
        target_dico = rt_dico_dir / f"{self.target_framework}.dico"

        phase_a_info = {
            "workspace": str(runtime_ws),
            "bin_exists": rt_bin.is_dir(),
            "dictionary_dir_exists": rt_dico_dir.is_dir(),
            "target_dll_exists": target_dll.is_file(),
            "target_dico_exists": target_dico.is_file(),
        }

        # Phase B: Resolve target CATPart model
        resolved_model = None
        if model_path:
            p = pathlib.Path(model_path)
            if p.is_file():
                resolved_model = p.resolve()
        if not resolved_model:
            candidate = (
                self.b28_root
                / "CAADoc"
                / "CAAMechanicalModeler.edu"
                / "InputData"
                / "CAAMmrMultiMeasureAndMeasureSet.CATPart"
            )
            if candidate.is_file():
                resolved_model = candidate.resolve()

        phase_b_info = {
            "model_path": str(resolved_model) if resolved_model else None,
            "model_exists": bool(resolved_model and resolved_model.is_file()),
            "component": self.target_component,
        }

        # Phase C & D Preparation: Nonce, Probe Log, Macro Script
        expected_nonce = f"NONCE_{uuid.uuid4().hex[:12].upper()}"
        probe_log = runtime_ws / "cade_probe_live.log"
        if probe_log.exists():
            try:
                probe_log.unlink()
            except OSError:
                pass

        macro_file = runtime_ws / "cade_trigger_visu.CATScript"
        target_model_for_script = resolved_model or (runtime_ws / "CAAMmrMultiMeasureAndMeasureSet.CATPart")
        self.generate_trigger_macro(target_model_for_script, macro_file)

        session_start_time = time.time()
        captured_pid: Optional[int] = None
        captured_modules: Optional[List[str]] = None
        stop_monitor = threading.Event()

        # Set environment variables for probe emission
        short_probe_log = _to_short_path(str(probe_log))
        os.environ["CADE_PROBE_FILE"] = short_probe_log
        os.environ["CADE_PROBE_NONCE"] = expected_nonce

        # Background PSAPI Process & Module Monitor
        def _monitor_cnext():
            nonlocal captured_pid, captured_modules
            initial_pids = set()
            try:
                for p in get_processes_snapshot_win32() or []:
                    if p.get("name", "").lower() == "cnext.exe":
                        initial_pids.add(p.get("pid"))
            except Exception:
                pass

            norm_expected_dll = os.path.normcase(os.path.abspath(str(target_dll)))

            while not stop_monitor.is_set():
                try:
                    current_procs = get_processes_snapshot_win32() or []
                    cnext_pids = [
                        p.get("pid") for p in current_procs
                        if p.get("name", "").lower() == "cnext.exe"
                    ]
                    # Prioritize newly spawned CNEXT process
                    new_pids = [pid for pid in cnext_pids if pid not in initial_pids]
                    target_pid = new_pids[0] if new_pids else (cnext_pids[0] if cnext_pids else None)

                    if target_pid:
                        captured_pid = target_pid
                        mods = get_process_loaded_modules(target_pid)
                        if mods:
                            captured_modules = mods
                            # Stop early if target module is already loaded
                            if any(os.path.normcase(os.path.abspath(m)) == norm_expected_dll for m in mods):
                                break
                except Exception:
                    pass
                stop_monitor.wait(monitor_poll_interval)

        monitor_thread = threading.Thread(target=_monitor_cnext, daemon=True)
        monitor_thread.start()

        # Launch Execution
        macro_exec_result = {}
        try:
            if runner_fn is not None:
                # Custom/Mock runner for unit testing and controlled execution
                macro_exec_result = runner_fn(
                    macro_path=_to_short_path(str(macro_file)),
                    workspace_path=str(runtime_ws),
                    timeout=timeout,
                )
            else:
                # Real launcher via run_catia_macro
                short_macro = _to_short_path(str(macro_file))
                macro_exec_result = run_catia_macro(
                    macro_path=short_macro,
                    workspace_path=str(runtime_ws),
                    timeout=timeout,
                )
        except Exception as e:
            macro_exec_result = {"status": "error", "message": str(e)}
        finally:
            stop_monitor.set()
            monitor_thread.join(timeout=3.0)
            os.environ.pop("CADE_PROBE_FILE", None)
            os.environ.pop("CADE_PROBE_NONCE", None)
            if macro_file.exists():
                try:
                    macro_file.unlink()
                except OSError:
                    pass

        # Fallback values from runner result if provided for testing
        if captured_pid is None and "cnext_pid" in macro_exec_result:
            captured_pid = macro_exec_result["cnext_pid"]
        if captured_modules is None and "loaded_modules" in macro_exec_result:
            captured_modules = macro_exec_result["loaded_modules"]

        # Phase D: Determine QI HRESULT based on execution and probe
        query_interface_hr = None
        if "query_interface_hr" in macro_exec_result:
            query_interface_hr = macro_exec_result["query_interface_hr"]
        elif macro_exec_result.get("status") == "success":
            query_interface_hr = 0
        elif macro_exec_result.get("status") in ("failed", "error", "timeout"):
            query_interface_hr = 0x80004005  # E_FAIL

        # Evaluate Layered Evidence Matrix (L0 ~ L5)
        evidence = self.evaluate_layered_evidence(
            runtime_ws=runtime_ws,
            cnext_pid=captured_pid,
            loaded_modules=captured_modules,
            probe_log_file=probe_log,
            query_interface_hr=query_interface_hr,
            expected_nonce=expected_nonce,
            expected_cnext_pid=captured_pid,
            session_start_time=session_start_time,
        )

        l4_status = evidence["L4"]["status"]
        if any(evidence[lvl]["status"] == "FAIL" for lvl in ("L0", "L1", "L2", "L3", "L4")):
            overall_status = "FAIL"
        elif (
            evidence["L0"]["status"] == "PASS"
            and evidence["L1"]["status"] == "PASS"
            and evidence["L2"]["status"] == "PASS"
            and evidence["L3"]["status"] == "PASS"
        ):
            if l4_status == "PASS":
                overall_status = "PASS"
            else:
                overall_status = "UNKNOWN"
        else:
            overall_status = "UNKNOWN"

        return {
            "protocol": "Live_Activation_Protocol_CNEXT_Macro",
            "overall_status": overall_status,
            "phase_a_runtime_view": phase_a_info,
            "phase_b_model": phase_b_info,
            "phase_c_macro_execution": macro_exec_result,
            "phase_d_evidence": evidence,
            "credentials": {
                "nonce": expected_nonce,
                "cnext_pid": captured_pid,
                "session_start_time": session_start_time,
                "probe_log": str(probe_log),
            },
        }

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """
        Generate full diagnostic and design report covering Lines B, C, and D.
        """
        conflict_info = self.check_system_dictionary_conflict()
        usecase_info = self.inspect_official_usecase()

        return {
            "architecture_scope": "CATIA CAA V5 Object Modeler DataExtension (not UI Add-in)",
            "target": {
                "component_late_type": self.target_component,
                "interface": self.target_interface,
                "extension_module": self.target_module,
                "framework": self.target_framework,
            },
            "line_b_official_usecase": usecase_info,
            "line_c_dictionary_conflict_analysis": conflict_info,
            "execution_protocol": {
                "phase_a": "Mount isolated runtime view containing AcceptanceFw.dico with precedence in CATDictionaryPath",
                "phase_b": f"Acquire real {self.target_component} instance from InputData\\CAAMmrMultiMeasureAndMeasureSet.CATPart",
                "phase_c": f"Invoke QueryInterface(IID_{self.target_interface}) on instance to trigger Object Modeler lookup and LoadLibraryExW",
                "phase_d": "Capture PSAPI module enumeration delta (L3) and 4-factor probe log (L4)",
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Object Modeler DataExtension Trigger & Evidence Driver")
    parser.add_argument("--b28-root", help="CATIA B28 installation root")
    parser.add_argument("--workspace", help="Workspace path for live activation")
    parser.add_argument("--model", help="Target CATPart model path")
    parser.add_argument("--live", action="store_true", help="Execute live activation protocol")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds for live activation")
    parser.add_argument("--json", action="store_true", help="Output full JSON report")
    args = parser.parse_args()

    driver = OMActivationDriver(b28_root=args.b28_root, workspace_path=args.workspace)

    if args.live:
        rep = driver.execute_live_activation(
            workspace_path=args.workspace,
            model_path=args.model,
            timeout=args.timeout,
        )
    else:
        rep = driver.generate_comprehensive_report()

    if args.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    elif args.live:
        print("=" * 70)
        print("  CADE Live Object Modeler Activation Protocol (CNEXT -macro)")
        print("=" * 70)
        print(f"Overall Status   : {rep['overall_status']}")
        print("\n[Phase A: Isolated Runtime View]")
        pa = rep["phase_a_runtime_view"]
        print(f"  Workspace      : {pa['workspace']}")
        print(f"  Bin Dir        : {'PASS' if pa['bin_exists'] else 'FAIL'}")
        print(f"  Dictionary Dir : {'PASS' if pa['dictionary_dir_exists'] else 'FAIL'}")
        print(f"  Target DLL     : {'FOUND' if pa['target_dll_exists'] else 'MISSING'}")
        print(f"  Target DICO    : {'FOUND' if pa['target_dico_exists'] else 'MISSING'}")
        print("\n[Phase B: Official Model Resolution]")
        pb = rep["phase_b_model"]
        print(f"  Model Path     : {pb['model_path']}")
        print(f"  Model Exists   : {pb['model_exists']}")
        print(f"  Component      : {pb['component']}")
        print("\n[Phase C: Trigger Macro Execution]")
        pc = rep["phase_c_macro_execution"]
        print(f"  Macro Status   : {pc.get('status')}")
        print(f"  Macro Message  : {pc.get('message')}")
        print("\n[Phase D: Layered Evidence Matrix (L0 ~ L5)]")
        ev = rep["phase_d_evidence"]
        for level in ["L0", "L1", "L2", "L3", "L4", "L5"]:
            item = ev.get(level, {})
            print(f"  [{item.get('status', 'UNKNOWN')}] {level}: {item.get('check')}")
        print("=" * 70)
    else:
        print("=" * 70)
        print("  CADE Object Modeler Activation & Evidence Driver")
        print("=" * 70)
        print(f"Target Component : {rep['target']['component_late_type']}")
        print(f"Target Interface : {rep['target']['interface']}")
        print(f"Target Module    : {rep['target']['extension_module']}")
        print("\n[Line B: Official Use Case Assets]")
        uc = rep['line_b_official_usecase']
        print(f"  CAAMechanicalModeler.edu exists : {uc['edu_directory_exists']}")
        print(f"  CATPart Model exists           : {uc['catpart_model_exists']} ({uc['catpart_path']})")
        print(f"  Official CPP AST Verified      : {uc['official_blueprint_verified']}")
        print(f"  Late Type Extracted from AST   : {uc['target_component_verified_from_ast']}")
        print(f"  Interface Extracted from AST   : {uc['target_interface_verified_from_ast']}")
        print(f"  Extension Type Extracted       : {uc['extension_type_verified']}")
        print(f"  CATPart Content Status         : {uc['catpart_content_status']}")
        print("\n[Line C: Dictionary Conflict Analysis]")
        dc = rep['line_c_dictionary_conflict_analysis']
        print(f"  Total Dictionaries Discovered  : {dc['total_dictionaries_discovered']}")
        print(f"  Successfully Scanned           : {dc['scanned_dictionaries_success']}")
        print(f"  Unreadable Files Count         : {dc['unreadable_files_count']}")
        print(f"  Scan Completeness Rate         : {dc['scan_completeness_rate']}")
        print(f"  System Conflicts Detected      : {dc['exact_interface_conflicts']}")
        print(f"  Exclusive Mapping in Scanned   : {dc['exclusive_mapping_in_scanned_dictionaries']}")
        print(f"  Precedence Status              : {dc['precedence_status']}")
        print(f"  Precedence Note                : {dc['precedence_note']}")
        print("\n[Line D: Execution Protocol (Phase A ~ D)]")
        proto = rep['execution_protocol']
        for k, v in proto.items():
            print(f"  {k.upper()}: {v}")
        print("=" * 70)


if __name__ == "__main__":
    main()
