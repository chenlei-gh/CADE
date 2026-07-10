# CADE Test Documentation

CADE 使用 **L1-L7 分层测试金字塔** + 集成/审计套件，覆盖从单元到系统的所有层次。

---

## 测试分层

```
         ┌─────────────┐
         │   L7 知识系统  │  ← 最顶层：验证知识资产完整性
         ├─────────────┤
         │   L6 故障注入  │  ← 异常/边界条件
         ├─────────────┤
         │   L5 语义     │  ← 跨模块一致性
         ├─────────────┤
         │   L4 架构     │  ← 不变量、设计约束
         ├─────────────┤
         │   L3 E2E     │  ← 完整工作流
         ├─────────────┤
         │   L2 集成     │  ← 功能模块（8 套件）
         ├─────────────┤
         │   L1 单元     │  ← 最底层：独立函数
         └─────────────┘
             ▲
    ┌────────┴────────┐
    │  集成 & 审计套件  │  ← 跨层验证
    └─────────────────┘
```

---

## 套件清单

### L1 — 单元测试

| 标签 | 文件 | 测试数 | 覆盖 |
|------|------|--------|------|
| L1-1 Unit (49) | `test_full_integration.py` | 49 | 元模型、变更集、模板、分析器、原子操作 |

### L2 — 功能模块集成（8 套件）

| 标签 | 文件 | 覆盖 |
|------|------|------|
| L2-1 Dependency Graph | `test_phase1_enhancements.py` | 依赖分析、级联删除、可视化 |
| L2-2 Intent Layer | `test_phase2_intents.py` | 意图→计划转换 |
| L2-3 Rollback | `test_phase3_rollback.py` | 快照、回滚、备份管理 |
| L2-4 Enhanced Intents | `test_phase4_enhanced.py` | Feature、Extension、智能推荐 |
| L2-5 Specification | `test_specification.py` | 8 种 Spec 类型校验 |
| L2-6 Diagnostics | `test_diagnostics.py` | 诊断引擎、FixPlan 生成 |
| L2-7 FixPlan Executor | `test_fixplan_executor.py` | 自动修复执行 |
| L2-8 Refactor | `test_refactor.py` | 重命名、移动、引用更新 |

### L3 — 端到端

| 标签 | 文件 | 覆盖 |
|------|------|------|
| L3-1 E2E Workflow | `test_e2e_workflow.py` | 创建→编译→运行完整流程 |

### L4 — 架构不变量

| 标签 | 文件 | 检查数 | 覆盖 |
|------|------|--------|------|
| L4-1 Architecture (29) | `test_l4_architecture.py` | 29 | 模块依赖方向、循环依赖、接口隔离 |

### L5 — 语义完整性

| 标签 | 文件 | 检查数 | 覆盖 |
|------|------|--------|------|
| L5-1 Semantic (40) | `test_l5_semantic.py` | 40 | 命名一致性、API 对称性、文档-代码对齐 |

### L6 — 故障注入

| 标签 | 文件 | 检查数 | 覆盖 |
|------|------|--------|------|
| L6-1 Fault Inject (16) | `test_l6_fault_injection.py` | 16 | 空输入、损坏数据、缺失文件、权限错误 |

### L7 — 知识系统

| 标签 | 文件 | 检查数 | 覆盖 |
|------|------|--------|------|
| L7-1 Knowledge (16) | `test_knowledge_system.py` | 16 | YAML frontmatter、ID 引用、Catalog 对齐 |

### 集成 & 审计套件

| 标签 | 文件 | 覆盖 |
|------|------|------|
| Int-1 Build & Run | `test_build_and_run.py` | 35 Build 命令 + 7 Run 命令 + 环境检测 |
| Int-2 Skill-AI | `test_skill_ai_coordination.py` | Skill-AI 协同 + 运行时链 |
| Full System | `test_complete_system.py` | 全系统 15 个类别验证 |
| Cross-Ref Audit | `test_cross_reference.py` | 文件引用、知识计数、README 对齐 |
| Token Optimizer | `test_token_optimizer.py` | Token 压缩率、关键信息保留 |
| Token Audit | `test_token_audit.py` | Token 消耗审计 |
| CAA Structure | `test_caa_structure.py` | CAA 目录结构合规 |
| Intent Planner | `test_intent_planner.py` | Intent Engine 规划验证 |
| AI Integration | `test_ai_integration.py` | AI 调用全 API 能力 |
| Deep Audit | `test_deep_audit.py` | 链接、导入、版本、Badge、模板对齐 |

---

## 运行方式

### 快速检查（跳过 Build/Run）
```bash
python tests/test_master.py --quick
# ~8s, 23 套件（跳过 Int-1 Build & Run）
```

### 全量检查
```bash
python tests/test_master.py
# ~60s, 24 套件（含 CATIA 启停）
```

### 单套件
```bash
python tests/test_knowledge_system.py
python tests/test_deep_audit.py
python tests/test_l4_architecture.py
```

### 按层级
```bash
# L1-L7 核心套件
python tests/test_master.py --layers

# 仅审计套件
python tests/test_master.py --audit
```

