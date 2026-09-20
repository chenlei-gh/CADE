"""
CADE Maintenance Context Manager (P3-A.1 / P3-A.2)
=================================================
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
import uuid

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
class RuntimeFeedback:
    """Historical observation of runtime behavior in CATIA entered by a developer."""
    feedback_id: str
    timestamp: str
    symptom: str
    steps: List[str] = field(default_factory=list)
    expected: str = ""
    actual: str = ""
    build_id: Optional[str] = None
    reporter: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeFeedback":
        raw_steps = data.get("steps", [])
        if isinstance(raw_steps, list):
            steps = [str(s) for s in raw_steps if str(s).strip()]
        elif isinstance(raw_steps, str) and raw_steps.strip():
            steps = [s.strip() for s in raw_steps.splitlines() if s.strip()]
        else:
            steps = []

        return cls(
            feedback_id=data.get("feedback_id", ""),
            timestamp=data.get("timestamp", ""),
            symptom=data.get("symptom", ""),
            steps=steps,
            expected=data.get("expected", ""),
            actual=data.get("actual", ""),
            build_id=data.get("build_id"),
            reporter=data.get("reporter", ""),
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
    def last_feedback(self) -> Optional[dict]:
        """Derived view of the most recent runtime observation."""
        if not self.runtime_feedback:
            return None
        return self.runtime_feedback[-1]

    def append_feedback(self, feedback: Union[RuntimeFeedback, dict]) -> None:
        """Append runtime observation to history. Preserves existing entries and build results."""
        entry = feedback.to_dict() if isinstance(feedback, RuntimeFeedback) else feedback
        self.runtime_feedback.append(entry)

    @property
    def unresolved_build_errors(self) -> List[dict]:
        """
        Returns active unresolved build errors for this module.
        Crucial safety contract (P0 fix):
          1. Scans build history in reverse for the latest EXPLICIT build regarding this module.
          2. If the latest explicit build succeeded, errors are considered resolved -> [].
          3. If the latest explicit build failed, returns the associated L0 errors.
          4. A general workspace-level success that did NOT explicitly build or verify
             this module MUST NOT clear previously recorded explicit failure records.
        """
        for record in reversed(self.build_results):
            if record.get("association") == "explicit":
                if record.get("status") == "success":
                    return []
                elif record.get("status") in ("failed", "error"):
                    return [e for e in record.get("errors", []) if e.get("associated", True)]
        return []


def generate_unique_id(prefix: str) -> str:
    """
    Generate a collision-resistant identifier combining microsecond timestamp
    and short random suffix. Eliminates collision risk under clock rollbacks,
    concurrency, or mocked clocks.
    """
    now = datetime.now()
    rand_suffix = uuid.uuid4().hex[:6]
    return f"{prefix}_{now.strftime('%Y%m%d_%H%M%S_%f')}_{rand_suffix}"


def generate_task_id(workspace: str, target_module: str, request: str = "") -> str:
    """Generate a deterministic yet unique task identifier."""
    ws_hash = hashlib.md5(str(Path(workspace).resolve()).encode()).hexdigest()[:6]
    req_hash = hashlib.md5(request.strip().encode()).hexdigest()[:6] if request else "default"
    clean_mod = target_module.replace(".m", "").replace(".", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"maint_{clean_mod}_{ws_hash}_{req_hash}_{ts}"


def get_context_path(workspace_root: Union[str, Path], target_module: Optional[str] = None) -> Optional[Path]:
    """
    Resolve the module-specific context storage path purely in memory (zero filesystem side-effects).
    Does NOT create directories or touch disk on read/load operations.
    Returns None if target_module is omitted (active.json singleton completely removed).
    """
    if not target_module:
        return None
    ws = Path(workspace_root).resolve()
    target_dir = ws / ".cade" / "maintenance"
    mod_slug = target_module.replace(".m", "")
    return target_dir / f"{mod_slug}.json"


def load_context(workspace_root: Union[str, Path], target_module: Optional[str] = None) -> Optional[MaintenanceContext]:
    """
    Load an existing module maintenance context.
    Resilience contract:
      - Requires target_module; no active.json singleton fallback exists.
      - Never creates directories or modifies disk during read.
      - If file is missing or corrupted, logs a warning and returns None gracefully.
    """
    if not target_module:
        return None
    try:
        path = get_context_path(workspace_root, target_module)
        if not path or not path.exists():
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
    Persist maintenance context to disk using genuine atomic replace (P1 fix).
    Uses os.replace / Path.replace without intermediate unlink to prevent data loss on crash.
    Saves strictly to the target module context file; zero active.json singleton side-effects.
    Never throws unhandled exceptions; returns True on success, False on failure.
    """
    try:
        path = get_context_path(ctx.workspace, ctx.target_module)
        if not path:
            logger.warning("Failed to persist maintenance context: target_module is missing")
            return False
        
        # Ensure parent directory exists only at write time
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to persist maintenance context: workspace is read-only or inaccessible: {e}")
            return False

        ctx.updated_at = datetime.now().isoformat()
        if not ctx.created_at:
            ctx.created_at = ctx.updated_at

        data_str = json.dumps(ctx.to_dict(), indent=2, ensure_ascii=False)
        
        # Genuine atomic replace via unique PID-tagged temp file in same directory
        pid = os.getpid()
        ts_hash = hashlib.md5(f"{pid}_{datetime.now().isoformat()}".encode()).hexdigest()[:6]
        tmp_path = path.with_suffix(f".tmp_{pid}_{ts_hash}")
        tmp_path.write_text(data_str, encoding="utf-8")
        
        # Atomic replacement: replaces existing file atomically on both POSIX and Windows
        tmp_path.replace(path)
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
    if code and str(code).startswith("LNK"):
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
        if mod and t_mod_clean == mod.replace(".m", "").lower():
            associated = True
        elif file_path:
            fp_lower = str(file_path).lower().replace("\\", "/")
            if (f"/{t_mod_clean}.m/" in fp_lower or
                f"/{t_mod_clean}/" in fp_lower or
                fp_lower.startswith(f"{t_mod_clean}.m/") or
                fp_lower.startswith(f"{t_mod_clean}/")):
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
    Hook called after any build attempt (success, failure, timeout, or exception).
    Associates the build outcome into the relevant maintenance context.

    Strict safety & association rules (P0 & P2 fixes):
      1. Never alters the build exit status, duration, or throws exceptions.
      2. If target_module is NOT explicitly passed, attempts strict inference:
         - Inspects raw errors: if all errors exclusively belong to a single module M,
           target_module is inferred as M.
         - If build is success without explicit module, checks verification DLLs.
         - If inference cannot achieve 100% certainty, REFUSES to associate
           (Contract: Better unassociated than wrongly associated).
      3. For successful builds, only marks association as 'explicit' if:
         - target_module was explicitly targeted, OR
         - verification output explicitly proves the module's DLL was compiled/verified.
    """
    try:
        raw_errors = build_result.get("errors", [])
        status = build_result.get("status", "unknown")
        duration = build_result.get("duration_seconds", 0.0)

        # P0 Fix: Strict target module inference (no blind fallback to active.json)
        resolved_module = target_module
        if not resolved_module:
            error_modules = set()
            for err in raw_errors:
                m = err.get("module") if isinstance(err, dict) else getattr(err, "module", None)
                if m:
                    error_modules.add(m.strip())
                else:
                    f = err.get("file") if isinstance(err, dict) else getattr(err, "file", None)
                    if f and ".m" in str(f):
                        # Extract module name from path, e.g., .../CAABOMToolCmd.m/...
                        parts = Path(f).parts
                        for p in parts:
                            if p.endswith(".m"):
                                error_modules.add(p)

            if len(error_modules) == 1:
                resolved_module = list(error_modules)[0]
            elif status == "success" and not error_modules:
                # Success build without explicit module: check if single DLL in verification
                v_dlls = build_result.get("verification", {}).get("dlls", [])
                if len(v_dlls) == 1:
                    dll_name = v_dlls[0].get("name", "")
                    if dll_name.endswith(".dll"):
                        resolved_module = dll_name.replace(".dll", ".m")

        # If we still cannot reliably determine the module, do NOT force association
        if not resolved_module:
            return None

        ctx = load_context(workspace_root, resolved_module)
        if not ctx:
            return None

        # Normalize errors to L0 structured evidence
        normalized_errors = []
        has_module_specific_error = False

        for err in raw_errors:
            struct_err = normalize_error(err, target_module=ctx.target_module)
            if struct_err.associated:
                has_module_specific_error = True
            normalized_errors.append(struct_err.to_dict())

        # Determine association type with strict verification (P0 fix)
        if has_module_specific_error:
            association = "explicit"
        elif status == "success":
            # Check if this module was actually compiled/verified in this build
            verified_dlls = [d.get("name", "").lower() for d in build_result.get("verification", {}).get("dlls", [])]
            mod_dll = f"{ctx.target_module.replace('.m', '').lower()}.dll"
            if target_module or (mod_dll in verified_dlls):
                association = "explicit"
            else:
                association = "workspace_level"
        else:
            association = "workspace_level"

        build_id = generate_unique_id("b")
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


def record_runtime_feedback(
    workspace_root: Union[str, Path],
    target_module: str,
    symptom: str,
    steps: Optional[List[str]] = None,
    expected: str = "",
    actual: str = "",
    build_id: Optional[str] = None,
    reporter: str = "",
) -> Optional[MaintenanceContext]:
    """
    Append a human runtime observation to the target module's maintenance context.

    Safety and Boundary Principles (P3-B):
    1. Human Observation != Compiler Fact: Recorded purely as subjective observations,
       strictly segregated from L0 build errors in data schema and analysis display.
    2. Non-destructive: Never modifies, purges, or resolves existing build_results or L0 errors.
    3. Append-only: Preserves full history of prior feedback items.
    4. Deterministic Identity: Assigns sub-second microsecond unique feedback_id.
    5. Atomic disk persistence: Persisted via save_context().
    """
    if not target_module or not symptom or not str(symptom).strip():
        logger.warning("record_runtime_feedback rejected: target_module and non-empty symptom required")
        return None

    try:
        ws_path = Path(workspace_root).resolve()
        resolved_module = target_module if target_module.endswith(".m") else f"{target_module}.m"

        ctx = load_context(ws_path, resolved_module)
        if not ctx:
            task_id = generate_task_id(str(ws_path), resolved_module, f"feedback_{symptom}")
            ctx = MaintenanceContext(
                task_id=task_id,
                workspace=str(ws_path),
                target_module=resolved_module,
                original_request=f"[Human Runtime Observation] {symptom}",
                problem_description=symptom,
            )

        now = datetime.now()
        fb_id = generate_unique_id("fb")

        norm_steps = []
        if isinstance(steps, list):
            norm_steps = [str(s).strip() for s in steps if str(s).strip()]
        elif isinstance(steps, str) and steps.strip():
            norm_steps = [s.strip() for s in steps.splitlines() if s.strip()]

        fb = RuntimeFeedback(
            feedback_id=fb_id,
            timestamp=now.isoformat(),
            symptom=str(symptom).strip(),
            steps=norm_steps,
            expected=str(expected).strip(),
            actual=str(actual).strip(),
            build_id=str(build_id).strip() if build_id else None,
            reporter=str(reporter).strip(),
        )

        ctx.append_feedback(fb)
        if save_context(ctx):
            return ctx
        return None
    except Exception as e:
        logger.warning(f"Non-blocking error in record_runtime_feedback: {e}")
        return None
