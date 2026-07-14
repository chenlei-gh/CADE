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

### L0 — Kernel 契约测试（v3.0 新增）

| 标签 | 文件 | 测试数 | 覆盖 |
|------|------|--------|------|
| L0-1 Kernel API | `test_kernel_public_api.py` | 16 | Kernel 3-mode 公共接口 |
| L0-2 Requirements | `test_requirements.py` | 21 | Requirements Clarifier |
| L0-3 Repair Loop | `test_repair_loop.py` | 20 | Repair Loop 状态机 |
| L0-4 Routing Coverage | `test_routing_coverage.py` | 41 | 41 旧工具 → 3-mode 全覆盖 |
| L0-5 Code Verifier | `test_code_verifier.py` | 15 | 静态代码检查宏/头文件/命名/格式 |
| L0-6 Token Status | `test_token_status.py` | 29 | 优化器状态白名单验证 |
| L0-7 SKILL YAML | `test_skill_yaml.py` | 17 | frontmatter 有效性检查 |

### L1 — 单元测试

| 标签 | 文件 | 测试数 | 覆盖 |
|------|------|--------|------|
| L1-1 Unit (49) | `test_full_integration.py` | 49 | 元模型、变更集、模板、分析器、原子操作 |
| L1-2 Decomposer | `test_decomposer.py` | 21 | 需求分解：决策→Playbook/Capability/依赖 |

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
| L3-1 E2E Integration | `test_e2e_integration.py` | Kernel + Actions 完整链路 |

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
| Full Regression | `test_full_regression.py` | 全系统 15 个类别验证 |
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
# ~8s, 31 套件（跳过 Int-1 Build & Run）
```

### 全量检查
```bash
python tests/test_master.py
# ~60s, 32 套件（含 CATIA 启停）
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
| 套件总数 | **32** |
| L1-L7+L0 核心 | 23 |
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
| 3 | **构建** | 9 | Int-1 + Full Regression | ✅ |
| 4 | **运行** | 4 | Int-1 | ✅ |
| 5 | **诊断修复** | 2 | L2-6 + L2-7 | ✅ |
| 6 | **重构** | 3 | L2-8 | ✅ |
| 7 | **回滚** | 4 | L2-3 | ✅ |
| 8 | **知识** | 3 | L7 + Cross-Ref + DeepAudit | ✅ |
| 9 | **交互** | 3 | Int-2 + AI Integration | ✅ |

### 48 条链路逐条测试覆盖

#### 创建 (10 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 1 | `create_framework` | L1 Unit | 单元测试 |
| 2 | `create_module` | L1 Unit | 单元测试 |
| 3 | `create_command` | L1 + L2-2 Intent + L3 E2E | 单元+意图+端到端 |
| 4 | `create_dialog` | L1 + L2-5 Spec | 单元+Spec 校验 |
| 5 | `create_workbench` | L1 + Full Regression | 单元+全系统 |
| 6 | `create_interface` | L1 + L2-5 Spec | 单元+Spec 校验 |
| 7 | `create_component` | L1 + L2-5 Spec | 单元+Spec 校验 |
| 8 | `add_command_to_workbench` | L1 + Full Regression | 单元+全系统 |
| 9 | `create_feature` | L2-4 Enhanced Intents | 意图层集成 |
| 10 | `create_extension` | L2-4 Enhanced Intents | 意图层集成 |

#### 查询 (10 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 11 | `analyze_workspace` | L1 + Full Regression | 单元+全系统 |
| 12 | `list_modules` | L1 + Cross-Ref | 单元+交叉引用 |
| 13 | `list_commands` | L1 | 单元测试 |
| 14 | `list_workbenches` | L1 | 单元测试 |
| 15 | `list_interfaces` | L1 | 单元测试 |
| 16 | `get_dependencies` | L2-1 DepGraph | 依赖图集成 |
| 17 | `get_dependents` | L2-1 DepGraph | 依赖图集成 |
| 18 | `visualize_dependencies` | L2-1 DepGraph | 依赖图集成 |
| 19 | `validate_workspace` | L1 + L4 Architecture | 单元+架构检查 |
| 20 | `find_orphaned_files` | L4 Architecture | 架构检查 |

