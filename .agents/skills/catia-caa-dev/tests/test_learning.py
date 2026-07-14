#!/usr/bin/env python3
"""
Learning System Tests
======================
Validates LearningRecorder event recording, PatternDetector
promotion logic, and failure pattern stub creation.

Run: python test_learning.py
"""

import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from learning import LearningEvent, LearningRecorder, PatternDetector, PatternRecord

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
# 1. LearningEvent Creation
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("  1. LearningEvent Creation")
print("=" * 70)

e1 = LearningEvent(type="compile_failure", source="build.py",
                   description="Missing include: CATBaseUnknown.h",
                   data={"error_signature": "missing_include", "file": "MyCmd.cpp", "line": 42})
check("event type", e1.type == "compile_failure")
check("event source", e1.source == "build.py")
check("event has timestamp", bool(e1.timestamp))
check("event data preserved", e1.data["error_signature"] == "missing_include")
check("event to_dict", isinstance(e1.to_dict(), dict))
check("to_dict has type", "type" in e1.to_dict())

e2 = LearningEvent(type="fix_success", source="repair.py",
                   description="Auto-added missing include",
                   data={"fix": "add_include", "file": "MyCmd.cpp"})
check("fix event type", e2.type == "fix_success")

e3 = LearningEvent(type="api_discovery", source="CAADoc/CATAssemblyInterfaces",
                   description="CATIProduct::ListChildren returns CATListVal",
                   data={"api": "CATIProduct", "method": "ListChildren"})
check("discovery event type", e3.type == "api_discovery")

# ═══════════════════════════════════════════════════════════════
# 2. LearningRecorder — Event Recording
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. LearningRecorder — Event Recording")
print("=" * 70)

recorder = LearningRecorder(skill_root=SKILL_ROOT)
check("recorder created", recorder is not None)
check("events start empty", len(recorder._events) == 0)

recorder.record(e1)
check("recorded 1 event", len(recorder._events) == 1)

recorder.record(e2)
recorder.record(e3)
check("recorded 3 events", len(recorder._events) == 3)

# Convenience method
recorder.record_event("compile_failure", "Test failure",
                      error_signature="test_error", file="test.cpp", line=10)
check("record_event adds event", len(recorder._events) == 4)
check("last event type", recorder._events[-1].type == "compile_failure")

# Recent events
recent = recorder.get_recent_events(limit=2)
check("get_recent_events limit=2", len(recent) == 2)
check("recent is dict list", isinstance(recent[0], dict))

# ═══════════════════════════════════════════════════════════════
# 3. Failure Pattern Stub Creation
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. Failure Pattern Stub Creation")
print("=" * 70)

# Use temp dir to avoid polluting real knowledge/
with tempfile.TemporaryDirectory() as tmpdir:
    tmp_skill = Path(tmpdir) / "skill"
    tmp_skill.mkdir()
    fp_dir = tmp_skill / "knowledge" / "failure_patterns"
    fp_dir.mkdir(parents=True)

    tmp_recorder = LearningRecorder(skill_root=tmp_skill)
    # Override failure_patterns_dir
    tmp_recorder.failure_patterns_dir = fp_dir

    e = LearningEvent(type="compile_failure", source="test.py",
                      description="Test failure pattern",
                      data={"error_signature": "fp_test_stub"})
    tmp_recorder.record(e)

    stub = fp_dir / "fp_fp_test_stub.md"
    check("stub file created", stub.exists())
    if stub.exists():
        content = stub.read_text(encoding="utf-8")
        check("stub has title", "Failure Pattern" in content)
        check("stub has signature", "fp_test_stub" in content)

# ═══════════════════════════════════════════════════════════════
# 4. PatternDetector — Single Events (No Promotion)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. PatternDetector — Single Events")
print("=" * 70)

detector = PatternDetector()
single_events = [
    LearningEvent(type="compile_failure", source="build.py",
                  description="Missing include A",
                  data={"error_signature": "missing_include_a"}),
]
results = detector.detect(single_events)
check("single event: no promotion", len(results) == 0, f"got {len(results)}")

