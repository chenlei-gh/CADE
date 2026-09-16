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
