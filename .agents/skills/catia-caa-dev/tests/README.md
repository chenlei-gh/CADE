# Test Index

测试目录包含 **24 个 master runner 套件**（含 3 个未注册独立测试）。共 **27 个文件**，~600 测试项，覆盖 48 条功能链路。

知识资产：204 文件（29K + 13P + 10C + 2PB + 149FW + 1E）

---

## Master Runner 套件（24）

在 `test_master.py` 中注册，可通过 `python test_master.py` 批量运行。

### L1 — 单元测试

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_full_integration.py` | 49 | L1-1 Unit (49) |

### L2 — 功能模块集成

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_phase1_enhancements.py` | 依赖图/级联删除/可视化 | L2-1 Dependency Graph |
| `test_phase2_intents.py` | 意图→计划转换 | L2-2 Intent Layer |
| `test_phase3_rollback.py` | 快照/回滚/备份管理 | L2-3 Rollback |
| `test_phase4_enhanced.py` | Feature/Extension/建议 | L2-4 Enhanced Intents |
| `test_specification.py` | 8 种 Spec 校验 | L2-5 Specification |
| `test_diagnostics.py` | 诊断引擎/FixPlan | L2-6 Diagnostics |
| `test_fixplan_executor.py` | 自动修复执行 | L2-7 FixPlan Executor |
| `test_refactor.py` | 重命名/移动/引用更新 | L2-8 Refactor |

### L3 — 端到端

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_e2e_workflow.py` | 创建→编译→运行流程 | L3-1 E2E Workflow |

### L4 — 架构不变量

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_l4_architecture.py` | 29 检查项 | L4-1 Architecture (29) |

### L5 — 语义完整性

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_l5_semantic.py` | 40 检查项 | L5-1 Semantic (40) |

### L6 — 故障注入

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_l6_fault_injection.py` | 16 检查项 | L6-1 Fault Inject (16) |

### L7 — 知识系统

| 文件 | 测试项 | Master 标签 |
|------|--------|------------|
| `test_knowledge_system.py` | 16 检查项 | L7-1 Knowledge (16) |

### 集成套件

| 文件 | Master 标签 | 备注 |
|------|------------|------|
| `test_build_and_run.py` | Int-1 Build & Run | 需 CATIA 环境，quick 模式跳过 |
| `test_skill_ai_coordination.py` | Int-2 Skill-AI | AI 协同 + 运行时链 |

### 审计套件

| 文件 | Master 标签 | 覆盖 |
|------|------------|------|
| `test_complete_system.py` | Full System | 15 类别全系统验证 |
| `test_cross_reference.py` | Cross-Ref Audit | 文件引用/知识计数/README 对齐 |
| `test_token_optimizer.py` | Token Optimizer | Token 压缩率/关键信息保留 |
| `test_token_audit.py` | Token Audit | Token 消耗审计 |
| `test_caa_structure.py` | CAA Structure | CAA 目录结构合规 |
| `test_intent_planner.py` | Intent Planner | Intent Engine 规划 |
| `test_ai_integration.py` | AI Integration | AI 全 API 能力 |
| `test_deep_audit.py` | Deep Audit | 链接/导入/版本/模板对齐 |

---

## 独立测试（3）

不在 master runner 中，需单独运行或作为开发工具使用。

| 文件 | 用途 | 运行方式 |
|------|------|---------|
| `test_catia_detection.py` | CATIA 安装检测系统测试 | `python test_catia_detection.py` |
| `test_production_readiness.py` | 生产就绪检查清单 | `python test_production_readiness.py` |
| `test_system_health.py` | 系统健康全面检查 | `python test_system_health.py` |

---

## 运行入口

```bash
# Master runner（推荐）
python test_master.py             # 全量
python test_master.py --quick     # 快速（跳过 Build/Run）

# 按层级
python test_master.py --layers    # 仅 L1-L7
python test_master.py --audit     # 仅审计套件

# 单文件
python test_knowledge_system.py
python test_deep_audit.py

# 独立测试
python test_catia_detection.py
python test_system_health.py
```

---

## 维护规则

1. **新测试必须注册到 `test_master.py`** 的 `SUITES` 字典，除非是独立开发工具
2. **测试文件命名**: `test_<功能>.py`
3. **使用统一 `check()` 函数** 格式：`check("描述", 条件)`
4. **独立测试**（不注册 master）仅限环境依赖或开发辅助工具
5. **本索引文件** 每次添加/删除测试后必须更新

---

**最后更新**: 2026-07-10  
**文件数**: 27（24 套件 + 3 独立）
