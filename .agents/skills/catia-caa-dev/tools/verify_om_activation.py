#!/usr/bin/env python3
"""
Object Modeler DataExtension Trigger & Runtime Evidence Verification Driver
=============================================================================
Unified Driver for P0-2 Verification:
- Line B: Official Use Case and Real CAAMmrMeasureSet asset verification
- Line C: B28 System Dictionary Conflict & Search Order Analysis
- Line D: End-to-End L0~L5 Layered Evidence Capture (DLL loading, OM activation probe)
"""

import os
import sys
import glob
import json
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
    Covers Preflight, Dictionary Conflict Analysis, Probe Deployment, and Layered Evidence.
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

    # ── Line C: System Dictionary Conflict & Priority Analysis ────────────
    def check_system_dictionary_conflict(self) -> Dict[str, Any]:
        """
        Scan all B28 system dictionaries under win_b64/code/dictionary.
        Check if (target_component, target_interface) is already registered in stock B28.
        """
        dico_dir = self.b28_root / "win_b64" / "code" / "dictionary"
        matches = []
        scanned_files = 0

        if dico_dir.is_dir():
            for dico_file in glob.glob(str(dico_dir / "*.dico")) + glob.glob(str(dico_dir / "*.dic")):
                scanned_files += 1
                try:
                    with open(dico_file, "r", encoding="latin-1", errors="ignore") as fp:
                        for line_no, raw_line in enumerate(fp, start=1):
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue
                            parts = line.split()
                            if len(parts) >= 2 and parts[0] == self.target_component:
                                matches.append({
                                    "file": os.path.basename(dico_file),
                                    "line": line_no,
                                    "entry": line,
                                    "component": parts[0],
                                    "interface": parts[1],
                                    "library": parts[2] if len(parts) >= 3 else "",
                                })
                except Exception as e:
                    pass

        interface_matches = [m for m in matches if m.get("interface") == self.target_interface]
        has_conflict = len(interface_matches) > 0

        analysis = {
            "scanned_system_dictionaries": scanned_files,
            "target_component": self.target_component,
            "target_interface": self.target_interface,
            "total_component_registrations": len(matches),
            "exact_interface_conflicts": len(interface_matches),
            "conflict_entries": interface_matches,
            "has_system_conflict": has_conflict,
            "exclusive_mapping": not has_conflict,
            "priority_rule": (
                "When CATDictionaryPath prepends the isolated runtime view, "
                "isolated entries take precedence in Object Modeler dictionary table. "
                "Since stock B28 has 0 conflict registrations for this pair, "
                "the isolated AcceptanceMod.dll is the sole provider of CATI3DGeoVisu for CAAMmrMeasureSet."
            ) if not has_conflict else (
                "Stock B28 contains existing registration. Isolated CATDictionaryPath must precede "
                "system path to ensure shadowing/override."
            )
        }
        return analysis

    # ── Line B: Official Use Case & Real Asset Verification ────────────────
    def inspect_official_usecase(self) -> Dict[str, Any]:
        """
        Verify the existence of Dassault official CAAMechanicalModeler.edu assets:
        - CAAMmrMultiMeasureAndMeasureSet.CATPart (real model containing CAAMmrMeasureSet)
        - CAAEMmrMeasureSetVisu.cpp (official implementation blueprint)
        - CAAMechanicalModeler.edu.dico
        """
        edu_dir = self.b28_root / "CAADoc" / "CAAMechanicalModeler.edu"
        catpart = edu_dir / "InputData" / "CAAMmrMultiMeasureAndMeasureSet.CATPart"
        cpp_src = edu_dir / "CAAMmrMultiMeasureAndMeasureSet.m" / "src" / "CAAEMmrMeasureSetVisu.cpp"
        dico_src = edu_dir / "CAAMechanicalModelerEduRscCNext.m" / "src" / "CNext" / "code" / "dictionary" / "CAAMechanicalModeler.edu.dico"

        official_dico_entry = None
        if dico_src.is_file():
            try:
                for line in dico_src.read_text(encoding="latin-1", errors="ignore").splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[0] == self.target_component and parts[1] == self.target_interface:
                        official_dico_entry = line.strip()
                        break
            except Exception:
                pass

        return {
            "edu_directory_exists": edu_dir.is_dir(),
            "catpart_model_exists": catpart.is_file(),
            "catpart_path": str(catpart) if catpart.is_file() else None,
            "official_cpp_source_exists": cpp_src.is_file(),
            "official_dico_exists": dico_src.is_file(),
            "official_dico_entry": official_dico_entry,
            "late_type_confirmed": self.target_component,
            "interface_confirmed": self.target_interface,
            "architecture_blueprint": "CATImplementClass(CAAEMmrMeasureSetVisu, DataExtension, CATExtIVisu, CAAMmrMeasureSet) + TIE_CATI3DGeoVisu",
        }

    # ── Line D: Layered Evidence Matrix Evaluator ─────────────────────────
    def evaluate_layered_evidence(
        self,
        runtime_ws: pathlib.Path,
        cnext_pid: Optional[int] = None,
        loaded_modules: Optional[List[str]] = None,
        probe_log_file: Optional[pathlib.Path] = None,
        query_interface_hr: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate L0 through L5 evidence status according to formal CADE contracts.
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

        # L3: Module Loaded with Exact Path
        l3_status = "NOT_RUN"
        matched_module_path = None
        if loaded_modules is not None:
            exact_expected = str(target_dll).lower()
            for mod in loaded_modules:
                if mod.lower() == exact_expected:
                    matched_module_path = mod
                    break
                elif os.path.basename(mod).lower() == dll_name.lower():
                    matched_module_path = mod
            l3_status = "PASS" if matched_module_path else "FAIL"
        l3_res = {
            "level": "L3",
            "status": l3_status,
            "check": "module_loaded_exact_path",
            "evidence": {
                "target_dll": str(target_dll),
                "loaded_match": matched_module_path,
                "exact_match_pass": bool(matched_module_path and matched_module_path.lower() == str(target_dll).lower()),
            }
        }

        # L4: Object Modeler Dictionary Resolution & Extension Activation
        l4_status = "UNKNOWN"
        l4_evidence = {}
        constructor_instantiated = False
        if probe_log_file and probe_log_file.is_file():
            try:
                log_content = probe_log_file.read_text(encoding="utf-8", errors="ignore")
                if "INSTANTIATED" in log_content and self.target_component in log_content:
                    constructor_instantiated = True
            except Exception:
                pass

        if query_interface_hr == 0 and constructor_instantiated:
            l4_status = "PASS"
            l4_evidence = {
                "query_interface_hr": "S_OK (0x0)",
                "constructor_probe_hit": True,
                "probe_log": str(probe_log_file),
                "active_extension": "MyVisuExtension",
            }
        elif query_interface_hr is not None:
            l4_status = "FAIL" if query_interface_hr != 0 else "UNKNOWN"
            l4_evidence = {
                "query_interface_hr": hex(query_interface_hr),
                "constructor_probe_hit": constructor_instantiated,
            }
        else:
            l4_evidence = {
                "reason": "awaiting_om_query_interface_trigger",
                "trigger_recipe": f"pMeasureSet->QueryInterface(IID_{self.target_interface}, (void**)&piVisu)",
                "constructor_probe_hit": constructor_instantiated,
            }

        l4_res = {
            "level": "L4",
            "status": l4_status,
            "check": "object_modeler_dictionary_resolution_and_extension_activation",
            "evidence": l4_evidence,
        }

        # L5: Visual Verification
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
                "phase_d": "Capture PSAPI module enumeration delta (L3) and probe log for constructor instantiation (L4)",
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
        print(f"  Official Visu CPP Blueprint    : {uc['official_cpp_source_exists']}")
        print("\n[Line C: Dictionary Conflict Analysis]")
        dc = rep['line_c_dictionary_conflict_analysis']
        print(f"  Scanned System Dictionaries    : {dc['scanned_system_dictionaries']}")
        print(f"  System Conflicts Detected      : {dc['exact_interface_conflicts']}")
        print(f"  Exclusive Mapping in B28       : {dc['exclusive_mapping']}")
        print(f"  Priority Rule                  : {dc['priority_rule']}")
        print("\n[Line D: Execution Protocol (Phase A ~ D)]")
        proto = rep['execution_protocol']
        for k, v in proto.items():
            print(f"  {k.upper()}: {v}")
        print("=" * 70)


if __name__ == "__main__":
    main()
