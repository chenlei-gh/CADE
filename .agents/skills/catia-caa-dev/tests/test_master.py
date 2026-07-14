#!/usr/bin/env python3
"""
CADE Test Suite — Master Runner
================================
Organized by L1-L7 pyramid. Run with: python test_master.py
"""

import subprocess
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent

SUITES = {
    # ── L1: Unit Tests ──
    "L1-1 Unit (49)": "test_full_integration.py",
    # ── L2: Integration — Feature modules ──
    "L2-1 Dependency Graph": "test_phase1_enhancements.py",
    "L2-2 Intent Layer": "test_phase2_intents.py",
    "L2-3 Rollback": "test_phase3_rollback.py",
    "L2-4 Enhanced Intents": "test_phase4_enhanced.py",
    "L2-5 Specification": "test_specification.py",
    "L2-6 Diagnostics": "test_diagnostics.py",
    "L2-7 FixPlan Executor": "test_fixplan_executor.py",
    "L2-8 Refactor": "test_refactor.py",
    # ── L3: End-to-End ──
    "L3-1 E2E Integration": "test_e2e_integration.py",
    # ── L4: Architecture ──
    "L4-1 Architecture (39)": "test_l4_architecture.py",
    # ── L5: Semantic ──
    "L5-1 Semantic (40)": "test_l5_semantic.py",
    # ── L6: Fault Injection ──
    "L6-1 Fault Inject (16)": "test_l6_fault_injection.py",
    # ── L7: Knowledge System ──
    "L7-1 Knowledge (16)": "test_knowledge_system.py",
    # ── L0: Kernel Contract Tests (v3.0) ──
    "L0-1 Kernel API": "test_kernel_public_api.py",
    "L0-2 Requirements": "test_requirements.py",
    "L0-3 Repair Loop": "test_repair_loop.py",
    "L0-4 Routing Coverage": "test_kernel_routing.py",
    "L0-5 Code Verifier": "test_code_verifier.py",
    "L0-6 Token Status": "test_token_status.py",
    "L0-7 SKILL YAML": "test_skill_yaml.py",
    "L1-2 Decomposer": "test_decomposer.py",
    # ── Integration & Coordination ──
    "Int-1 Build & Run": "test_build_and_run.py",
    "Int-2 Skill-AI": "test_skill_ai_coordination.py",
    # ── Full System ──
    "Full System": "test_full_regression.py",
    # ── Audit ──
    "Cross-Ref Audit": "test_cross_reference.py",
    "Token Optimizer": "test_token_optimizer.py",
    "CAA Structure": "test_caa_structure.py",
    "Intent Planner": "test_intent_planner.py",
    "AI Integration": "test_ai_integration.py",
    "Token Audit": "test_token_audit.py",
    "Deep Audit": "test_deep_audit.py",
    }

SKIP_SLOW = {"Int-1 Build & Run"}  # Skips CATIA start/stop in quick mode

VERIFY_STRINGS = {
    "test_full_integration.py": "ALL TESTS PASSED",
    "test_phase1_enhancements.py": "Phase 1 Enhancement Tests Complete",
    "test_phase2_intents.py": "Intent Layer implementation verified",
    "test_phase3_rollback.py": "Rollback system verified",
    "test_phase4_enhanced.py": "Phase 4 enhancements verified",
    "test_specification.py": "100%",
    "test_diagnostics.py": "100%",
    "test_fixplan_executor.py": "100%",
    "test_refactor.py": "100%",
    "test_e2e_integration.py": "passed",
    "test_l4_architecture.py": "100%",
    "test_l5_semantic.py": "100%",
    "test_l6_fault_injection.py": "100%",
    "test_knowledge_system.py": "ALL CHECKS PASSED",
    "test_kernel_public_api.py": "passed",
    "test_requirements.py": "passed",
    "test_repair_loop.py": "passed",
    "test_kernel_routing.py": "passed",
    "test_code_verifier.py": "passed",
    "test_token_status.py": "passed",
    "test_skill_yaml.py": "passed",
    "test_decomposer.py": "passed",
    "test_build_and_run.py": "All Build Time & Run Time commands working",
    "test_skill_ai_coordination.py": "Perfect —",
    "test_full_regression.py": "ALL TESTS PASSED",
    "test_cross_reference.py": "ALL CROSS-REFERENCES CONSISTENT",
    "test_token_optimizer.py": "All token optimizer tests passed",
    "test_caa_structure.py": "All CAA standard paths verified",
    "test_intent_planner.py": "All Planner tests passed",
    "test_ai_integration.py": "AI can seamlessly use ALL CADE APIs",
        "test_token_audit.py": "LOW (<500)",
            "test_deep_audit.py": "ALL REFERENCES CONSISTENT",
    }


def run(quick: bool = False):
    passed = 0
    failed = 0
    total_time = 0

    print("=" * 70)
    print("  CADE Test Suite — Master Runner")
    print(f"  Python {sys.version.split()[0]} | {time.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Mode: {'QUICK (skip slow)' if quick else 'FULL'}")
    print("=" * 70)

    for label, script in SUITES.items():
        script_path = SKILL_ROOT / "tests" / script

        if quick and label in SKIP_SLOW:
            print(f"\n  [SKIP] {label:<30s} (quick mode)")
            continue

        print(f"\n  [{label}]", end="", flush=True)

        t0 = time.time()
        try:
            r = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            print(f" TIMEOUT")
            failed += 1
            continue

        t1 = time.time()
        total_time += t1 - t0

        check_str = VERIFY_STRINGS.get(script, "")
        ok = check_str in r.stdout if check_str else (r.returncode == 0)

        if ok:
            passed += 1
            print(f" PASS ({t1 - t0:.1f}s)")
        else:
            failed += 1
            tail = (r.stderr or r.stdout)[-120:].replace("\n", " ")[:100]
            print(f" FAIL ({t1 - t0:.1f}s) — {tail}")

    # Summary
    total = passed + failed
    print("\n" + "=" * 70)
    print(f"  RESULT: {passed}/{total} suites ({passed / total * 100:.0f}%)")
    print(f"  Time:   {total_time:.0f}s")
    print("=" * 70)

    if failed == 0:
        print("\n  >>> ALL SUITES PASSED <<<")
    else:
        print(f"\n  >>> {failed} SUITE(S) FAILED <<<")

    return failed == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CADE Master Test Runner")
    parser.add_argument(
        "--quick", action="store_true", help="Skip slow tests (CATIA start/stop)"
    )
    args = parser.parse_args()

    ok = run(quick=args.quick)
    sys.exit(0 if ok else 1)
