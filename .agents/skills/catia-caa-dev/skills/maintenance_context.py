"""
CADE Maintenance Context Manager (P3-A.1)
=========================================
Lightweight, resilient JSON persistence contract for brownfield maintenance tasks.
Decoupled data layer: imported by build.py, kernel.py, and cade.py with zero circularity.

Schema Version: 1
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger("cade.maintenance_context")


@dataclass
class StructuredError:
    """Represents a structured error backed by L0 build evidence."""
    kind: str  # "compiler_error" | "linker_error" | "build_system_error" | "generic_error"
    file: Optional[str] = None
    line: Optional[int] = None
    code: Optional[str] = None  # e.g., "C2065", "LNK2001", "C1083"
    message: str = ""
    raw: str = ""
    level: str = "L0"  # L0 direct builder output
    module: Optional[str] = None
    associated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StructuredError":
        return cls(
            kind=data.get("kind", "generic_error"),
            file=data.get("file"),
            line=data.get("line"),
            code=data.get("code"),
            message=data.get("message", ""),
            raw=data.get("raw", ""),
            level=data.get("level", "L0"),
            module=data.get("module"),
            associated=bool(data.get("associated", False)),
        )


@dataclass
class BuildRecord:
    """Historical record of a single build attempt associated with maintenance."""
    build_id: str
    timestamp: str
    status: str  # "success" | "failed" | "error"
    association: str  # "explicit" | "workspace_level" | "unassociated"
    error_count: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BuildRecord":
        return cls(
            build_id=data.get("build_id", ""),
            timestamp=data.get("timestamp", ""),
            status=data.get("status", "unknown"),
            association=data.get("association", "unassociated"),
            error_count=int(data.get("error_count", 0)),
            errors=data.get("errors", []),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
        )


@dataclass
class MaintenanceContext:
    """
    Contract for a targeted module maintenance session.
    Preserves original request, findings, candidate code locations,
    runtime feedback, and build outcome history.
    """
    schema_version: int = 1
    task_id: str = ""
    workspace: str = ""
    target_module: str = ""
    original_request: str = ""
    problem_description: str = ""
    candidate_locations: List[Dict[str, Any]] = field(default_factory=list)
    verification_findings: List[Dict[str, Any]] = field(default_factory=list)
    runtime_feedback: List[Dict[str, Any]] = field(default_factory=list)
    build_results: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MaintenanceContext":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            task_id=data.get("task_id", ""),
            workspace=data.get("workspace", ""),
            target_module=data.get("target_module", ""),
            original_request=data.get("original_request", ""),
            problem_description=data.get("problem_description", ""),
            candidate_locations=data.get("candidate_locations", []),
            verification_findings=data.get("verification_findings", []),
            runtime_feedback=data.get("runtime_feedback", []),
            build_results=data.get("build_results", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    @property
    def last_build(self) -> Optional[dict]:
        """Derived view of the most recent build attempt."""
        if not self.build_results:
            return None
        return self.build_results[-1]

    @property
    def unresolved_build_errors(self) -> List[dict]:
        """
        Returns active build errors from the most recent build.
        Crucial contract: If the last build succeeded, previously recorded errors
        are considered resolved and this returns an empty list.
        """
        lb = self.last_build
        if not lb or lb.get("status") != "failed":
            return []
        return [e for e in lb.get("errors", []) if e.get("associated", True)]


def generate_task_id(workspace: str, target_module: str, request: str = "") -> str:
    """Generate a deterministic yet unique task identifier."""
    ws_hash = hashlib.md5(str(Path(workspace).resolve()).encode()).hexdigest()[:6]
    req_hash = hashlib.md5(request.strip().encode()).hexdigest()[:6] if request else "default"
    clean_mod = target_module.replace(".m", "").replace(".", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"maint_{clean_mod}_{ws_hash}_{req_hash}_{ts}"


def get_context_path(workspace_root: Union[str, Path], target_module: Optional[str] = None) -> Path:
    """
    Resolve the primary context storage path.
    Prioritizes <workspace>/.cade/maintenance/<module>.json.
    Falls back to user cache if workspace is read-only or inaccessible.
    """
    ws = Path(workspace_root).resolve()
    target_dir = ws / ".cade" / "maintenance"
    mod_slug = target_module.replace(".m", "") if target_module else "active"
    
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{mod_slug}.json"
    except (OSError, PermissionError):
        # Fallback to local cache
        ws_hash = hashlib.md5(str(ws).encode()).hexdigest()[:8]
        fallback_dir = Path(tempfile.gettempdir()) / "cade_cache" / ws_hash / "maintenance"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / f"{mod_slug}.json"


def load_context(workspace_root: Union[str, Path], target_module: Optional[str] = None) -> Optional[MaintenanceContext]:
    """
    Load an existing maintenance context.
    Resilience contract: If the file is missing, empty, or corrupted, returns None
    and logs a warning without crashing the caller.
    """
    try:
        path = get_context_path(workspace_root, target_module)
        if not path.exists():
            # If a specific module was requested but not found, also check if 'active.json' matches
            if target_module and target_module != "active":
                active_path = get_context_path(workspace_root, "active")
                if active_path.exists():
                    active_ctx = load_context(workspace_root, "active")
                    if active_ctx and active_ctx.target_module == target_module:
                        return active_ctx
            return None

        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return None

        data = json.loads(content)
        if not isinstance(data, dict):
            logger.warning(f"Corrupted maintenance context at {path}: root is not a dict")
            return None

        return MaintenanceContext.from_dict(data)
    except json.JSONDecodeError as jde:
        logger.warning(f"Malformed JSON in maintenance context at {path}: {jde}")
        return None
    except Exception as e:
        logger.warning(f"Failed to read maintenance context from {workspace_root}: {e}")
        return None


def save_context(ctx: MaintenanceContext) -> bool:
    """
    Persist maintenance context to disk atomically.
    Never throws unhandled exceptions; returns True on success, False on failure.
    """
    try:
        path = get_context_path(ctx.workspace, ctx.target_module)
        ctx.updated_at = datetime.now().isoformat()
        if not ctx.created_at:
            ctx.created_at = ctx.updated_at

        data_str = json.dumps(ctx.to_dict(), indent=2, ensure_ascii=False)
        
        # Atomic write via temporary file
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(data_str, encoding="utf-8")
        if path.exists():
            path.unlink()
        tmp_path.rename(path)

        # Also update active.json pointer if this is a module-specific context
        if ctx.target_module and ctx.target_module != "active":
            active_path = get_context_path(ctx.workspace, "active")
            try:
                active_path.write_text(data_str, encoding="utf-8")
            except Exception:
                pass

        return True
    except Exception as e:
        logger.warning(f"Failed to persist maintenance context: {e}")
        return False


def normalize_error(raw_err: Any, target_module: Optional[str] = None) -> StructuredError:
    """Normalize raw parser/compiler error objects into structured L0 evidence."""
    if isinstance(raw_err, dict):
        file_path = raw_err.get("file")
        line_num = raw_err.get("line")
        code = raw_err.get("code")
        message = raw_err.get("message", "")
        mod = raw_err.get("module")
        raw = raw_err.get("raw") or f"{file_path}({line_num}) : {code} {message}"
    elif hasattr(raw_err, "file"):
        file_path = getattr(raw_err, "file", None)
        line_num = getattr(raw_err, "line", None)
        code = getattr(raw_err, "code", None)
        message = getattr(raw_err, "message", "")
        mod = getattr(raw_err, "module", None)
        raw = getattr(raw_err, "raw", "") or f"{file_path}({line_num}) : {code} {message}"
    else:
        raw = str(raw_err)
        file_path, line_num, code, message, mod = None, None, None, raw, None

    # Determine kind
    kind = "compiler_error"
    if code and code.startswith("LNK"):
        kind = "linker_error"
    elif code and "make" in str(code).lower():
        kind = "build_system_error"

    # Line normalization
    try:
        line_int = int(line_num) if line_num is not None else None
    except (ValueError, TypeError):
        line_int = None

    # Association determination
    associated = False
    if target_module:
        t_mod_clean = target_module.replace(".m", "").lower()
        if mod and t_mod_clean in mod.lower():
            associated = True
        elif file_path and (t_mod_clean in file_path.lower() or target_module.lower() in file_path.lower()):
            associated = True

    return StructuredError(
        kind=kind,
        file=file_path,
        line=line_int,
        code=code,
        message=message,
        raw=raw,
        level="L0",
        module=mod,
        associated=associated,
    )


def attach_build_result(
    workspace_root: Union[str, Path],
    build_result: dict,
    target_module: Optional[str] = None,
) -> Optional[MaintenanceContext]:
    """
    Hook called after a build completes.
    Associates the build outcome into the active maintenance context.

    Safety contract:
      - Never alters the build exit status or throws exceptions.
      - If no active maintenance context exists for target_module or workspace,
        no spurious context is forced.
      - Accurately classifies association (explicit vs unassociated).
    """
    try:
        ctx = load_context(workspace_root, target_module)
        if not ctx:
            return None

        status = build_result.get("status", "unknown")
        raw_errors = build_result.get("errors", [])
        duration = build_result.get("duration_seconds", 0.0)

        # Normalize errors to L0 structured evidence
        normalized_errors = []
        has_module_specific_error = False

        for err in raw_errors:
            struct_err = normalize_error(err, target_module=ctx.target_module)
            if struct_err.associated:
                has_module_specific_error = True
            normalized_errors.append(struct_err.to_dict())

        # Determine association type
        if has_module_specific_error:
            association = "explicit"
        elif not normalized_errors and status == "success":
            association = "explicit"
        else:
            association = "workspace_level"

        build_id = f"b_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        record = BuildRecord(
            build_id=build_id,
            timestamp=datetime.now().isoformat(),
            status=status,
            association=association,
            error_count=len(normalized_errors),
            errors=normalized_errors,
            duration_seconds=duration,
        )

        ctx.build_results.append(record.to_dict())
        save_context(ctx)
        return ctx
    except Exception as e:
        logger.warning(f"Non-blocking error in attach_build_result: {e}")
        return None
