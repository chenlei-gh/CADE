---
id: pb.native_command_investigation
title: Native Command Investigation / 原生命令逆向调查方法论
category: playbook
domain: infrastructure
keywords: [reverse engineering, native command, dll, vtable, slot, investigation, B28, 逆向, 原生命令, 官方命令, 私有接口]
capabilities: []
apis: []
frameworks: []
difficulty: advanced
effort: large
release: [R28]
tags: [playbook, methodology, investigation, reverse_engineering]
---

# Native Command Investigation (原生命令逆向调查方法论)

本 Playbook 总结在面对官方公开 CAA 文档存在能力盲区、但 CATIA 原生界面拥有对应功能时的决策分析与逆向调查方法论。

> **方法论定位**：本方法论为跨领域的通用逆向调查框架，不绑定单一特定 Capability。文中所涉实测验证案例（如 Slot 17/18 属性重置）属于 Visualization/MecMod 领域，作为案例证据引用，不构成该方法论之能力边界。

---

## 准入条件 (Entry Criteria)

在启动原生命令深入调查前，必须严格确认满足以下全部条件：

1. **官方 CAA 确无公开方案**：已完整检索 CAADoc、全量头文件、`*.dico` 与已知 Playbook，未发现合法的公开 API。
2. **原生 UI 行为明确存在**：在 CATIA V5 交互界面中，该操作可以通过特定的按钮、菜单或对话框稳定复现。
3. **收益明确且风险可控**：该能力对于业务闭环具备关键价值，且团队了解非公开接口的稳定性和维护成本。

---

## 调查决策框架 (Investigation Phases)

> ⚠️ **说明**：以下阶段是结构化的**决策框架与排查思路**，而非僵化的一刀切流水线。实际调查应根据发现的线索灵活选择分析重心。

```text
Entry Criteria (准入核实)
      ↓
Phase 1 — Confirm native behavior (确认原生交互行为与上下文)
      ↓
Phase 2 — Identify native command (定位原生命令标识与所属 DLL)
      ↓
Phase 3 — Investigate implementation (分析二进制实现、符号与虚表)
      ↓
Phase 4 — Validate candidate interface (验证候选接口与调用语义)
      ↓
Phase 5 — Reproduce behavior (实验复现与隔离封装)
      ↓
Evidence / Version Scope (确定证据边界与风险标注)
```

### Phase 1 — Confirm native behavior (确认原生行为)
- 在纯净环境中操作原生功能，观察完整的上下文。
- 确认该功能修改的是模型数据（SpecObject）、图形显示状态（Visualization），还是纯会话临时状态。

### Phase 2 — Identify native command (定位原生命令与 DLL)
- 通过界面提示信息、NLS 资源文件（`resources/msgcatalog/*.CATNls`）或 `CATCommandHeader` 注册名反查命令标识。
- 结合运行时进程模块加载与导出表，定位承载该命令具体逻辑的共享库（`*.dll`）。

### Phase 3 — Investigate implementation (调查实现与虚表结构)
- 检查该 DLL 的导出符号、RTTI 类型信息及关联接口定义。
- 若目标行为通过未文档化的接口实现，分析其 vtable（虚函数表）布局，识别候选虚方法在虚表中的偏移位置。

### Phase 4 — Validate candidate interface (验证候选接口)
- 编写隔离的小型测试用例，尝试获取目标对象的候选接口。
- 检查方法签名的参数约定、调用约定（`__stdcall` / `__cdecl`）与内存管理语义（AddRef / Release 归属）。

### Phase 5 — Reproduce behavior (复现与封装)
- 在真实 CATIA 环境中运行测试，验证是否达到与原生功能完全一致的行为。
- 若验证成功，必须对调用点进行严格的隔离封装与异常防御，不得污染核心业务代码。

---

## 案例调查证据：CATIMmiResetProperties / Slot 17/18

在对 CATIA V5 B28 图形属性重置功能的逆向调查中，曾发现针对特定属性清除的私有虚表接口候选：

