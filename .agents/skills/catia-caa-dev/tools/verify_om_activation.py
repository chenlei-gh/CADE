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
import uuid
import time
import argparse
import pathlib
from typing import Dict, Any, List, Optional, Tuple

SKILL_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from env import CAAEnvironment
from runtime_view import _verify_pe_file, _verify_dico_syntax
from run import (
    get_processes_snapshot_win32,
    get_process_loaded_modules,
)


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
    def inspect_official_usecase(self) -> Dict[str, Any]:
        """
        Verify the existence and parse genuine Dassault official CAAMechanicalModeler.edu assets:
        - CAAMmrMultiMeasureAndMeasureSet.CATPart (real model containing CAAMmrMeasureSet)
        - CAAEMmrMeasureSetVisu.cpp (parsed via regex for CATImplementClass and TIE_)
        - CAAMechanicalModeler.edu.dico (parsed for exact matching entries)
        """
        edu_dir = self.b28_root / "CAADoc" / "CAAMechanicalModeler.edu"
        catpart = edu_dir / "InputData" / "CAAMmrMultiMeasureAndMeasureSet.CATPart"
        cpp_src = edu_dir / "CAAMmrMultiMeasureAndMeasureSet.m" / "src" / "CAAEMmrMeasureSetVisu.cpp"
        dico_src = edu_dir / "CAAMechanicalModelerEduRscCNext.m" / "src" / "CNext" / "code" / "dictionary" / "CAAMechanicalModeler.edu.dico"

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

        # Cross-validate parsed AST against target specifications
        cpp_late_type = parsed_cpp.get("target_late_type")
        cpp_iface = parsed_cpp.get("tie_interface")
        cpp_ext_type = parsed_cpp.get("extension_type")
        cpp_base_class = parsed_cpp.get("base_class")
        dico_entry_match = len(parsed_dico.get("matching_entries", [])) > 0

        blueprint_verified = bool(
            parsed_cpp["parsed"]
            and cpp_ext_type == "DataExtension"
            and cpp_late_type == self.target_component
            and cpp_iface == self.target_interface
            and cpp_base_class == "CATExtIVisu"
            and dico_entry_match
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
    ) -> Dict[str, Any]:
        """
        Evaluate L0 through L5 evidence status according to formal CADE contracts.
        Enforces exact DLL path matching for L3 and 4-factor probe validation for L4.
        """
        # L0: Runtime View
        rt_bin = runtime_ws / "win_b64" / "code" / "bin"
        rt_dico_dir = runtime_ws / "win_b64" / "code" / "dictionary"
        l0_ok = rt_bin.is_dir() and rt_dico_dir.is_dir()
        l0_res = {
            "level": "L0",
            "status": "PASS" if l0_ok else "FAIL",
            "check": "runtime_view_structure",
            "evidence": {
                "workspace": str(runtime_ws),
                "bin_dir_exists": rt_bin.is_dir(),
                "dictionary_dir_exists": rt_dico_dir.is_dir(),
            }
        }

        # L1: Static Assets
        dll_name = f"{self.target_module}.dll"
        target_dll = rt_bin / dll_name
        dico_file = rt_dico_dir / f"{self.target_framework}.dico"

        pe_ok = _verify_pe_file(target_dll) if target_dll.is_file() else False
        dico_ok, dico_count = _verify_dico_syntax(dico_file, self.target_module) if dico_file.is_file() else (False, 0)
        l1_ok = pe_ok and dico_ok
        l1_res = {
            "level": "L1",
            "status": "PASS" if l1_ok else "FAIL",
            "check": "static_binary_assets",
            "evidence": {
                "dll_path": str(target_dll),
                "dll_pe_valid": pe_ok,
                "dico_path": str(dico_file),
                "dico_syntax_valid": dico_ok,
                "dico_entries_count": dico_count,
            }
        }

        # L2: Target Process Identity
        l2_status = "NOT_RUN"
        l2_evidence = {}
        if cnext_pid is not None:
            l2_status = "PASS" if cnext_pid > 0 else "FAIL"
            l2_evidence = {"cnext_pid": cnext_pid, "verified": cnext_pid > 0}
        l2_res = {
            "level": "L2",
            "status": l2_status,
            "check": "target_process_identity",
            "evidence": l2_evidence,
        }

        # L3: Module Loaded with Exact Path (Strict Path Invariant)
        l3_status = "NOT_RUN"
        exact_matched_path = None
        stray_mismatch_path = None

        if loaded_modules is not None:
            norm_expected = os.path.normcase(os.path.abspath(str(target_dll)))
            for mod in loaded_modules:
                norm_mod = os.path.normcase(os.path.abspath(mod))
                if norm_mod == norm_expected:
                    exact_matched_path = mod
                    break
                elif os.path.basename(norm_mod) == os.path.basename(norm_expected):
                    stray_mismatch_path = mod

            # Strict L3 Rule: Only PASS when the exact path matches
            if exact_matched_path is not None:
                l3_status = "PASS"
            else:
                l3_status = "FAIL"

        l3_res = {
            "level": "L3",
            "status": l3_status,
            "check": "module_loaded_exact_path",
            "evidence": {
                "expected_target_dll": str(target_dll),
                "exact_matched_path": exact_matched_path,
                "stray_mismatch_path": stray_mismatch_path,
                "exact_match_pass": bool(exact_matched_path),
                "reason": "exact_path_loaded" if exact_matched_path else (
                    "stray_dll_loaded_from_wrong_path" if stray_mismatch_path else "dll_not_loaded"
                ),
            }
        }

        # L4: Object Modeler Resolution & Extension Activation (Strict Atomic 4-Factor Contract)
        # Factors:
        # 1. Mandatory credentials provided (valid non-empty nonce, positive pid, non-zero session_start_time)
        # 2. QI S_OK (0x0)
        # 3. File Freshness (mtime >= session_start_time - 1.0)
        # 4. Atomic Event Record: ACTION=CONSTRUCTOR_ACTIVATED, NONCE, PID, COMPONENT all match on the SAME line!
        l4_status = "UNKNOWN"
        credentials_valid = bool(
            expected_nonce and isinstance(expected_nonce, str) and expected_nonce.strip()
            and expected_cnext_pid and isinstance(expected_cnext_pid, int) and expected_cnext_pid > 0
            and session_start_time and isinstance(session_start_time, (int, float)) and session_start_time > 0
        )

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
                # Freshness check: file mtime must be >= session_start_time - 1.0
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

                        # Enforce single atomic event record invariant:
                        # ACTION, NONCE, PID, and COMPONENT must ALL be satisfied simultaneously on the SAME line.
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
                            break  # Found verified atomic activation record

                probe_contract["all_factors_satisfied"] = bool(
                    credentials_valid
                    and probe_contract["file_exists"]
                    and probe_contract["freshness_valid"]
                    and probe_contract["atomic_event_verified"]
                )
            except Exception as e:
                probe_contract["parse_error"] = str(e)

        if query_interface_hr == 0 and probe_contract["all_factors_satisfied"]:
            l4_status = "PASS"
            l4_evidence = {
                "query_interface_hr": "S_OK (0x0)",
                "atomic_probe_verified": True,
                "probe_details": probe_contract,
                "activated_extension": "MyVisuExtension",
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
    parser.add_argument("--json", action="store_true", help="Output full JSON report")
    args = parser.parse_args()

    driver = OMActivationDriver(b28_root=args.b28_root)
    rep = driver.generate_comprehensive_report()

    if args.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
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