#### 构建 (9 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 21 | `incremental_build` | Int-1 Build & Run | 真实 mkmk 调用 |
| 22 | `full_build` | Int-1 Build & Run | 真实 mkmk 调用 |
| 23 | `clean_build` | Int-1 Build & Run | 真实 mkmk 调用 |
| 24 | `debug_build` | Int-1 Build & Run | 真实 mkmk 调用 |
| 25 | `build_with_threads` | Int-1 Build & Run | 真实 mkmk 调用 |
| 26 | `create_runtime_view` | Int-1 Build & Run | 真实 mkCreateRuntimeView |
| 27 | `workspace_info` | Int-1 Build & Run | mkwhereami + mkreadcpd |
| 28 | `get_prerequisite` | Int-1 Build & Run | mkGetPreq + mkPrintPreq |
| 29 | `create_identity_card` | Int-1 Build & Run | mkCreateIC |

#### 运行 (4 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 30 | `start_catia` | Int-1 Build & Run | 真实 CNEXT 启动 |
| 31 | `run_macro` | Int-1 Build & Run | CNEXT -macro |
| 32 | `run_batch` | Int-1 Build & Run | CNEXT -batch |
| 33 | `stop_catia` | Int-1 Build & Run | 进程管理 |

#### 诊断修复 (2 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 34 | `diagnose` | L2-6 Diagnostics | 诊断引擎 |
| 35 | `fix_apply` | L2-7 FixPlan | 自动修复执行 |

#### 重构 (3 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 36 | `rename_command` | L2-8 Refactor | 重命名+引用更新 |
| 37 | `rename_interface` | L2-8 Refactor | 接口重命名 |
| 38 | `move_command` | L2-8 Refactor | 跨模块移动 |

#### 回滚 (4 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 39 | `snapshot` | L2-3 Rollback | 快照创建 |
| 40 | `rollback` | L2-3 Rollback | 回滚执行 |
| 41 | `list_backups` | L2-3 Rollback | 备份列表 |
| 42 | `cleanup_backups` | L2-3 Rollback | 备份清理 |

#### 知识 (3 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 43 | `catalog_lookup` | L7 Knowledge + Cross-Ref | frontmatter + catalog 对齐 |
| 44 | `caadoc_fallback` | 规则 + gap 检测 | SKILL.md 提示 + knowledge/gaps/ |
| 45 | `knowledge_precipitate` | Cross-Ref §8 + L7 | gap 检测 + catalog 完整性 |

#### 交互 (3 条)

| # | 链路 | 测试套件 | 验证方式 |
|---|------|---------|----------|
| 46 | `mcp_call` | Int-2 Skill-AI + AI Integration | AI 通过 MCP 全 API |
| 47 | `cli_call` | 各套件调用 | `cade` 命令 → Python API |
| 48 | `python_api` | AI Integration | 直接 Python API 调用 |

### 覆盖统计

| 指标 | 值 |
|------|-----|
| 链路总数 | **48** |
| 自动测试覆盖 | **47** (98%) |
| 规则+检测覆盖 | **1** (caadoc_fallback) |
| 测试套件 | **26** |
| 断言/检查 | **~600** |

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

**2026-07-11 23:22**: 全部 12 条链路验证通过，32/32 全量测试 100%（77s）。
  知识资产: 234（29K + 13P + 13C + 6PB + 149FW + 1E + 6PH + 3FP）

---

## 常见问题

**Q: 快速模式跳过了什么？**
A: 只跳过 `Int-1 Build & Run`（需要 CATIA 运行时+开发环境）。

**Q: 为什么全量模式偶尔失败？**
A: Build & Run 套件依赖真实 CATIA 环境（`CAA_INSTALL` 环境变量、mkmk 工具链）。确认 `caa_env_config.txt` 已正确配置。

**Q: 如何只跑新增的测试？**
A: `python tests/test_master.py --quick` 已覆盖所有非环境依赖套件。

---

**最后更新**: 2026-07-12  
**维护者**: Kiro AI Agent
