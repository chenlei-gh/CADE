"""
CATIA CAA Build Time Environment Initializer
============================================
Purpose: Initialize Build Time Prompt environment variables
Called by: All other skills (build.py, run.py, etc.)
Output: Dictionary of environment variables

Build Time Prompt 调用链 (CATIA V5R28/B28):
  cmd.exe
    → tck_init.bat     (基础 TCK 环境变量)
    → mkinit.bat        (完整 Mkmk 环境, 检测 VS/Windows Kit)
    → mkmkM.exe         (编译)

Run Time Prompt 调用链:
  cmd.exe
    → mkinit.bat        (环境初始化)
    → mkrun.bat         (设置运行时变量)
    → mkrunM.exe        (启动器)
    → CNEXT.exe         (CATIA)
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


class CAAEnvironment:
    """Manages CATIA CAA Build Time environment"""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize CAA environment

        Args:
            config_file: Path to caa_env_config.txt (auto-detect if None)
        """
        self.skill_root = Path(__file__).parent.parent
        self.config_file = (
            config_file or self.skill_root / "config" / "caa_env_config.txt"
        )
        self.config = {}
        self.env = os.environ.copy()
        self._version = None
        self._rules = None

    def load_config(self) -> bool:
        """Load configuration, auto-detect if missing"""
        if not Path(self.config_file).exists():
            if not self._auto_detect():
                print(
                    f"ERROR: Cannot detect CATIA. Set CATIA_INSTALL in {self.config_file}",
                    file=sys.stderr,
                )
                return False

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        self.config[key.strip()] = value.strip()
            return True
        except Exception as e:
            print(f"ERROR: Failed to read config: {e}", file=sys.stderr)
            return False

    def _auto_detect(self) -> bool:
        """Auto-detect CATIA installation and write config using new detector"""
        import os as _os

        # Use new CATIA detector (no hardcoded paths)
        try:
            from ..tools.catia_detector import detect_catia_installations
        except ImportError:
            try:
                sys.path.insert(0, str(self.skill_root / "tools"))
                from catia_detector import detect_catia_installations
            except ImportError:
                # Fallback: return False if detector not available
                return False

        installations = detect_catia_installations(verbose=False)
        if not installations:
            return False

        # Use the newest version (first in sorted list)
        selected = installations[0]
        catia_install = str(selected.root_path)
        catia_version = selected.version

        # Detect architecture
        arch = "win_b64"
        arch_path = _os.path.join(catia_install, arch, "code", "bin")
        if not _os.path.isdir(arch_path):
            arch = "intel_a"
            arch_path = _os.path.join(catia_install, arch, "code", "bin")

        # Verify mkmk exists
        mkmk_path = None
        for name in ["mkmkM.exe", "mkmk.exe"]:
            candidate = _os.path.join(arch_path, name)
            if _os.path.exists(candidate):
                mkmk_path = candidate
                break

        if not mkmk_path:
            return False

        # Write config
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        workspace = str(self.skill_root.parent.parent)  # workspace root

        lines = [
            "# CADE Auto-Detected Configuration",
            f"# Generated: auto-detect",
            "",
            f"CATIA_INSTALL={catia_install}",
            f"CATIA_VERSION={catia_version}",
            f"CAA_INSTALL={catia_install}",
            f"WORKSPACE={workspace}",
            "",
            "# Build Tools",
            f"TCK_INIT={catia_install}\\{arch}\\code\\command\\tck_init.bat",
            f"MKMK={mkmk_path}",
            "",
            "# Detection",
            "DETECTED_BY=auto_detect",
        ]
        self.config_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"[CADE] Auto-detected CATIA: {catia_install}", file=sys.stderr)
        print(f"[CADE] Config written: {self.config_file}", file=sys.stderr)

        return True

    def initialize(self, workspace_path: str = None) -> Dict[str, str]:
        """
        Initialize Run Time environment variables for CATIA execution.

        Args:
            workspace_path: Optional workspace path to use Runtime View from.
                          If provided, will add Runtime View paths to environment.
        """
        if not self.load_config():
            return {}

        catia_path = self.config.get("CATIA_INSTALL", "")
        if not catia_path:
            print("ERROR: CATIA_INSTALL not found in config", file=sys.stderr)
            return {}

        catia_path = Path(catia_path)
        if not catia_path.exists():
            print(f"ERROR: CATIA path does not exist: {catia_path}", file=sys.stderr)
            return {}

        arch = self._detect_architecture(catia_path)
        if not arch:
            print("ERROR: Could not detect CATIA architecture", file=sys.stderr)
            return {}

        # Base CATIA paths
        code_bin = catia_path / arch / "code" / "bin"

        self.env["CATInstallPath"] = str(catia_path)
        self.env["CATDictionaryPath"] = str(
            catia_path / "CNext" / "code" / "dictionary"
        )
        self.env["CATGraphicPath"] = str(catia_path / "CNext" / "resources" / "graphic")
        self.env["CATMsgCatalogPath"] = str(
            catia_path / "CNext" / "resources" / "msgcatalog"
        )
        self.env["CATReffilesPath"] = str(catia_path / "CNext" / "reffiles")

        # Set up PATH - Runtime View first, then CATIA
        path_components = []

        # Add Runtime View paths if workspace is provided
        if workspace_path:
            workspace_path = Path(workspace_path)
            runtime_view = workspace_path / arch

            if runtime_view.exists():
                # Add Runtime View code/bin to PATH (highest priority)
                runtime_bin = runtime_view / "code" / "bin"
                if runtime_bin.exists():
                    path_components.append(str(runtime_bin))
                    print(f"Using Runtime View: {runtime_view}", file=sys.stderr)

                # Set CATDLLPath to include Runtime View
                runtime_code = runtime_view / "code"
                if runtime_code.exists():
                    self.env["CATDLLPath"] = str(runtime_code)

        # Add CATIA code/bin
        if code_bin.exists():
            path_components.append(str(code_bin))

        # Add existing PATH
        if self.env.get("PATH"):
            path_components.append(self.env["PATH"])

        self.env["PATH"] = os.pathsep.join(path_components)

        return self.env

    def _detect_architecture(self, catia_path: Path) -> Optional[str]:
        """Detect CATIA architecture (win_b64 or intel_a)"""
        for arch in ["win_b64", "intel_a"]:
            arch_path = catia_path / arch / "code" / "bin"
            if arch_path.exists():
                return arch
        return None

    def _find_vcvars(self) -> Path:
        """Find vcvarsall.bat for VS compiler environment (P2-006 fix).

        Uses environment variables before falling back to hardcoded paths.
        Supports VS 2012 (VC11) through VS 2022.
        Raises FileNotFoundError if not found.
        """
        import os

        # Use environment variables for program files (supports non-C drives)
        prog_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        prog = os.environ.get("ProgramFiles", r"C:\Program Files")

        candidates = [
            # VS 2012 (VC11) — required by CATIA B28
            Path(prog_x86) / "Microsoft Visual Studio 11.0" / "VC" / "vcvarsall.bat",
            Path(prog) / "Microsoft Visual Studio 11.0" / "VC" / "vcvarsall.bat",
            # VS 2013 (VC12)
            Path(prog_x86) / "Microsoft Visual Studio 12.0" / "VC" / "vcvarsall.bat",
            Path(prog) / "Microsoft Visual Studio 12.0" / "VC" / "vcvarsall.bat",
        ]

        # Check common VS 2012/2013 locations first
        for p in candidates:
            if p.exists():
                return p

        # Try vswhere.exe for VS 2017+ (installed with VS Build Tools)
        vswhere = Path(prog_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if vswhere.exists():
            try:
                import subprocess
                result = subprocess.run(
                    [str(vswhere), "-latest", "-property", "installationPath"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    vs_path = Path(result.stdout.strip())
                    vcvars = vs_path / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
                    if vcvars.exists():
                        return vcvars
            except Exception:
                pass

        # Fallback: scan known version patterns on both program file roots
        for ver in ["14.0", "2017", "2019", "2022"]:
            for base in [prog_x86, prog]:
                base_p = Path(base) / "Microsoft Visual Studio"
                if ver in ("2017", "2019", "2022"):
                    p = base_p / ver / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
                else:
                    p = base_p / ver / "VC" / "vcvarsall.bat"
                if p.exists():
                    return p

        raise FileNotFoundError(
            f"vcvarsall.bat not found. Searched: {prog_x86}, {prog}. "
            f"Install Visual Studio 2012 (VC11) or newer with C++ tools."
        )

    def get_mkmk_path(self) -> Optional[Path]:
        """Get full path to mkmk executable"""
        if not self.config:
            self.load_config()

        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path)
        if arch:
            for mkmk_name in ["mkmkM.exe", "mkmk.exe"]:
                mkmk = catia_path / arch / "code" / "bin" / mkmk_name
                if mkmk.exists():
                    return mkmk
        return None

    def get_cnext_path(self) -> Optional[Path]:
        """Get full path to CNEXT.exe (for Runtime)"""
        if not self.config:
            self.load_config()

        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path)
        if arch:
            cnext = catia_path / arch / "code" / "bin" / "CNEXT.exe"
            if cnext.exists():
                return cnext
        return None

    def get_catstart_path(self) -> Optional[Path]:
        """Get full path to CATSTART.exe (recommended for normal startup)"""
        if not self.config:
            self.load_config()

        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path)
        if arch:
            catstart = catia_path / arch / "code" / "bin" / "CATSTART.exe"
            if catstart.exists():
                return catstart
        return None

    def get_mkinit_bat(self) -> Optional[Path]:
        """Get path to mkinit.bat (the proper Build Time entry point)"""
        if not self.config:
            self.load_config()

        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path)
        if arch:
            mkinit = catia_path / arch / "code" / "command" / "mkinit.bat"
            if mkinit.exists():
                return mkinit
        return None

    def get_architecture(self) -> str:
        """Get detected architecture (public accessor)"""
        if not self.config:
            self.load_config()
        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        return self._detect_architecture(catia_path) or "win_b64"

    def get_catenv_dir(self) -> str:
        """Auto-detect CATEnv directory from config or known locations"""
        if not self.config:
            self.load_config()
        if self.config.get("CATENV_DIR"):
            p = Path(self.config["CATENV_DIR"])
            if p.exists():
                return str(p)
        candidates = [
            Path(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"))
            / "DassaultSystemes"
            / "CATEnv",
            Path(os.environ.get("APPDATA", "")) / "DassaultSystemes" / "CATEnv",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return r"C:\ProgramData\DassaultSystemes\CATEnv"

    def get_available_envs(self) -> list:
        """List available CATIA environments"""
        if not self.config:
            self.load_config()
        envs = []
        catenv_dir = Path(self.get_catenv_dir())
        if catenv_dir.exists():
            for f in catenv_dir.glob("*.xml"):
                envs.append(f.stem)
            for f in catenv_dir.glob("*.CATEnv"):
                envs.append(f.stem)
        user_env = Path(os.environ.get("APPDATA", "")) / "DassaultSystemes" / "CATEnv"
        if user_env.exists():
            for f in user_env.glob("*.xml"):
                if f.stem not in envs:
                    envs.append(f.stem)
        return envs

    def get_default_env(self) -> str:
        """Get default CATIA environment from config or auto-detect"""
        if not self.config:
            self.load_config()
        if self.config.get("CATIA_ENV"):
            return self.config["CATIA_ENV"]
        envs = self.get_available_envs()
        if envs:
            for env in envs:
                if env.upper().startswith("CATIA") and "RADE" not in env.upper():
                    return env
            return envs[0]

        # No .edu found, use detected version from config (auto-detect uses newest)
        version = self.config.get(
            "CATIA_VERSION", "B30"
        )  # Default to B30 instead of B28
        return f"CATIA_P3.V5-6R2018.{version}"

    def get_info(self) -> Dict[str, str]:
        """Get environment information for debugging"""
        if not self.config:
            self.load_config()

        info = {
            "catia_install": self.config.get("CATIA_INSTALL", "N/A"),
            "catia_version": self.config.get("CATIA_VERSION", "N/A"),
            "workspace": self.config.get("WORKSPACE", "N/A"),
            "mkmk_path": str(self.get_mkmk_path() or "N/A"),
            "cnext_path": str(self.get_cnext_path() or "N/A"),
            "mkinit_bat": str(self.get_mkinit_bat() or "N/A"),
            "catenv_dir": self.get_catenv_dir(),
            "default_env": self.get_default_env(),
            "available_envs": str(self.get_available_envs()),
        }

        # Add version info
        ver = self.detect_caa_version()
        if ver:
            info["caa_version_label"] = ver.label
            info["caa_platform"] = ver.platform.value
            info["caa_prefer_tie"] = str(not ver.boa_default)

        return info

    # ── Version Detection ───────────────────────────────────────

    def detect_caa_version(self):
        """Detect and cache the CAA version"""
        if self._version:
            return self._version

        from version_strategy import detect_version

        if not self.config:
            self.load_config()

        ver_str = self.config.get("CATIA_VERSION", "")
        install = self.config.get("CATIA_INSTALL", "")

        self._version = detect_version(
            catia_install=install,
            version_str=ver_str,
        )
        return self._version

    def get_version_rules(self):
        """Get version-specific rules"""
        if self._rules:
            return self._rules

        from version_strategy import get_rules

        ver = self.detect_caa_version()
        if ver:
            self._rules = get_rules(ver)
        return self._rules

    def _resolve_rade_settings(self) -> Dict[str, str]:
        """
        Resolve RADE license settings from CATEnv files.

        When tck_profile fails (TCK not registered), this fallback reads
        the CAA_RADE CATEnv file and extracts the variables mkmk needs
        for RADE license validation.

        Returns:
            Dict of env vars to set in the build .bat (keys use %VAR% syntax
            for cmd.exe expansion, e.g. 'APPDATA').
        """
        catenv_dir = Path(self.get_catenv_dir())
        user_catenv = Path(os.environ.get("APPDATA", "")) / "DassaultSystemes" / "CATEnv"
        settings = {}

        # Priority: RADE specific env file first, then CATIA env as fallback
        candidates = [
            catenv_dir / "CAA_RADE.V5-6R2018.B28.txt",
            catenv_dir / "CATIA_P3.V5-6R2018.B28.txt",
        ]
        # Also check user CATEnv
        if user_catenv.exists():
            for f in user_catenv.glob("*.txt"):
                candidates.append(f)

        for fpath in candidates:
            if not fpath.exists():
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("!") or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, _, value = line.partition("=")
                            key = key.strip()
                            value = value.strip()
                            if key in ("CATUserSettingPath", "CATReferenceSettingPath"):
                                settings[key] = value
                            elif key == "RADECATSettingPath" and key not in settings:
                                settings[key] = value
            except Exception:
                continue

            # Found at least CATUserSettingPath, stop scanning
            if "CATUserSettingPath" in settings:
                break

        # If RADE file exists, RADECATSettingPath mirrors CATUserSettingPath
        if "CATUserSettingPath" in settings and "RADECATSettingPath" not in settings:
            settings["RADECATSettingPath"] = settings["CATUserSettingPath"]

        return settings

    def _generate_catenv_fallback_bat(self) -> str:
        """
        Generate .bat commands that set RADE license variables from CATEnv fallback.

        CSIDL_* paths are resolved at cmd.exe runtime via %APPDATA%, %LOCALAPPDATA% etc.
        Returns empty string if CATEnv files cannot be read.
        """
        settings = self._resolve_rade_settings()
        if not settings or "CATUserSettingPath" not in settings:
            return ""

        lines = ["echo [CADE] tck_profile failed, using CATEnv fallback for RADE license"]
        appdata = os.environ.get("APPDATA", "%APPDATA%")
        localappdata = os.environ.get("LOCALAPPDATA", "%LOCALAPPDATA%")
        userprofile = os.environ.get("USERPROFILE", "%USERPROFILE%")

        for key, value in settings.items():
            # Resolve CSIDL_* macros to actual paths
            resolved = value
            resolved = resolved.replace("CSIDL_APPDATA", appdata)
            resolved = resolved.replace("CSIDL_LOCAL_APPDATA", localappdata)
            resolved = resolved.replace("CSIDL_PERSONAL", f"{userprofile}\\Documents")
            lines.append(f"set {key}={resolved}")

        return "\r\n".join(lines) + "\r\n"

    def build_time_command(
        self, workspace_path: str, mkmk_options: str = "-u"
    ) -> Tuple[list, str]:
        """
        Build the correct cmd.exe command to run mkmk with full Build Time environment.

        This replicates the VS Build Time Prompt behavior:
          1. tck_init.bat     → basic TCK variables
          2. tck_profile.bat  → RADE license initialization (with workspace TCK lookup)
          3. [FALLBACK]       → if TCK not registered, load CATEnv settings directly
          4. mkinit.bat       → full Mkmk environment (detects VS, Windows Kit, etc.)
          5. mkGetPreq        → link workspace prerequisites
          6. mkmk             → compilation

        The fallback at step 3 makes build.py robust even when TCK is not configured,
        by reading RADE license settings from CATEnv files (CAA_RADE.V5-6R2018.B28.txt).

        Args:
            workspace_path: Path to workspace or module directory
            mkmk_options: mkmk command line options (e.g., "-u", "-g", "-a")

        Returns:
            Tuple of (command_list, display_string)
        """
        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path) or "win_b64"
        code_bin = catia_path / arch / "code" / "bin"
        code_command = catia_path / arch / "code" / "command"

        mkinit = code_command / "mkinit.bat"
        tck_init = code_command / "tck_init.bat"
        tck_profile = catia_path / arch / "TCK" / "command" / "tck_profile.bat"

        if not mkinit.exists():
            raise FileNotFoundError(f"mkinit.bat not found. Expected at: {mkinit}")

        # Generate CATEnv fallback block (used if tck_profile fails)
        fallback_block = self._generate_catenv_fallback_bat()

        # Build .bat content with proper error handling and fallback
        # tck_profile may fail if TCK not registered — we fall back to CATEnv.
        lines = []
        lines.append("@echo off")
        lines.append(f'call "{tck_init}" > NUL 2>&1')

        if tck_profile.exists():
            # Try tck_profile with workspace path (helps TCK locate the workspace TCK)
            lines.append(
                f'call "{tck_profile}" "{workspace_path}" > NUL 2>&1'
            )
            lines.append("set _TCKPROFILE_RC=%ERRORLEVEL%")
            if fallback_block:
                lines.append("if %_TCKPROFILE_RC% neq 0 (")
                for fb_line in fallback_block.strip().split("\r\n"):
                    if fb_line.strip():
                        lines.append(f"    {fb_line.strip()}")
                lines.append(")")
        elif fallback_block:
            lines.append("echo [CADE] tck_profile.bat missing, using CATEnv fallback")
            for fb_line in fallback_block.strip().split("\r\n"):
                if fb_line.strip():
                    lines.append(fb_line.strip())

        lines.append(f'call "{mkinit}" > NUL 2>&1')
        lines.append(f"set PATH={code_bin};{code_command};%PATH%")
        lines.append(f'cd /d "{workspace_path}"')
        lines.append(f'call mkGetPreq -p "{catia_path};" > NUL 2>&1')
        # mkmk output goes to stdout — build.py will capture it
        lines.append(f"mkmk {mkmk_options}")

        bat_content = "\r\n".join(lines) + "\r\n"

        # Write to temp .bat for cmd.exe execution (P2-008 fix)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".bat", prefix="cade_build_", delete=False, mode="w", encoding="ascii") as f:
            f.write(bat_content)
            self._build_bat = Path(f.name)

        display = f"tck_init → tck_profile → [fallback if TCK missing] → mkinit → mkmk {mkmk_options}"
        return ["cmd", "/c", str(self._build_bat)], display

    def run_command(self, command: str, workspace_path: str = None) -> Tuple[list, str]:
        """
        Build a generic Build Time command (not just mkmk).

        Usable for: mkCreateRuntimeView, mkwhereami, mkreadcpd, mkrmfw,
        mkmkdepend, mkGetPreq, etc.

        Auto-detects whether the command needs a .bat wrapper in code/command
        or an .exe with M suffix in code/bin.

        Args:
            command: Full command with args (e.g., "mkCreateRuntimeView", "mkwhereami")
            workspace_path: Optional workspace directory to cd into

        Returns:
            Tuple of (command_list, display_string)
        """
        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path) or "win_b64"
        code_bin = catia_path / arch / "code" / "bin"
        code_command = catia_path / arch / "code" / "command"

        mkinit = code_command / "mkinit.bat"
        tck_init = code_command / "tck_init.bat"
        tck_profile = catia_path / arch / "TCK" / "command" / "tck_profile.bat"
        vcvars = self._find_vcvars()

        # Auto-detect: prefer .bat in code/command, fallback to .exe with M suffix
        cmd_name, cmd_args = (
            command.split(maxsplit=1) if " " in command else (command, "")
        )
        bat_path = code_command / f"{cmd_name}.bat"
        exe_path = code_bin / f"{cmd_name}.exe"
        exeM_path = code_bin / f"{cmd_name}M.exe"

        if bat_path.exists():
            resolved_cmd = command  # use as-is, .bat handles it
        elif exe_path.exists():
            resolved_cmd = command
        elif exeM_path.exists():
            resolved_cmd = f"{cmd_name}M {cmd_args}".strip()
        else:
            resolved_cmd = command  # best effort

        if workspace_path:
            cmd_str = (
                f'call "{vcvars}" amd64 > NUL 2>&1 && '
                f'call "{tck_init}" > NUL 2>&1 && '
                f'call "{tck_profile}" > NUL 2>&1 && '
                f'call "{mkinit}" > NUL 2>&1 && '
                f"set PATH={code_bin};{code_command};%PATH% && "
                f'cd /d "{workspace_path}" && '
                f"{resolved_cmd}"
            )
        else:
            cmd_str = (
                f'call "{vcvars}" amd64 > NUL 2>&1 && '
                f'call "{tck_init}" > NUL 2>&1 && '
                f'call "{tck_profile}" > NUL 2>&1 && '
                f'call "{mkinit}" > NUL 2>&1 && '
                f"set PATH={code_bin};{code_command};%PATH% && "
                f"{resolved_cmd}"
            )

        return ["cmd", "/c", cmd_str], cmd_str


def get_build_env() -> Dict[str, str]:
    """Quick helper to get Build Time environment (Python-side only)"""
    caa_env = CAAEnvironment()
    return caa_env.initialize()


def get_build_command(workspace_path: str, options: str = "-u") -> Tuple[list, str]:
    """Quick helper to get the full Build Time command"""
    caa_env = CAAEnvironment()
    return caa_env.build_time_command(workspace_path, options)


if __name__ == "__main__":
    import json

    print("Initializing CAA Environment...")
    env = CAAEnvironment()

    if env.initialize():
        print()
        print("[OK] Environment initialized successfully")
        print()
        info = env.get_info()
        print(json.dumps(info, indent=2))
    else:
        print()
        print("[FAIL] Failed to initialize environment")
        sys.exit(1)
