# Retrieval Architecture Contract

**Version**: 1.0
**Status**: Production
**Audience**: CADE developers and AI agents

This document defines how CADE looks up knowledge. It is a **contract**,
not a tutorial: it fixes which data sources are authoritative, which
entry points are mandatory, and which shortcuts are forbidden. Future
retrieval features (capability graphs, embeddings, new indexes) must
extend this contract, not bypass it.

---

## 1. The Four-Index Model

All retrieval in CADE goes through four indexes, each with a single
authoritative data source and a single lifecycle:

| Index | Authoritative source | What it answers | Snapshot (2026-07) |
|---|---|---|---|
| **CatalogIndex** | `catalog/index.yaml` | "Which knowledge file matches this intent?" | 86 entries, 34 aliases |
| **ApiRegistry** | `capabilities/*.md` + `templates/**` + `knowledge/frameworks/*.md` + `knowledge/failure_patterns/*.md` | "Is this API name real?" | 342 APIs |
| **HeaderMap** | B28 install `<FW>/PublicInterfaces/*.h` scan → `cache/header_map_<ver>.json` | "Does this class/header exist in CATIA?" | 5500 headers, 503 frameworks |
| **MethodIndex** | `cache/caadoc_index.json` (pre-parsed SDK headers) → `cache/method_index.pickle` | "Does type X really have method M?" | 2655 types |

The snapshot numbers are illustrative, not contractual; they change as
the knowledge base and CATIA versions grow. The sources are contractual.

---

## 2. Mandatory Entry Point

Every consumer must obtain indexes through the facade:

```python
from retrieval import get_retrieval
r = get_retrieval(skill_root)
hm = r.header_map        # HeaderMap (process-cached)
mi = r.method_index      # MethodIndex (HeaderMap injected)
reg = r.registry         # ApiRegistry (process-cached)
cat = r.catalog          # CatalogIndex (disk + process cached)
```

Rules:

- **Do not** call `HeaderMap.load()`, `MethodIndex.load()`,
  `ApiRegistry.load()`, or `CatalogIndex.load()` from feature code.
  The facade owns their lifecycle; direct calls create duplicate loads
  and stale instances.
- Exception: CLI entry points and tests may call `load()` directly when
  they intentionally need a fresh instance.

Agent-facing diagnostics:

```bash
python skills/retrieval.py
```

prints a JSON health report for all four indexes. Use this first when
any lookup result looks wrong.

---

## 3. Cache Lifecycle (uniform across indexes)

Every index follows the same three-tier pattern:

1. **Process cache** — one instance per skill_root per process,
   invalidated when the underlying cache file's mtime changes.
2. **Disk cache** — `cache/*.pickle` or `cache/*.json`, invalidated by
   source mtime plus a parser `_CACHE_VERSION` bump.
3. **Full rebuild** — parse the authoritative source, then populate
   both caches.

Cache corruption must log a warning, never fail silently (the catalog
`self/cls` bug went unnoticed for months because it failed silently).
`CACHE_STATS` counters exist so tests can assert caches engage.

---

## 4. Decision Rules

These rules resolve "which index do I trust" before you write code.

### 4.1 Judging whether an API / class / header exists

Priority:

1. **HeaderMap** — authoritative; built from the real CATIA install.
2. **ApiRegistry** — fallback when HeaderMap is unavailable.
3. **Knowledge documents** — context only, never proof of existence.

Forbidden:

- Scanning the B28 installation directory at runtime.
- Parsing SDK headers at runtime to prove a type exists (MethodIndex
  does this lazily for base classes only, inside the facade).
- Trusting LLM memory of CAA class names.

### 4.2 Judging whether a capability exists

Priority:

1. **`skills/capabilities.yaml`** — the declared capability registry.
2. **ApiRegistry** — for API-level facts.
3. **Knowledge documents** — for rationale.

Forbidden:

- Inferring a capability from the existence of a file (Phantom
  Capability anti-pattern; see `docs/CAPABILITY_HISTORY.md`).

### 4.3 Judging whether `receiver->Method()` is valid

Priority:

1. **MethodIndex** — type-aware, walks the inheritance chain.
2. **HeaderMap** — resolves which header declares the type.

Forbidden:

- Trusting LLM memory of method names.
- Warning on unknown types or unknown methods (MethodIndex returns
  `None` for "cannot judge"; silence is correct there).

### 4.4 Finding knowledge for a user intent

Priority:

1. **CatalogIndex.search()** — includes Chinese-alias expansion and
   relevance ranking.

Forbidden:

- `grep` over `knowledge/` from feature code.

---

## 5. Forbidden Shortcuts (summary)

| Tempting shortcut | Why it is forbidden |
|---|---|
| Runtime-scan B28 `PublicInterfaces/` | 503 frameworks; the scan is what `header_map_<ver>.json` caches |
| `grep` SDK headers for a method | MethodIndex already parsed them, with inheritance |
| Read `knowledge/*.md` directly in a feature | Bypasses catalog ranking and alias expansion |
| Add a new index without registering it here | Creates a second source of truth (Phantom) |

---

## 6. Extending This Contract

Before adding a fifth index or a new lookup path:

1. Check whether an existing index already answers the question.
2. If not, add the index behind the `Retrieval` facade with the same
   three-tier lifecycle.
3. Register it in `Retrieval.health()` and in
   `tests/test_retrieval_benchmark.py`.
4. Update this document's index table and Decision Rules.

`find_capability()` and capability-graph lookups are planned extensions
and must plug in here — they are deliberately deferred until real usage
shows the need.

---

*Related: `docs/CAPABILITY_HISTORY.md` (removed capabilities),
`skills/capabilities.yaml` (declared capability registry),
`tests/test_retrieval_benchmark.py` (cache regression tripwire).*
