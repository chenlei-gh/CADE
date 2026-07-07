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
        """Auto-detect CATIA installation and write config"""
        import os as _os

        # Scan for CATIA in standard locations
        search_paths = []
        for drive in ["C:\\", "D:\\"]:
            for base in ["Program Files", "Program Files (x86)"]:
                ds_dir = _os.path.join(drive, base, "Dassault Systemes")
                if _os.path.isdir(ds_dir):
                    for entry in _os.listdir(ds_dir):
                        full = _os.path.join(ds_dir, entry)
                        if _os.path.isdir(full) and entry.startswith("B"):
                            search_paths.append(full)

        if not search_paths:
            return False

        # Use the first found
        catia_install = search_paths[0]
        catia_version = _os.path.basename(catia_install)

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
        version = self.config.get("CATIA_VERSION", "B28")
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

    def build_time_command(
        self, workspace_path: str, mkmk_options: str = "-u"
    ) -> Tuple[list, str]:
        """
        Build the correct cmd.exe command to run mkmk with full Build Time environment.

        This replicates the VS Build Time Prompt behavior:
          1. tck_init.bat  → basic TCK variables
          2. mkinit.bat    → full Mkmk environment (detects VS, Windows Kit, etc.)
          3. mkmkM.exe     → actual compilation

        Args:
            workspace_path: Path to workspace or module directory
            mkmk_options: mkmk command line options (e.g., "-u", "-g", "-a")

        Returns:
            Tuple of (command_list, display_string)
        """
        mkinit = self.get_mkinit_bat()
        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path) or "win_b64"
        code_bin = catia_path / arch / "code" / "bin"

        if not mkinit or not mkinit.exists():
            raise FileNotFoundError(f"mkinit.bat not found. Expected at: {mkinit}")

        # Detect the correct mkmk executable name (mkmkM.exe or mkmk.exe)
        mkmk_path = self.get_mkmk_path()
        mkmk_name = mkmk_path.name if mkmk_path else "mkmkM.exe"

        # Build the cmd command string
        # The full environment can only be initialized inside cmd.exe
        code_command = catia_path / arch / "code" / "command"
        cmd_str = (
            f'call "{mkinit}" > NUL 2>&1 && '
            f"set PATH={code_bin};{code_command};%PATH% && "
            f'cd /d "{workspace_path}" && '
            f"{mkmk_name} {mkmk_options}"
        )

        return ["cmd", "/c", cmd_str], cmd_str

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
        mkinit = self.get_mkinit_bat()
        catia_path = Path(self.config.get("CATIA_INSTALL", ""))
        arch = self._detect_architecture(catia_path) or "win_b64"
        code_bin = catia_path / arch / "code" / "bin"
        code_command = catia_path / arch / "code" / "command"

        if not mkinit or not mkinit.exists():
            raise FileNotFoundError(f"mkinit.bat not found")

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
                f'call "{mkinit}" > NUL 2>&1 && '
                f"set PATH={code_bin};{code_command};%PATH% && "
                f'cd /d "{workspace_path}" && '
                f"{resolved_cmd}"
            )
        else:
            cmd_str = (
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
