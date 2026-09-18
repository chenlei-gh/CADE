# Test Index

套件数以 `test_master.py` 的 `SUITES` 为准（当前 **42** 个注册套件；`--quick` 跳过 `SKIP_SLOW = {Int-1 Build & Run}`，执行 41 套）。

磁盘上另有 `test_*.py` 文件（当前 43 个，含本 runner）。**不要用文件个数覆盖套件数。** 未注册进 `SUITES` 的文件不算 master 套件。

知识资产计数会漂移；以知识目录与 Catalog 为准，不要用本节数字结案。

---

## Master Runner 套件

在 `test_master.py` 的 `SUITES` 中注册，可通过 `python test_master.py` 批量运行。下表是导航，不是权威；增删套件只改 `SUITES`。

### L0 — Kernel 契约测试（v3.0）

| 文件 | Master 标签 |
|------|------------|
| `test_kernel_public_api.py` | L0-1 Kernel API |
| `test_requirements.py` | L0-2 Requirements |
| `test_repair_loop.py` | L0-3 Repair Loop |
| `test_kernel_routing.py` | L0-4 Routing Coverage |
| `test_code_verifier.py` | L0-5 Code Verifier |
| `test_token_status.py` | L0-6 Token Status |
| `test_skill_yaml.py` | L0-7 SKILL YAML |

### L1 — 单元测试

| 文件 | Master 标签 |
|------|------------|
| `test_full_integration.py` | L1-1 Unit (49) |
| `test_icons.py` | L1-2 Icons (14) |
| `test_decomposer.py` | L1-2 Decomposer |
| `test_token_audit.py` | L1-3 Token Audit |

### L2 — 功能模块集成

| 文件 | Master 标签 |
|------|------------|
| `test_phase1_enhancements.py` | L2-1 Dependency Graph |
| `test_phase2_intents.py` | L2-2 Intent Layer |
| `test_phase3_rollback.py` | L2-3 Rollback |
| `test_phase4_enhanced.py` | L2-4 Enhanced Intents |
| `test_diagnostics.py` | L2-5 Diagnostics |
| `test_fixplan_executor.py` | L2-6 FixPlan Executor |
| `test_refactor.py` | L2-7 Refactor |
| `test_production_regressions.py` | L2-8 Production Regressions |

### L3 — 端到端

| 文件 | Master 标签 |
|------|------------|
| `test_e2e_integration.py` | L3-1 E2E Integration |

### L4–L7

| 文件 | Master 标签 |
|------|------------|
| `test_l4_architecture.py` | L4-1 Architecture (39) |
| `test_l5_semantic.py` | L5-1 Semantic (40) |
| `test_l6_fault_injection.py` | L6-1 Fault Inject (16) |
| `test_knowledge_system.py` | L7-1 Knowledge (16) |

### 集成套件

| 文件 | Master 标签 | 备注 |
|------|------------|------|
| `test_build_and_run.py` | Int-1 Build & Run | 需 CATIA 环境，quick 模式跳过 |
| `test_catia_detection.py` | Sys-1 CATIA Detection | 已注册，不是独立测试 |
| `test_skill_ai_coordination.py` | Int-2 Skill-AI | AI 协同 + 运行时链 |

### 审计 / 其余注册套件

| 文件 | Master 标签 |
|------|------------|
| `test_full_regression.py` | Full System |
| `test_cross_reference.py` | Cross-Ref Audit |
| `test_token_optimizer.py` | Token Optimizer (merged) |
| `test_caa_structure.py` | CAA Structure |
| `test_intent_planner.py` | Intent Planner |
| `test_ai_integration.py` | AI Integration |
| `test_deep_audit.py` | Deep Audit |
| `test_system_health.py` | System Health |
| `test_multi_intent.py` | Multi-Intent |
| `test_kernel_edge_cases.py` | Kernel Edges |
| `test_ui_scenario.py` | UI Scenario |
| `test_capability_contract.py` | Capability Contract |
| `test_retrieval_benchmark.py` | Retrieval Benchmark |
| `test_usecase_index.py` | UseCase Index |
| `test_ui_generator_clarifier.py` | UI Clarifier |

---

## 未注册进 SUITES 的文件

这些**不是** master 套件。不要把它们算进 42。

| 文件 | 说明 |
|------|------|
| `test_master.py` | runner 本身 |

`tools/production_readiness_check.py` 是工具，不是测试套件。

---

## 运行入口

```bash
# Master runner（推荐）
python test_master.py             # 全量（42 套）
python test_master.py --quick     # 快速（41 套，跳过 Int-1 Build & Run）

# 按层级（以 test_master.py 实现为准）
python test_master.py --layers
python test_master.py --audit

# 单文件（已注册套件也可单独跑）
python test_knowledge_system.py
python test_deep_audit.py
```

---

## 维护规则

1. **新测试必须注册到 `test_master.py` 的 `SUITES`**，除非明确是未接入的实验/辅助脚本
2. **测试文件命名**: `test_<功能>.py`
3. **使用统一 `check()` 函数** 格式：`check("描述", 条件)`
4. **套件总数不要写死在本文件标题里**；权威是 `SUITES` 的条目数，quick 跳过集合是 `SKIP_SLOW`
5. 本索引只负责导航。增删套件后核对本表是否漏列即可，不要靠手改「30/32/33/35」这类计数

---

**最后更新**: 2026-08-28