# ═══════════════════════════════════════════════════════════════
# 5. PatternDetector — 3+ Repeated Events (Promotion)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. PatternDetector — Promotion Threshold")
print("=" * 70)

detector2 = PatternDetector()
repeated_events = [
    LearningEvent(type="compile_failure", source="build.py",
                  description="Missing CATBaseUnknown include",
                  data={"error_signature": "missing_catbaseunknown"}),
    LearningEvent(type="compile_failure", source="build.py",
                  description="Missing CATBaseUnknown include",
                  data={"error_signature": "missing_catbaseunknown"}),
    LearningEvent(type="compile_failure", source="build.py",
                  description="Missing CATBaseUnknown include",
                  data={"error_signature": "missing_catbaseunknown"}),
]
results = detector2.detect(repeated_events)
check("3 repeats: promotion triggered", len(results) >= 1, f"got {len(results)}")
if results:
    p = results[0]
    check("pattern occurrence=3", p.occurrence_count == 3)
    check("pattern should_promote", p.should_promote(threshold=3))
    check("pattern has description", bool(p.description))

# ═══════════════════════════════════════════════════════════════
# 6. PatternDetector — Mixed Event Types
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. PatternDetector — Mixed Events")
print("=" * 70)

detector3 = PatternDetector()
mixed_events = [
    LearningEvent(type="compile_failure", source="build.py",
                  description="Error A", data={"error_signature": "err_a"}),
    LearningEvent(type="compile_failure", source="build.py",
                  description="Error A", data={"error_signature": "err_a"}),
    LearningEvent(type="fix_success", source="repair.py",
                  description="Fixed B", data={"fix": "add_include"}),
    LearningEvent(type="compile_failure", source="build.py",
                  description="Error A", data={"error_signature": "err_a"}),
]
results = detector3.detect(mixed_events)
# err_a should appear 3 times → promoted; fix_success not promoted (threshold 3)
check("mixed: 1 pattern promoted", len(results) >= 1, f"got {len(results)}")
if results:
    promoted = results[0]
    check("promoted has correct key", "err_a" in promoted.id)

# ═══════════════════════════════════════════════════════════════
# 7. PatternRecord
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  7. PatternRecord")
print("=" * 70)

pr = PatternRecord(id="test_pattern", description="Test pattern",
                   occurrence_count=1)
check("not should_promote(1)", not pr.should_promote(threshold=3))
pr.occurrence_count = 3
check("should_promote(3)", pr.should_promote(threshold=3))
pr.occurrence_count = 5
check("should_promote(5)", pr.should_promote(threshold=3))

# ═══════════════════════════════════════════════════════════════
# 8. Integration: Recorder + Detector Pipeline
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  8. Integration: Recorder → Detector Pipeline")
print("=" * 70)

# Use temp dir to avoid writing stubs to real knowledge/
with tempfile.TemporaryDirectory() as tmpdir:
    tmp_skill = Path(tmpdir) / "skill"
    tmp_skill.mkdir()
    fp_dir = tmp_skill / "knowledge" / "failure_patterns"
    fp_dir.mkdir(parents=True)

    rec = LearningRecorder(skill_root=tmp_skill)
    rec.failure_patterns_dir = fp_dir
    det = PatternDetector(recorder=rec)

    # Record 3 identical failures
    for i in range(3):
        rec.record(LearningEvent(
            type="compile_failure", source="build.py",
            description="Missing LINK_WITH dependency",
            data={"error_signature": "missing_link_with"},
        ))

    results = det.detect()
    # Should detect the repeated pattern
    check("pipeline: pattern detected", len(results) >= 1, f"got {len(results)}")
    if results:
        check("pipeline: occurrence=3", results[0].occurrence_count == 3)

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  LEARNING SYSTEM: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All learning system tests passed <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")
    sys.exit(1)
