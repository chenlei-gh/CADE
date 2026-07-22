"""
CAA API Registry — Knowledge-driven API Whitelist
==================================================
Builds a verified API/header whitelist from the CADE knowledge base
(capabilities/*.md curated frontmatter + templates' actual includes),
so the static verifier can flag fabricated or misspelled CAA APIs
instead of silently passing them.

Why this exists:
  capabilities/*.md frontmatter contains hand-verified `apis:` lists
  (checked against CAADoc — e.g. capabilities/selection.md documents
  that CATISelection::GetSelection() does NOT exist). Before this
  module, that knowledge was only used for docs search; generated
  code was never validated against it, so a fabricated API like
  #include "CATISelectionSetFactory.h" would sail through.

Design principle:
  One registry, loaded once per process (cached), read-only.
  Knowledge stays in the .md files — this is just an index over it.

Usage:
  from api_registry import ApiRegistry
  reg = ApiRegistry.load(skill_root)
  reg.is_known_header("CATISpecObject.h")      # True
  reg.is_known_api("CATCSO")                   # True
  reg.is_known_api("CATISelectionFactoryX")    # False → suspect
  reg.suggest("CATISelectionn")                # "CATISelectionSet"?
"""

from __future__ import annotations

import re
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Set


# YAML frontmatter list field:  apis: [A, B, C]  (single line only —
# all 13 capabilities files and framework files use this form)
_LIST_FIELD_RE = re.compile(
    r"^(?P<key>apis|frameworks)\s*:\s*\[(?P<items>[^\]]*)\]",
    re.MULTILINE,
)
# CAA identifiers: CAT-prefixed class/interface names, also CATI*/CATDlg* etc.
_CAA_NAME_RE = re.compile(r"\bCAT[A-Za-z0-9_]{2,}\b")


class ApiRegistry:
    """
    Whitelist of known CAA APIs and headers, indexed from the knowledge base.

    Sources (in trust order):
      1. capabilities/*.md frontmatter `apis:` — hand-verified against CAADoc
      2. templates/** #include "X.h" — headers CADE itself emits (self-consistent)
      3. knowledge/frameworks/*.md frontmatter `apis:` — auto-extracted, noisy
         (used for headers only after _NON_API_SUFFIXES filtering)
    """

    # Suffixes seen in auto-extracted framework keywords that are NOT real
    # API names (CAADoc page anchors like CATI2DCamera_22103).
    _NOISY_SUFFIX_RE = re.compile(r"_\d{4,}$")

    def __init__(self):
        self.apis: Set[str] = set()            # verified API names (CATIProduct, ...)
        self.headers: Set[str] = set()         # known header basenames (no .h)
        self.api_source: Dict[str, str] = {}   # api → where it came from (for diagnostics)

    # ─── Loading ─────────────────────────────────────────────────

    @classmethod
    def load(cls, skill_root: Path) -> "ApiRegistry":
        """Build the registry from the skill's knowledge base + templates."""
        reg = cls()
        skill_root = Path(skill_root)

        # 1. capabilities/*.md — curated, highest trust
        cap_dir = skill_root / "capabilities"
        if cap_dir.is_dir():
            for md in sorted(cap_dir.glob("*.md")):
                reg._ingest_frontmatter(md, trust="capability")

        # 2. templates/** — headers CADE generates (keeps registry
        #    self-consistent: verifier must never flag our own output)
        tpl_dir = skill_root / "templates"
        if tpl_dir.is_dir():
            reg._ingest_template_includes(tpl_dir)

        # 3. knowledge/frameworks/*.md — auto-extracted; filter noise
        fw_dir = skill_root / "knowledge" / "frameworks"
        if fw_dir.is_dir():
            for md in sorted(fw_dir.glob("*.md")):
                reg._ingest_frontmatter(md, trust="framework")

        return reg

    def _ingest_frontmatter(self, md_file: Path, trust: str):
        """Parse apis: [...] from a knowledge file's YAML frontmatter."""
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        # Only scan the frontmatter block (--- ... ---) to avoid body noise
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return
        fm = m.group(1)
        for field in _LIST_FIELD_RE.finditer(fm):
            if field.group("key") != "apis":
                continue
            for item in field.group("items").split(","):
                name = item.strip().strip("'\"")
                if not _CAA_NAME_RE.fullmatch(name):
                    continue
                if self._NOISY_SUFFIX_RE.search(name):
                    continue  # CATI2DCamera_22103-style anchors
                self._add_api(name, f"{trust}:{md_file.name}")
                # Convention: interface CATIProduct → CATIProduct.h
                self.headers.add(name)

    def _ingest_template_includes(self, tpl_dir: Path):
        """Harvest #include "X.h" headers from templates (CADE's own output)."""
        inc_re = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
        for f in tpl_dir.rglob("*"):
            if f.suffix not in (".h", ".cpp", ".mk"):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for inc in inc_re.findall(content):
                stem = Path(inc).stem
                # Skip placeholders (<CommandClassName>) and non-CAA
                if not stem or "<" in stem or not _CAA_NAME_RE.fullmatch(stem):
                    continue
                self.headers.add(stem)
                self._add_api(stem, "template")

    def _add_api(self, name: str, source: str):
        self.apis.add(name)
        self.api_source.setdefault(name, source)

    # ─── Queries ─────────────────────────────────────────────────

    def is_known_api(self, name: str) -> bool:
        """True if `name` is a whitelisted CAA API/class/interface."""
        return name in self.apis

    def is_known_header(self, header: str) -> bool:
        """True if `header` (basename, with or without .h) is whitelisted."""
        stem = Path(header).stem
        return stem in self.headers

    def is_caa_like(self, name: str) -> bool:
        """True if `name` looks like a CAA identifier (CAT-prefixed).

        Used to decide whether an unknown name is *suspect* (CAA-like but
        not whitelisted → possibly fabricated) vs. custom user code.
        """
        return bool(_CAA_NAME_RE.fullmatch(name))

    def suggest(self, name: str, n: int = 3) -> List[str]:
        """Closest whitelisted APIs for a suspect name (typo correction)."""
        return get_close_matches(name, sorted(self.apis), n=n, cutoff=0.75)

    # ─── Diagnostics ─────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "apis": len(self.apis),
            "headers": len(self.headers),
            "sources": {
                "capability": sum(1 for s in self.api_source.values() if s.startswith("capability:")),
                "framework": sum(1 for s in self.api_source.values() if s.startswith("framework:")),
                "template": sum(1 for s in self.api_source.values() if s == "template"),
            },
        }


# ─── Module-level cache ──────────────────────────────────────────

_CACHE: "Dict[str, ApiRegistry]" = {}


def get_registry(skill_root: Optional[Path] = None) -> ApiRegistry:
    """Process-wide cached registry. Loads once per skill_root."""
    if skill_root is None:
        skill_root = Path(__file__).parent.parent
    key = str(Path(skill_root).resolve())
    if key not in _CACHE:
        _CACHE[key] = ApiRegistry.load(skill_root)
    return _CACHE[key]
