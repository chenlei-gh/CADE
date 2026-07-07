"""
CATIA CAA Version Strategy Engine
==================================
Version-aware rules for code generation, diagnostics, and build.

CATIA versions have significant differences:
  - R19-R24: V5 classic, BOA preferred
  - R25-R28: V5 late, TIE preferred, some API changes
  - 3DEXPERIENCE R201x+: V6 platform, different framework structure

This module detects the target version and provides version-specific
rules for naming, interface patterns, build options, and more.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

# ─── Version Detection ───────────────────────────────────────────


class Platform(Enum):
    V5 = "V5"
    V6 = "V6"  # 3DEXPERIENCE


@dataclass
class CAAVersion:
    """Represents a specific CATIA/CAA version"""

    name: str  # e.g., "R28", "R2019x"
    platform: Platform
    major: int  # e.g., 28
    boa_default: bool = True  # BOA vs TIE preference
    cnext_exe: str = "CNEXT.exe"  # Executable name
    mkmk_exe: str = "mkmkM.exe"  # Compiler name
    framework_suffix: str = ".edu"  # Framework directory suffix
    module_suffix: str = ".m"  # Module directory suffix

    @property
    def label(self) -> str:
        return f"CATIA {self.platform.value} {self.name}"


# Known versions
KNOWN_VERSIONS = [
    CAAVersion("R19", Platform.V5, 19),
    CAAVersion("R20", Platform.V5, 20),
    CAAVersion("R21", Platform.V5, 21),
    CAAVersion("R24", Platform.V5, 24),
    CAAVersion("R25", Platform.V5, 25, boa_default=False),
    CAAVersion("R26", Platform.V5, 26, boa_default=False),
    CAAVersion("R27", Platform.V5, 27, boa_default=False),
    CAAVersion("R28", Platform.V5, 28, boa_default=False),
    CAAVersion("B28", Platform.V5, 28, boa_default=False),  # alias
    CAAVersion(
        "R2019x",
        Platform.V6,
        2019,
        boa_default=False,
        framework_suffix=".fw",
        module_suffix=".mod",
    ),
    CAAVersion(
        "R2020x",
        Platform.V6,
        2020,
        boa_default=False,
        framework_suffix=".fw",
        module_suffix=".mod",
    ),
    CAAVersion(
        "R2021x",
        Platform.V6,
        2021,
        boa_default=False,
        framework_suffix=".fw",
        module_suffix=".mod",
    ),
    CAAVersion(
        "R2022x",
        Platform.V6,
        2022,
        boa_default=False,
        framework_suffix=".fw",
        module_suffix=".mod",
    ),
]


# ─── Version Detection ───────────────────────────────────────────


def detect_version(
    catia_install: str = None, version_str: str = None
) -> Optional[CAAVersion]:
    """
    Detect CATIA version from install path or explicit string.

    Args:
        catia_install: Path to CATIA installation (e.g., "C:/.../B28")
        version_str: Explicit version string (e.g., "R28", "R2019x")
    """
    if version_str:
        for v in KNOWN_VERSIONS:
            if v.name.upper() == version_str.upper():
                return v

    if catia_install:
        path = Path(catia_install)
        # Try last path component as version
        last = path.name.upper()
        for v in KNOWN_VERSIONS:
            if v.name.upper() == last:
                return v
            if v.name.upper() in str(path).upper():
                return v

    return None


# ─── Version-Aware Rules ─────────────────────────────────────────


@dataclass
class VersionRules:
    """Version-specific rules for code generation and validation"""

    version: CAAVersion

    # Interface patterns
    interface_prefix: str = "I"  # e.g., IMyInterface
    tielib_prefix: str = "TIE_"  # e.g., TIE_IMyInterface

    # Component patterns
    prefer_tie: bool = False  # TIE over BOA for R25+
    boa_macro: str = "CATDeclareBOA"  # BOA declaration macro
    tie_macro: str = "CATDeclareTIE"  # TIE declaration macro

    # Dictionary format
    dict_separator: str = "  "  # Separator in .dico entries
    dict_comment_char: str = "#"

    # Imakefile
    imake_ext: str = ".mk"
    link_with_keyword: str = "LINK_WITH"

    # Naming conventions
    header_ext: str = ".h"
    source_ext: str = ".cpp"
    idl_ext: str = ".idl"

    def component_declaration(self, name: str) -> str:
        """Generate the component declaration macro"""
        if self.prefer_tie:
            return f"{self.tie_macro}({name})"
        return f"{self.boa_macro}({name})"

    def tie_include(self, interface_name: str) -> str:
        """Generate the TIE include line"""
        return f'#include "{self.tielib_prefix}{interface_name}{self.header_ext}"'

    @property
    def dictionary_format_hint(self) -> str:
        return f"# Format: ComponentName{self.dict_separator}BaseClass{self.dict_separator}libModule"

    def is_valid_interface_name(self, name: str) -> bool:
        return name.startswith(self.interface_prefix)

    def is_valid_module_name(self, name: str) -> bool:
        return name.endswith(self.version.module_suffix)

    def is_valid_framework_name(self, name: str) -> bool:
        return name.endswith(self.version.framework_suffix)


# ─── Rule Factory ────────────────────────────────────────────────


def get_rules(version: CAAVersion) -> VersionRules:
    """Get version-specific rules for a given CATIA version"""
    rules = VersionRules(version=version)

    if version.platform == Platform.V5:
        if version.major < 25:
            # R19-R24: BOA preferred
            rules.prefer_tie = False
            rules.boa_macro = "CATDeclareBOA"
        else:
            # R25-R28: TIE preferred
            rules.prefer_tie = True
            rules.boa_macro = "CATDeclareClass"
            rules.tie_macro = "CATDeclareTIE"

    elif version.platform == Platform.V6:
        # 3DEXPERIENCE
        rules.prefer_tie = True
        rules.boa_macro = "CATDeclareClass"
        rules.framework_suffix = version.framework_suffix
        rules.module_suffix = version.module_suffix
        rules.imake_ext = ".mk"
        rules.link_with_keyword = "LINK_WITH"

    return rules


# ─── Convenience ─────────────────────────────────────────────────


def detect_and_get_rules(catia_install: str = None, version_str: str = None) -> tuple:
    """Detect version and return (CAAVersion, VersionRules) or (None, None)"""
    version = detect_version(catia_install, version_str)
    if version:
        return version, get_rules(version)
    return None, None
