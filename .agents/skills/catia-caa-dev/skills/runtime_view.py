"""
CATIA CAA Runtime View Skill
=============================
Purpose: Create and manage CATIA Runtime View
Usage: python runtime_view.py [workspace_path] [options]
Output: JSON with runtime view status
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from env import CAAEnvironment
from utils import Cache, Logger, format_duration, output_json


# Authority delegation: build.py is the single historical authority for runtime view generation.
from build import create_runtime_view


def check_runtime_view_l0(workspace_path: Path, architecture: str = None) -> dict:
    """Check L0: Physical Runtime View directory presence."""
    if architecture is None:
        try:
            architecture = CAAEnvironment().get_architecture() or "win_b64"
        except Exception:
            architecture = "win_b64"

    target_dir = Path(workspace_path) / architecture
    exists = target_dir.is_dir()
    return {
        "level": "L0",
        "status": "PASS" if exists else "FAIL",
        "check": "runtime_view_directory_present",
        "evidence": {
            "target_path": str(target_dir),
            "architecture": architecture,
            "exists": exists,
            "scope": "physical_directory_check",
        },
    }


def _verify_pe_file(path: Path, expected_arch: str = None) -> bool:
    """Verify that path is a structurally consistent Windows PE image.

    Checks:
    1. DOS header magic (MZ) and minimum file size
    2. e_lfanew pointer validity within file boundaries
    3. PE signature (PE\\0\\0)
    4. COFF File Header (20 bytes): 1 <= NumberOfSections <= 96, SizeOfOptionalHeader >= 2
    5. Machine architecture matching (win_b64 -> 0x8664 AMD64, intel_a -> 0x014c i386)
    6. Optional Header magic (0x020B PE32+ for 64-bit, 0x010B PE32 for 32-bit)
    7. SizeOfOptionalHeader fully contained within file boundaries
    8. SizeOfHeaders covers the DOS stub, PE headers and the whole Section Table,
       and does not exceed the file (R-03)
    9. Section Table (40 bytes per section) fully contained within file boundaries
    10. Section raw data pointers and sizes within file boundaries
    11. Each section's virtual range (VirtualAddress + max(VirtualSize, SizeOfRawData))
        stays inside SizeOfImage (R-03)

    Scope: this is a structural precheck, not loader acceptance. It cannot prove
    that Windows or CATIA can load the image; only an actual load can.
    """
    try:
        import struct

        file_size = path.stat().st_size
        if file_size < 90:
            return False

        with open(path, "rb") as f:
            header = f.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                return False

            pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
            if pe_offset <= 0 or pe_offset > file_size - 26:
                return False

            f.seek(pe_offset)
            pe_sig = f.read(4)
            if pe_sig != b"PE\x00\x00":
                return False

            coff_bytes = f.read(20)
            if len(coff_bytes) < 20:
                return False

            machine, num_sections, _, _, _, size_opt_hdr, characteristics = struct.unpack("<HHIIIHH", coff_bytes)
            # A loadable DLL needs at least one section and IMAGE_FILE_DLL (0x2000).
            # https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
            IMAGE_FILE_DLL = 0x2000
            if num_sections < 1 or num_sections > 96 or size_opt_hdr < 2:
                return False
            if (characteristics & IMAGE_FILE_DLL) == 0:
                return False

            # Check Optional Header boundary
            opt_hdr_offset = pe_offset + 4 + 20
            if opt_hdr_offset + size_opt_hdr > file_size:
                return False

            opt_hdr = f.read(size_opt_hdr)
            if len(opt_hdr) < size_opt_hdr or len(opt_hdr) < 2:
                return False
            opt_magic = struct.unpack_from("<H", opt_hdr, 0)[0]

            # Validate architecture consistency
            norm_arch = (expected_arch or "").lower()
            if norm_arch == "win_b64":
                if machine != 0x8664 or opt_magic != 0x020B:
                    return False
            elif norm_arch == "intel_a":
                if machine != 0x014C or opt_magic != 0x010B:
                    return False
            else:
                # General check: must be either AMD64 (PE32+) or i386 (PE32)
                if machine == 0x8664 and opt_magic != 0x020B:
                    return False
                elif machine == 0x014C and opt_magic != 0x010B:
                    return False
                elif machine not in (0x8664, 0x014C):
                    return False

            # PE32 standard optional header is 96 bytes; PE32+ is 112.
            # FileAlignment lives at offset 36 in both layouts.
            min_opt = 112 if opt_magic == 0x020B else 96
            if size_opt_hdr < min_opt or len(opt_hdr) < 40:
                return False
            file_alignment = struct.unpack_from("<I", opt_hdr, 36)[0]
            if file_alignment < 512 or file_alignment > 65536 or (file_alignment & (file_alignment - 1)) != 0:
                return False
            # Same offsets in PE32 and PE32+.
            # https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
            # SectionAlignment >= FileAlignment and a power of two.
            # If it is below the architecture page size, it must equal FileAlignment.
            # SizeOfImage is a multiple of SectionAlignment.
            # SizeOfHeaders is rounded up to a multiple of FileAlignment.
            if len(opt_hdr) < 64:
                return False
            section_alignment = struct.unpack_from("<I", opt_hdr, 32)[0]
            size_of_image = struct.unpack_from("<I", opt_hdr, 56)[0]
            size_of_headers = struct.unpack_from("<I", opt_hdr, 60)[0]
            if (
                section_alignment < file_alignment
                or section_alignment > 0x10000000
                or section_alignment == 0
                or (section_alignment & (section_alignment - 1)) != 0
            ):
                return False
            if section_alignment < 4096 and section_alignment != file_alignment:
                return False
            if size_of_image == 0 or (size_of_image % section_alignment) != 0:
                return False
            if size_of_headers == 0 or (size_of_headers % file_alignment) != 0:
                return False
            if size_of_headers > size_of_image:
                return False
            # SizeOfHeaders describes bytes that must exist in the file. A header
            # size beyond EOF is a self-inconsistent image, not a loadable one.
            if size_of_headers > file_size:
                return False

            # Validate Section Table boundary
            sec_table_offset = opt_hdr_offset + size_opt_hdr
            sec_table_size = num_sections * 40
            if sec_table_offset + sec_table_size > file_size:
                return False
            # SizeOfHeaders must cover the DOS stub, both headers and the whole
            # section table. Otherwise the table lives outside the mapped headers.
            if size_of_headers < sec_table_offset + sec_table_size:
                return False

            f.seek(sec_table_offset)
            for _ in range(num_sections):
                sec_bytes = f.read(40)
                if len(sec_bytes) < 40:
                    return False
                _, virt_size, virt_addr, raw_size, raw_ptr = struct.unpack("<8sIIII", sec_bytes[:24])
                if virt_addr % section_alignment != 0:
                    return False
                if raw_ptr > file_size:
                    return False
                if (raw_ptr % file_alignment) != 0 or (raw_size % file_alignment) != 0:
                    return False
                if raw_size > 0 and raw_ptr + raw_size > file_size:
                    return False
                # The loader maps sections into the image described by
                # SizeOfImage; a section reaching past it is inconsistent.
                mapped = virt_size if virt_size > raw_size else raw_size
                if mapped and virt_addr + mapped > size_of_image:
                    return False

            return True
    except Exception:
        return False


def _verify_dico_syntax(
    path: Path,
    target_module: str = None,
    target_component: str = None,
    target_interface: str = None,
) -> dict:
    """Verify official CATIA B28 .dico grammar and target binding.

    Official CATIA B28 rules:
    - Exactly three whitespace-separated tokens per non-empty, non-comment line:
      <component> <interface> <library>
    - Comment lines begin with ``#``; empty lines are ignored.
    - Shipped dictionaries (e.g. ``B28/.../code/dictionary/MechanicalCommands.dico``)
      contain 423 entries, every single one matching this grammar.
    - 6 of those 423 lines use a library token WITHOUT the ``lib`` prefix
      (e.g. ``CAAOsmAdd CATIBuild CAAOsmBuildUpdate``), so requiring ``lib``
      is not a valid rule and would reject real CAA output.
    - A fourth token, dots, or free text never appear in a shipped line.

    Target linkage: when ``target_module`` is given, the library token must
    equal ``lib<Module>`` or ``<Module>`` exactly. Substring matches do not
    bind the target, and an unrelated dictionary cannot stand in for it.

    When ``target_component`` or ``target_interface`` is provided, the entry
    must also match the specified component and interface tokens.

    Scope: this is a structural precheck of the line grammar, not a complete
    CATIA B28 dictionary parser and not proof that CATIA accepts the entry.
    """
    import re
    entries_count = 0
    syntax_errors = 0
    mentions_target = False
    target_registration_found = False

    expected_libs = set()
    if target_module:
        bare = target_module[:-2] if target_module.endswith(".m") else target_module
        if bare.lower().endswith(".dll"):
            bare = bare[:-4]
        elif bare.lower().endswith(".so"):
            bare = bare[:-3]
        # Both spellings are attested in shipped dictionaries.
        expected_libs = {"lib" + bare, bare}

    # Official .dico tokens are identifiers, not free text. Dots are .fact syntax, not .dico.
    id_pattern = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_idx, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                # Exactly three identifier tokens. One good line cannot launder the rest.
                if len(parts) == 3 and all(id_pattern.match(p) for p in parts):
                    entries_count += 1
                    lib_match = bool(expected_libs and parts[2] in expected_libs)
                    if lib_match:
                        mentions_target = True

                    comp_match = (target_component is None or parts[0] == target_component)
                    iface_match = (target_interface is None or parts[1] == target_interface)
                    lib_reg_match = (not expected_libs or lib_match)

                    if comp_match and iface_match and lib_reg_match:
                        target_registration_found = True
                else:
                    syntax_errors += 1
    except Exception:
        return {
            "valid_syntax": False,
            "entry_count": 0,
            "syntax_errors": 1,
            "mentions_target_module": False if target_module else None,
            "target_registration_found": False if (target_component or target_interface) else None,
        }

    return {
        "valid_syntax": (entries_count > 0 and syntax_errors == 0),
        "entry_count": entries_count,
        "syntax_errors": syntax_errors,
        "mentions_target_module": mentions_target if target_module else None,
        "target_registration_found": target_registration_found if (target_component or target_interface) else None,
    }


def check_runtime_view_l1(
    workspace_path: Path,
    architecture: str = None,
    target_module: str = None,
    target_framework: str = None,
    target_component: str = None,
    target_interface: str = None,
) -> dict:
    """Check L1 structural precheck of Runtime View assets.

    PASS means the target DLL has the required PE image fields and a matching
    three-token DICO line. It does not mean the Windows loader or CATIA accepted
    the file.

    When ``target_framework`` is specified, L1 strictly verifies that the dictionary
    named ``<target_framework>.dico`` exists and satisfies all syntax and target
    registration requirements. Other dictionaries cannot stand in for it.
    """
    l0 = check_runtime_view_l0(workspace_path, architecture)
    if l0["status"] != "PASS":
        return {
            "level": "L1",
            "status": "NOT_RUN",
            "check": "runtime_asset_integrity",
            "evidence": {
                "reason": "l0_directory_not_present",
                "target_module": target_module,
                "target_framework": target_framework,
            },
        }

    arch_dir = Path(l0["evidence"]["target_path"])
    bin_dir = arch_dir / "code" / "bin"
    dico_dir = arch_dir / "code" / "dictionary"
    msg_dir = arch_dir / "resources" / "msgcatalog"

    # Scan DLLs & verify PE format with architecture matching
    dll_files = []
    pe_valid_dlls = []
    if bin_dir.is_dir():
        dll_files = [f for f in bin_dir.glob("*.dll") if f.is_file() and f.stat().st_size > 0]
        pe_valid_dlls = [f for f in dll_files if _verify_pe_file(f, expected_arch=architecture)]

    # Scan DICOs & verify syntax
    dico_files = []
    dico_reports = []
    if dico_dir.is_dir():
        dico_files = [f for f in dico_dir.glob("*.dico") if f.is_file() and f.stat().st_size > 0]
        for df in dico_files:
            rep = _verify_dico_syntax(
                df,
                target_module=target_module,
                target_component=target_component,
                target_interface=target_interface,
            )
            dico_reports.append({"file": df.name, **rep})

    # Scan MsgCatalogs
    nls_files = []
    if msg_dir.is_dir():
        nls_files = [f for f in msg_dir.glob("*.CATNls") if f.is_file() and f.stat().st_size > 0]

    # Target module check if requested
    target_dll_found = False
    target_dll_valid_pe = False
    if target_module:
        norm_mod = target_module[:-2] if target_module.endswith(".m") else target_module
        expected_dll_name = f"{norm_mod}.dll".lower()
        for f in dll_files:
            if f.name.lower() == expected_dll_name:
                target_dll_found = True
                target_dll_valid_pe = _verify_pe_file(f, expected_arch=architecture)
                break

    target_dico_path = None
    target_dico_exists = None
    target_dico_bound = False
    target_registration_found = None

    if target_framework:
        target_dico_name = f"{target_framework}.dico"
        target_dico_path = dico_dir / target_dico_name
        target_dico_exists = target_dico_path.is_file() and target_dico_path.stat().st_size > 0
        if target_dico_exists:
            target_rep = _verify_dico_syntax(
                target_dico_path,
                target_module=target_module,
                target_component=target_component,
                target_interface=target_interface,
            )
            target_syntax_ok = target_rep.get("valid_syntax", False)
            if target_component or target_interface:
                target_reg_ok = bool(target_rep.get("target_registration_found", False))
                target_registration_found = target_reg_ok
            else:
                target_reg_ok = bool(target_rep.get("mentions_target_module", False))
                target_registration_found = target_rep.get("target_registration_found")
            target_dico_bound = bool(target_syntax_ok and target_reg_ok)
        else:
            target_dico_bound = False
            if target_component or target_interface:
                target_registration_found = False
    elif target_module:
        # Backward-compatible general scan: at least one valid DICO must explicitly mention the target module
        target_dico_bound = any(r.get("valid_syntax") and r.get("mentions_target_module") for r in dico_reports)
        if target_component or target_interface:
            target_registration_found = any(r.get("valid_syntax") and r.get("target_registration_found") for r in dico_reports)

    # General syntax validity of DICOs
    any_valid_dico = any(r["valid_syntax"] for r in dico_reports)

    # Evaluation
    # If target_module or target_framework is specified, it MUST have a valid PE DLL AND be declared in a valid DICO.
    if target_module or target_framework:
        passed = target_dll_found and target_dll_valid_pe and target_dico_bound
    else:
        passed = len(pe_valid_dlls) > 0 and any_valid_dico

    return {
        "level": "L1",
        "status": "PASS" if passed else "FAIL",
        "check": "runtime_asset_integrity",
        "evidence": {
            "target_module": target_module,
            "target_framework": target_framework,
            "target_dico_path": str(target_dico_path) if target_dico_path else None,
            "target_dico_exists": target_dico_exists,
            "target_dll_found": target_dll_found if target_module else None,
            "target_dll_valid_pe": target_dll_valid_pe if target_module else None,
            "target_dico_bound": target_dico_bound if (target_module or target_framework) else None,
            "target_registration_found": target_registration_found,
            "dll_count": len(dll_files),
            "pe_valid_dll_count": len(pe_valid_dlls),
            "dico_count": len(dico_files),
            "dico_reports": dico_reports,
            "nls_count": len(nls_files),
            "bin_dir_exists": bin_dir.is_dir(),
            "dico_dir_exists": dico_dir.is_dir(),
            "assets": {
                "dll": {
                    "count": len(dll_files),
                    "valid_pe_count": len(pe_valid_dlls),
                    "target_found": target_dll_found if target_module else None,
                    "target_valid_pe": target_dll_valid_pe if target_module else None,
                },
                "dico": {
                    "count": len(dico_files),
                    "valid_syntax": any_valid_dico,
                    "reports": dico_reports,
                },
            },
            "scope": "structural_precheck_not_loadability",
            "note": (
                "L1 PASS is a structural precheck of PE image fields and an exact "
                "3-token DICO binding. It is not Windows loader acceptance and not "
                "evidence that CATIA loaded the DLL."
            ),
        },
    }


def check_runtime_view(workspace_path: Path, target_module: str = None) -> dict:
    """
    Check Runtime View with layered evidence (L0 and L1).

    Args:
        workspace_path: Path to workspace directory
        target_module: Optional target module to verify in L1

    Returns:
        Dictionary with runtime view status and verification levels
    """
    logger = Logger("runtime_view.log")

    runtime_dirs = []

    # Check for common runtime view directories
    for arch in ["win_b64", "intel_a"]:
        runtime_path = workspace_path / arch
        if runtime_path.exists():
            runtime_dirs.append(
                {"architecture": arch, "path": str(runtime_path), "exists": True}
            )

    try:
        configured_arch = CAAEnvironment().get_architecture() or "win_b64"
    except Exception:
        configured_arch = "win_b64"

    l0_res = check_runtime_view_l0(workspace_path, configured_arch)
    l1_res = check_runtime_view_l1(workspace_path, configured_arch, target_module=target_module)

    levels = {
        "L0": l0_res,
        "L1": l1_res,
        "L2": {"level": "L2", "status": "NOT_RUN", "check": "target_process_identity", "evidence": {"reason": "static_probe_only"}},
        "L3": {"level": "L3", "status": "NOT_RUN", "check": "module_loaded_exact_path", "evidence": {"reason": "static_probe_only"}},
        "L4": {"level": "L4", "status": "NOT_RUN", "check": "addin_runtime_registration", "evidence": {"reason": "static_probe_only"}},
        "L5": {"level": "L5", "status": "NOT_RUN", "check": "functional_verification", "evidence": {"reason": "static_probe_only"}},
    }

    highest = "L1" if l1_res["status"] == "PASS" else ("L0" if l0_res["status"] == "PASS" else "NONE")

    if runtime_dirs:
        res = {
            "status": "found",
            "message": f"Found {len(runtime_dirs)} Runtime View(s)",
            "runtime_views": runtime_dirs,
            "runtime_view_present": True,
            "runtime_view_mounted": True,  # legacy alias
            "runtime_verification": {
                "highest_verified_level": highest,
                "levels": levels,
            },
        }
        raw_snapshot = dict(res)
        if len(runtime_dirs) == 1:
            target_arch = runtime_dirs[0]["architecture"]
            target_path = runtime_dirs[0]["path"]
            arch_matched = (target_arch == configured_arch)
        else:
            target_arch = [d["architecture"] for d in runtime_dirs]
            target_path = [d["path"] for d in runtime_dirs]
            arch_matched = any(d["architecture"] == configured_arch for d in runtime_dirs)

        res["execution"] = {
            "status": "completed",
            "action_result": "found",
            "raw": raw_snapshot,
        }
        res["verification"] = {
            "status": "passed",
            "check": "runtime_candidate_path_exists",
            "evidence": {
                "target_architecture": target_arch,
                "target_path": target_path,
                "configured_architecture": configured_arch,
                "architecture_matched": arch_matched,
                "exists": True,
                "instance_scope": "path_existence_predicate_only",
                "levels": levels,
            },
        }
        return res
    else:
        res = {
            "status": "not_found",
            "message": "No Runtime View found",
            "runtime_views": [],
            "runtime_view_present": False,
            "runtime_view_mounted": False,  # legacy alias
            "runtime_verification": {
                "highest_verified_level": "NONE",
                "levels": levels,
            },
        }
        raw_snapshot = dict(res)
        res["execution"] = {
            "status": "completed",
            "action_result": "not_found",
            "raw": raw_snapshot,
        }
        res["verification"] = {
            "status": "not_run",
            "check": "none",
            "evidence": {
                "reason": "no_candidate_path_exists",
                "configured_architecture": configured_arch,
                "architecture_matched": False,
                "exists": False,
                "levels": levels,
            },
        }
        return res


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Create or check CATIA Runtime View",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runtime_view.py                     # Check current directory
  python runtime_view.py --create            # Create runtime view
  python runtime_view.py --create --overwrite # Recreate runtime view
  python runtime_view.py D:\\workspace --create # Create in specific workspace
        """,
    )

    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Path to workspace directory (default: current directory)",
    )

    parser.add_argument("--create", action="store_true", help="Create Runtime View")

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Runtime View (requires --create)",
    )

    parser.add_argument(
        "--architecture",
        default=None,
        choices=["win_b64", "intel_a"],
        help="Target architecture (auto-detect if not specified)",
    )

    args = parser.parse_args()

    # Resolve workspace path
    workspace_path = Path(args.workspace).resolve()

    # Execute command
    if args.create:
        result = create_runtime_view(
            workspace_path, overwrite=args.overwrite, architecture=args.architecture
        )
    else:
        result = check_runtime_view(workspace_path)

    # Output JSON
    exit_code = 0 if result["status"] in ["success", "found", "exists"] else 1
    output_json(result, exit_code=exit_code)


if __name__ == "__main__":
    main()
