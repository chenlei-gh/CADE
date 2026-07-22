"""
Catalog Index — Structured Knowledge Access
=============================================
Single source of truth for all catalog/index.yaml operations.
Parses once, exposes unified search + alias expansion.

Design principle:
  No scattered string parsing. One model, one API.
"""

from __future__ import annotations

import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CatalogEntry:
    """A single entry from the catalog index (capability, playbook, knowledge, etc.)"""
    id: str
    file: str
    title: str = ""
    category: str = ""  # capability | playbook | knowledge | philosophy | pattern | framework
    keywords: List[str] = field(default_factory=list)
    raw_line: str = ""


class CatalogIndex:
    """
    Parsed catalog/index.yaml — one instance per skill.

    Usage:
      catalog = CatalogIndex.load(skill_root)
      results = catalog.search("对话框")  # alias expansion + keyword matching
    """

    def __init__(self):
        self.entries: List[CatalogEntry] = []
        self.aliases: Dict[str, List[str]] = {}  # alias_key → ["en_keyword1", "en_keyword2"]
        self._inverted: Dict[str, List[int]] = {}  # word → entry indices (built lazily)
        self._search_cache: Dict[str, List[CatalogEntry]] = {}  # query → results (LRU-ish)

    # ─── Process-wide cache (per skill_root + file mtime) ─────────
    _PROC_CACHE: Dict[str, "CatalogIndex"] = {}
    _PROC_CACHE_MTIME: Dict[str, float] = {}
    _SEARCH_CACHE_MAX = 128

    @classmethod
    def load(cls, skill_root: Path) -> "CatalogIndex":
        """Parse catalog/index.yaml into structured model.

        Three-tier loading, fastest first:
          1. process-wide cache (valid while index.yaml mtime unchanged)
          2. on-disk pickle cache in cache/catalog_index.pickle
          3. full YAML parse (then populate both caches)
        """
        catalog_file = skill_root / "catalog" / "index.yaml"
        try:
            mtime = catalog_file.stat().st_mtime
        except OSError:
            return cls()

        # Tier 1: process-wide cache
        key = str(Path(skill_root).resolve())
        if (key in cls._PROC_CACHE
                and cls._PROC_CACHE_MTIME.get(key) == mtime):
            return cls._PROC_CACHE[key]

        # Tier 2: on-disk pickle cache (survives process restarts —
        # this is what makes CLI/MCP cold-start retrieval sub-ms)
        index = cls._load_disk_cache(skill_root, catalog_file, mtime)

        # Tier 3: full parse
        if index is None:
            index = cls()
            content = catalog_file.read_text(encoding="utf-8", errors="replace")
            index._parse(content)
            index._save_disk_cache(skill_root, catalog_file, mtime)

        cls._PROC_CACHE[key] = index
        cls._PROC_CACHE_MTIME[key] = mtime
        return index

    # ─── Disk cache ──────────────────────────────────────────────

    @classmethod
    def _disk_cache_path(cls, skill_root: Path, catalog_file: Path) -> Path:
        return skill_root / "cache" / "catalog_index.pickle"

    @classmethod
    def _load_disk_cache(cls, skill_root: Path, catalog_file: Path,
                         mtime: float) -> "Optional[CatalogIndex]":
        p = cls._disk_cache_path(skill_root, catalog_file)
        try:
            with p.open("rb") as f:
                payload = pickle.load(f)
            if payload.get("mtime") != mtime:
                return None
            if payload.get("version") != 1:
                return None
            index = cls()
            index.entries = payload["entries"]
            index.aliases = payload["aliases"]
            return index
        except Exception:
            return None

    def _save_disk_cache(self, skill_root: Path, catalog_file: Path,
                         mtime: float) -> None:
        p = self._disk_cache_path(skill_root, catalog_file)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "mtime": mtime,
                "entries": self.entries,
                "aliases": self.aliases,
            }
            with p.open("wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass  # cache write is best-effort

    # ─── Public API ──────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[CatalogEntry]:
        """
        Search catalog for entries matching the query.
        Automatically expands Chinese aliases to English keywords.

        Uses an inverted index (word → entries) instead of a linear scan,
        plus a small query→results cache for repeated lookups.
        """
        cache_key = f"{query}|{max_results}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        if not self._inverted:
            self._build_inverted_index()

        expanded = self._expand_aliases(query)
        words = [w.lower() for w in expanded.split() if len(w) >= 3]

        # Collect candidate entry indices via inverted index (substring
        # match on indexed words), preserving first-seen order.
        seen: Dict[int, None] = {}
        for w in words:
            for word, indices in self._inverted.items():
                if w in word:
                    for i in indices:
                        if i not in seen:
                            seen[i] = None
                            if len(seen) >= max_results:
                                break
                if len(seen) >= max_results:
                    break
            if len(seen) >= max_results:
                break

        results = [self.entries[i] for i in seen]

        # Bound the cache
        if len(self._search_cache) >= self._SEARCH_CACHE_MAX:
            self._search_cache.clear()
        self._search_cache[cache_key] = results
        return results

    def _build_inverted_index(self) -> None:
        """Build word → entry-indices map from keywords + title words."""
        self._inverted = {}
        for i, entry in enumerate(self.entries):
            words = set(entry.keywords)
            words.update(w.lower() for w in entry.title.split() if len(w) >= 3)
            for w in words:
                if len(w) >= 3:
                    self._inverted.setdefault(w, []).append(i)

    def has_alias_match(self, query: str) -> bool:
        """Check if query matches any alias key (for routing decisions)."""
        for alias_key in self.aliases:
            parts = [p.strip() for p in alias_key.replace("/", " ").split()]
            if any(p in query for p in parts):
                return True
        return False

    # ─── Internal ────────────────────────────────────────────────

    def _parse(self, content: str) -> None:
        """Parse catalog YAML content into entries and aliases."""
        # Find main sections
        sections = {
            "capability": ("### Capability 索引", "### Playbook 索引"),
            "playbook": ("### Playbook 索引", "### Framework 索引"),
            "philosophy": ("### Philosophy 索引", "### Failure Pattern 索引"),
            "failure_pattern": ("### Failure Pattern 索引", "### Knowledge 索引"),
            "knowledge": ("### Knowledge 索引", "### Pattern 索引"),
            "pattern": ("### Pattern 索引", "### Example 索引"),
        }

        for category, (start_marker, end_marker) in sections.items():
            self._parse_table_section(content, category, start_marker, end_marker)

        # Parse aliases
        self._parse_aliases(content)

    def _parse_table_section(self, content: str, category: str, start: str, end: str) -> None:
        """Extract table rows between two markers."""
        if start not in content:
            return

        # Extract section between start and end markers
        parts = content.split(start, 1)
        if len(parts) < 2:
            return
        section = parts[1]
        if end and end in section:
            section = section.split(end, 1)[0]

        for line in section.split("\n"):
            line = line.strip()
            if not line or not line.startswith("|"):
                continue
            if "---" in line:  # separator row
                continue

            # Parse table columns: | id | file | title/desc | ... |
            cols = [c.strip() for c in line.split("|")]
            # Strip empty first/last from split
            cols = [c for c in cols if c]
            if len(cols) < 3:
                continue

            entry_id = cols[0] if len(cols) > 0 else ""
            entry_file = cols[1] if len(cols) > 1 else ""
            entry_title = cols[2] if len(cols) > 2 else ""

            # Skip header rows
            if entry_id in ("ID", "id") or entry_title in ("文件", "目标", "能力", "内容", "诊断", "关键词", "适用场景"):
                continue

            # Extract keywords from remaining columns
            keywords = []
            for c in cols[2:]:
                keywords.extend([k.strip().lower() for k in re.split(r"[,/、]", c) if k.strip() and len(k.strip()) >= 3])

            self.entries.append(CatalogEntry(
                id=entry_id,
                file=entry_file,
                title=entry_title,
                category=category,
                keywords=keywords,
                raw_line=line,
            ))

    def _parse_aliases(self, content: str) -> None:
        """Parse the aliases table."""
        if "## 别名映射" not in content and "## 别名" not in content:
            return

        # Find alias section
        for header in ["## 别名映射 (Aliases)", "## 别名映射", "## 别名"]:
            if header in content:
                parts = content.split(header, 1)
                break
        else:
            return

        if len(parts) < 2:
            return
        section = parts[1]
        if "## 索引" in section:
            section = section.split("## 索引", 1)[0]

        for line in section.split("\n"):
            line = line.strip()
            if not line or not line.startswith("|"):
                continue
            if "---" in line:
                continue

            cols = [c.strip() for c in line.split("|")]
            cols = [c for c in cols if c]
            if len(cols) < 2:
                continue

            alias_key = cols[0]
            alias_values = cols[1] if len(cols) > 1 else ""

            # Skip header
            if alias_key in ("别名", "展开为关键词"):
                continue

            # Parse comma-separated keywords
            keywords = [k.strip().lower() for k in alias_values.replace("，", ",").split(",") if k.strip()]
            self.aliases[alias_key] = keywords

    def _expand_aliases(self, query: str) -> str:
        """Expand Chinese aliases in query to their English keywords."""
        expanded = query
        for alias_key, keywords in self.aliases.items():
            parts = [p.strip() for p in alias_key.replace("/", " ").split()]
            if any(p in query for p in parts):
                expanded += " " + " ".join(keywords)
        return expanded