---

## 测试统计

| 指标 | 值 |
|------|-----|
| 套件总数 | **24** |
| L1-L7 核心 | 15 |
| 集成套件 | 2 |
| 审计套件 | 7 |
| 测试函数 | **56** |
| 断言/检查 | **~600** |
| 快速模式耗时 | ~8s |
| 全量模式耗时 | ~60s |
| 通过率 | **100%** |

---

## 添加新测试

### 1. 选择层级
- L1: 纯函数，无副作用
- L2: 功能模块集成，依赖 Python 模块
- L3: 完整工作流，依赖文件系统
- L4: 架构约束，静态分析
- L5: 语义检查，跨文件引用
- L6: 异常/边界，故意传入错误输入
- L7: 知识系统，验证 metadata + 引用

### 2. 遵循规范
```python
# test_new_feature.py
"""
New Feature Tests

验证：xxx 功能，覆盖 yyy 场景
"""

def check(name, condition, detail=""):
    """统一检查函数，格式：[PASS]/[FAIL] name — detail"""
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}")
    if not condition and detail:
        print(f"         {detail}")
    return condition

# 测试函数
def test_feature_a():
    check("1.1 basic case", result == expected)
    check("1.2 edge case", edge_result is not None)
```

### 3. 注册到 master runner
在 `test_master.py` 的 `SUITES` 字典中添加条目。

---

## 核心链路验证

CADE 共有 **48 条功能链路**，分属 **9 大类**。24 个测试套件覆盖全部链路。每次 CI 全量运行即验证全部。

### 链路矩阵

| # | 类别 | 链路数 | 覆盖测试 | 状态 |
|---|------|--------|---------|------|
| 1 | **创建** | 10 | L1 + L2-2 + L2-4 + L3 | ✅ |
| 2 | **查询** | 10 | L2-1 + L2-5 + L4 + L5 | ✅ |
| 3 | **构建** | 9 | Int-1 + Full System | ✅ |
| 4 | **运行** | 4 | Int-1 | ✅ |
| 5 | **诊断修复** | 2 | L2-6 + L2-7 | ✅ |
| 6 | **重构** | 3 | L2-8 | ✅ |
| 7 | **回滚** | 4 | L2-3 | ✅ |
| 8 | **知识** | 3 | L7 + Cross-Ref + DeepAudit | ✅ |
| 9 | **交互** | 3 | Int-2 + AI Integration | ✅ |

### 详细链路清单

| 类别 | 链路 | 验证
|------|------|------
| 创建 | framework → module → command → dialog → workbench → interface → component → add_to_wb → feature → extension | L1+L2-2+L2-4+L3
| 查询 | analyze → list_modules/commands/wb/interfaces → get_dep → get_dependents → visualize → validate → find_orphaned | L2-1+L4+L5
| 构建 | incremental → full → clean → debug → threaded → runtime_view → workspace_info → prereq → identity_card | Int-1
| 运行 | start_catia → run_macro → run_batch → stop_catia | Int-1
| 诊断修复 | diagnose_workspace → fix_apply | L2-6+L2-7
| 重构 | rename_command → rename_interface → move_command | L2-8
| 回滚 | snapshot → rollback → list_backups → cleanup | L2-3
| 知识 | catalog_lookup → caadoc_fallback → knowledge_precipitate | L7+DeepAudit
| 交互 | mcp_call → cli_call → python_api | Int-2+AI

### CAADoc Fallback 链路详解

```
AI 遇到 CADE knowledge/ 没有的问题
    ↓ ①
SKILL.md 规则: 📖 知识不足查 CAADoc/
    ↓ ②
`<CATIA_INSTALL>/CAADoc/Doc/online/` ← 使用案例（动态路径，非硬编码）
`<CATIA_INSTALL>/CAADoc/Doc/docs/api/` ← API 参考
    ↓ ③
解决问题后，强制沉淀:
  - knowledge/gaps/ 创建 gap 文件
  - knowledge/ 创建正式文件（含 YAML frontmatter）
  - catalog/index.yaml 添加条目
  - CHANGELOG.md 📝 知识沉淀 记录
  - 删除 gap 文件
    ↓ ④
test_cross_reference.py §8: 检测未沉淀缺口
test_knowledge_system.py: catalog ↔ files 对齐
```

### 验证日期

**2026-07-10**: 全部 12 条链路验证通过，24/24 全量测试 100%。

---

## 常见问题

**Q: 快速模式跳过了什么？**
A: 只跳过 `Int-1 Build & Run`（需要 CATIA 运行时+开发环境）。

**Q: 为什么全量模式偶尔失败？**
A: Build & Run 套件依赖真实 CATIA 环境（`CAA_INSTALL` 环境变量、mkmk 工具链）。确认 `caa_env_config.txt` 已正确配置。

**Q: 如何只跑新增的测试？**
A: `python tests/test_master.py --quick` 已覆盖所有非环境依赖套件。

---

**最后更新**: 2026-07-10  
**维护者**: Kiro AI Agent