### ⚠️ 风险等级评估 (Risk & Contract Disclaimer)

```text
Evidence type: Reverse-engineered (逆向工程发现)
Version: CATIA V5 R2018 / B28
Official CAA documentation: Not established (非官方公开接口)
ABI stability: Not guaranteed (不保证跨版本/补丁包二进制兼容)
Cross-version validation: Not established (未在其它版本交叉验证)
Recommended use: Experimental / version-scoped only (仅限实验性验证或特定受控场景)
```

> **核心原则：Slot 17/18 是证据，不是 API 合同。**
> 
> 任何基于虚函数表偏移（vtable slot offset）的直接内存调用均不属于 Dassault Systèmes 的官方 API 承诺。CATIA 在后续的 Service Pack、Hotfix 或大版本更迭中，可能会因重构基类、调整继承链或重排虚函数顺序导致虚表偏移发生变化，进而引发非法内存访问硬崩溃。生产代码应优先追求官方支持的替代方案或明确受控的版本屏障。

---

## 停止条件 (Exit / Stop Criteria)

逆向调查应保持高度克制，当出现以下任一情况时，必须立即**终止逆向调查流程**：

1. **已发现公开替代方案**：在后续排查或深入官方用例中发现了官方支持的公开 API 组合，优先退回公开 CAA 路线。
2. **已有可靠 Knowledge / Failure Pattern 支持**：现有知识库或已知失效模式已能合理解释该现象或提供既有规避手段。
3. **原生行为无法稳定复现**：在纯净环境下该功能表现为偶发、强依赖特定环境或无法确立最小复现路径。
4. **候选私有接口无法独立验证**：缺乏必要的上下文句柄、初始化依赖深重或调用时必然引发无符号段错误。
5. **私有 ABI 风险不可承受**：项目明确要求跨 CATIA 大版本/Hotfix 强二进制兼容，且无法设置版本隔离保护网。

---

## 调查成果沉淀出口与规范 (Knowledge Sinks)

调查完成后，无论成功、部分成功或失败，均应通过人工方式进行结构化沉淀，严禁将未经验证的经验作为普通公开 API 合同沉淀。

### 1. 验证成功（获得可控规避或受限方案）
沉淀出口：`knowledge/<domain>/<name>.md`

必须包含以下结构化要素，**不能把一次“验证成功”直接等同于通用可复用方案**：

```markdown
---
id: <domain>.<name>
title: <简明描述>
category: knowledge
domain: <domain>
release: [<明确验证过的版本, 如 R28>]
tags: [<domain>, reverse_engineered, <环境实证tag>]
---

### 1. 观察到的事实 (Observed Facts)
- 原生界面的行为、命令 ID、对应承载 DLL。

### 2. 验证环境与版本 (Environment & Version)
- 严禁默认使用 `b28_verified`！只有真实在 B28 本机运行验证时方可标注；其它版本如实标注（如 `r21_verified`），仅靠二进制静态分析尚未实机运行的必须标为 `unverified_static_analysis`。

### 3. 实验复现步骤 (Reproduction Steps)
- 触发该行为的最小前置条件与调用代码示例。

### 4. 生效条件与前置约束 (Preconditions & Constraints)
- 目标对象类型、状态要求、必要的上下文环境。

### 5. 尚未确认的假设 (Unconfirmed Hypotheses)
- 明确指出哪些推论（如参数含义、副效应、内存释放机制）尚未完全证明。

### 6. 跨版本与 ABI 风险 (Cross-version & ABI Risks)
- 声明不可作为公开 API 合同，评估不同 SP/Hotfix 可能存在的虚表偏移变动风险与崩溃规避措施。
```

### 2. 验证失败（证明为死路或崩溃陷阱）
沉淀出口：`knowledge/failure_patterns/fp_<name>.md`

- 记录失败现象、崩溃堆栈或未生效的调用路径；
- 记录已排除的假设（例如确认某 DLL 导出函数并非预期功能）；
- 防止后续开发者重复进行无谓的二次探雷。
