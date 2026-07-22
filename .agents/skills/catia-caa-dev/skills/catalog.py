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

    # Relevance scoring: field weight × match quality, per query word (max
    # across fields), plus intent-based category boost. Ties keep the
    # original catalog order (stable).
    # 'desc' is a free-text natural-language description (playbook 目标,
    # failure 诊断). It is sparser and broader than curated keywords, so it
    # is weighted below 'keyword' to avoid a single Chinese-phrase hit
    # outranking a curated API keyword.
    # 'ref' holds cross-reference targets (cap.xxx, pb.xxx ...). They aid
    # recall (a playbook about selection should surface for 选择) but rank
    # low so they never outrank the referenced entry itself.
    _FIELD_WEIGHTS = {"keyword": 3.0, "id": 2.5, "title": 2.0, "desc": 1.8, "file": 1.0, "ref": 0.9}
    _MATCH_EXACT = 3.0
    _MATCH_PREFIX = 2.0
    _MATCH_SUBSTRING = 1.0
    # Playbook/pattern entries that match ONLY via their id/file tokens are
    # penalized: their "涉及 Capability" column declares they delegate to the
    # referenced capability/knowledge entry, so an id-only hit (e.g. 'dialog'
    # in pb.dialog_wizard) should rank below the foundational entry.
    _ID_ONLY_PENALTY = 0.7
    # Category priors: on neutral queries a playbook is a composition of
    # capabilities, so it starts slightly below the foundational entry it
    # delegates to. A pattern-intent query lifts playbooks/patterns instead.
    _PLAYBOOK_PRIOR = 0.8
    # Failure patterns are diagnostic references; on a neutral query they sit
    # below both foundational knowledge and playbooks. Only an explicit
    # failure-intent query lifts them (via _INTENT_BOOST).
    _FAILURE_PRIOR = 0.8
    _PATTERN_INTENT = ("pattern", "playbook", "模式", "架构", "最佳实践")
    _FAILURE_INTENT = ("报错", "错误", "失败", "崩溃", "无法", "不显示", "不工作",
                       "无反应", "缺失", "error", "fail", "missing", "crash")
    _INTENT_BOOST = 1.5   # category matches detected query intent
    _DEFAULT_BOOST = 1.2  # knowledge/capability on neutral queries

    def __init__(self):
        self.entries: List[CatalogEntry] = []
        self.aliases: Dict[str, List[str]] = {}  # alias_key → ["en_keyword1", "en_keyword2"]
        self._entry_refs: List[List[str]] = []  # per-entry cross-reference targets
        self._field_index: List[Dict[str, List[str]]] = []  # per-entry searchable tokens
        self._search_cache: Dict[str, List[CatalogEntry]] = {}  # query → results (LRU-ish)

    # ─── Process-wide cache (per skill_root + file mtime) ─────────
    _PROC_CACHE: Dict[str, "CatalogIndex"] = {}
    _PROC_CACHE_MTIME: Dict[str, float] = {}
    _SEARCH_CACHE_MAX = 128
    # Bump whenever parsing/scoring changes so stale disk pickles are dropped.
    _CACHE_VERSION = 2

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
            # Parser version guards against stale pickles when the scoring/
            # parsing logic changes but index.yaml does not. Bump on change.
            if payload.get("version") != self._CACHE_VERSION:
                return None
            index = cls()
            index.entries = payload["entries"]
            index.aliases = payload["aliases"]
            index._entry_refs = payload.get("refs", [[] for _ in index.entries])
            return index
        except Exception:
            return None

    def _save_disk_cache(self, skill_root: Path, catalog_file: Path,
                         mtime: float) -> None:
        p = self._disk_cache_path(skill_root, catalog_file)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": self._CACHE_VERSION,
                "mtime": mtime,
                "entries": self.entries,
                "aliases": self.aliases,
                "refs": self._entry_refs,
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

        Relevance-ranked: each entry scores per query word as
        max(field_weight × match_quality), then boosted by category when the
        query shows pattern-seeking or failure-diagnosis intent. Higher score
        first; ties preserve catalog order.
        """
        cache_key = f"{query}|{max_results}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        if not self._field_index:
            self._build_field_index()

        expanded = self._expand_aliases(query)
        words = [w.lower() for w in expanded.split() if len(w) >= 3]

        query_lower = query.lower()
        pattern_intent = any(t in query_lower for t in self._PATTERN_INTENT)
        failure_intent = any(t in query_lower for t in self._FAILURE_INTENT)

        scored: List[tuple] = []
        for idx, fields in enumerate(self._field_index):
            score = 0.0
            strong_hit = False  # any query word matched keyword or title
            for w in words:
                best = 0.0
                best_field = ""
                for field_name, tokens in fields.items():
                    weight = self._FIELD_WEIGHTS[field_name]
                    for tok in tokens:
                        if w == tok:
                            match = self._MATCH_EXACT
                        elif tok.startswith(w):
                            match = self._MATCH_PREFIX
                        elif w in tok:
                            match = self._MATCH_SUBSTRING
                        else:
                            continue
                        cand = weight * match
                        if cand > best:
                            best, best_field = cand, field_name
                score += best
                if best_field in ("keyword", "title", "desc"):
                    strong_hit = True
            if score <= 0:
                continue
            category = self.entries[idx].category
            if not strong_hit and category in ("playbook", "pattern"):
                score *= self._ID_ONLY_PENALTY
            if failure_intent and category == "failure_pattern":
                score *= self._INTENT_BOOST
            elif pattern_intent and category in ("pattern", "playbook"):
                score *= self._INTENT_BOOST
            elif not failure_intent and not pattern_intent:
                if category in ("knowledge", "capability"):
                    score *= self._DEFAULT_BOOST
                elif category == "playbook":
                    score *= self._PLAYBOOK_PRIOR
                elif category == "failure_pattern":
                    score *= self._FAILURE_PRIOR
            scored.append((score, idx))

        # Stable sort: score desc, original catalog order as tiebreak
        scored.sort(key=lambda t: (-t[0], t[1]))
        results = [self.entries[i] for _, i in scored[:max_results]]

        # Bound the cache
        if len(self._search_cache) >= self._SEARCH_CACHE_MAX:
            self._search_cache.clear()
        self._search_cache[cache_key] = results
        return results

    def _build_field_index(self) -> None:
        """Build per-entry searchable-token buckets, weighted by field."""
        self._field_index = []
        split_re = r"[._\-/]"
        # Title words are split on whitespace AND separators, with stray
        # punctuation stripped — knowledge-section titles are comma-joined
        # keyword strings, playbook/capability titles are Chinese phrases.
        title_re = r"[,/、，]"
        for i, entry in enumerate(self.entries):
            title_tokens = []
            for part in re.split(title_re, entry.title.lower()):
                for t in part.split():
                    t = t.strip("+*()（）,，.。:：")
                    if len(t) >= 3:
                        title_tokens.append(t)
            fields = {
                "keyword": [k for k in entry.keywords if len(k) >= 3],
                "id": [t for t in re.split(split_re, entry.id.lower()) if len(t) >= 3],
                "title": title_tokens,
                "file": [t for t in re.split(split_re, entry.file.lower()) if len(t) >= 3],
                "ref": list(self._entry_refs[i]) if i < len(self._entry_refs) else [],
            }
            # Playbook/failure titles are free-text descriptions, not curated
            # keywords; demote their hit weight to the 'desc' bucket.
            if entry.category in ("playbook", "failure_pattern"):
                fields["desc"] = fields.pop("title")
            self._field_index.append(fields)

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

            # Keywords come only from columns AFTER the title/description
            # column. The title is handled separately (title/desc field), so
            # it must not double-count as a keyword. Cross-reference tokens
            # (cap.xxx, pb.xxx, mecmod.xxx ...) are links to other entries,
            # not search keywords — indexing them lets a pattern/playbook
            # steal the referenced entry's terms.
            keywords = []
            refs = []
            for c in cols[3:]:
                for k in re.split(r"[,/、]", c):
                    k = k.strip().lower()
                    if len(k) < 3:
                        continue
                    if re.match(r"^[a-z]+\.[a-z_]", k):
                        refs.append(k)
                    else:
                        keywords.append(k)

            self.entries.append(CatalogEntry(
                id=entry_id,
                file=entry_file,
                title=entry_title,
                category=category,
                keywords=keywords,
                raw_line=line,
            ))
            self._entry_refs.append(refs)

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
