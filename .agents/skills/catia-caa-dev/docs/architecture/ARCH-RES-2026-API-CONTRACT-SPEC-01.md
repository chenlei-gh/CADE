# ARCH-RES-2026-API-CONTRACT-SPEC-01: 结构化 API 契约提取与证据关联可行性规范

> **状态**: `ARCHIVED_TECHNICAL_RESERVE`（技术储备归档）  
> **日期**: 2026-10-22  
> **基准版本**: CATIA V5-6R2018 (B28) SDK Headers, Refman HTML, shipped `.dic`, UseCase `.cpp`  
> **兼容性定级**: `ARCHITECTURAL_COMPATIBILITY_CONFIRMED_BY_DESIGN`（设计解耦，未宣称集成回归通过）  
> **执行约束**: 本规范仅作为架构技术储备归档；**主干代码暂不实现、不合入，现有检索索引与门禁保持原状**。未来若启动工程实现，须以此规范为基准并重新获得明确授权。

---

## 1. 背景与缘起

在排查 `CATIVisu::GiveRep()` 的方法级索引与调用链问题时，确认了以下事实：
1. **现有检索能力正常**：`GiveRep` 在 CADE 的 `MethodIndex` 中已收录（`CATIVisu::GiveRep OK`），SDK 头文件和官方样例均有收录，不是索引遗漏。
2. **能力边界明确**：现有 `MethodIndex` 为轻量级方法名集合（`Set[str]`），底层 `caadoc_index.json`（Schema 2）虽保存了部分原始文本，但未向上层暴露类型化的完整结构化契约（返回类型、参数结构、参数方向、Ownership/生命周期说明等）。
3. **调用链提升门禁有意关闭**：`ChainExplorer` 输出 `root_matched_metadata_unverified`，Kernel 仅在 `consistent` 下晋升，此为阶段性安全门禁，不是 GiveRep 缺陷。
4. **单点修补被否决**：不应为 `GiveRep` 单个方法在索引或门禁中打补丁，而应将“从方法名索引发展为结构化 API 契约视图”作为独立的架构课题进行可行性研究。

---

## 2. 核心架构原则

为防止未来开发引入歧义或脏数据，确立以下 7 条不可逾越的架构原则：

1. **可选视图原则（View, Not Database）**：结构化契约作为现有 CAADoc 原始事实索引上的**可选结构化视图（Optional Contract View）**，不建立独立的事实数据库。
2. **物理声明与查询视图分离（Declaration vs. Query Scenario）**：
   - **API Declaration**：只代表类在头文件中真实的物理声明，拥有唯一的真实归属（`declared_in`）。
   - **API Query Scenario**：代表调用者视角的多态查询视图，包含继承链上溯和适配器提示，**绝不向子类虚构复制父类方法**。
3. **三源分工与证据原则（Three-Source Evidence Model）**：
   - **Header**：证明“语法与声明存在性”（返回类型、参数列表、const、修饰符）。
   - **Refman**：证明“官方文档语义”（参数方向 `[in]/[out]`、返回值说明、角色说明）。
   - **UseCase**：证明“真实调用上下文证据”（出现样例、实际调用代码片段、上下文引用）。
   - **严禁越权推断**：任何单一数据源不得越权断言其他数据源的职责范围。
4. **语法解析保守降级原则（Conservative Syntax Parsing）**：遇到宏展开、复杂模板、函数指针等复杂语法时，必须主动降级为 `UNPARSED` 或 `AMBIGUOUS`，保留原始字符串，严禁无证据猜测。
5. **Ownership 保守原则（Default UNKNOWN）**：
   - 所有对象的生命周期与释放责任默认一律为 `UNKNOWN`。
   - 只有在 Refman 或样例注释中存在可定位、可复核的显式官方文本（如 `"do not release"`、`"must be released by caller"`）时才允许提升状态。
   - 0% 误判是持续验证红线，宁可 100% 保持 `UNKNOWN`，也绝不能向下游输出错误的释放指令导致运行时内存崩溃。
6. **错误关联率独立核算原则（Mis-attribution Independence）**：三源数据 join 时的错误关联率（特别是同名重载错配）必须独立于单源解析准确率单独统计，作为高危指标严密监控。
7. **现有系统零破坏原则（Non-Invasive Architecture）**：新契约系统不得改变现有 `MethodIndex.method_exists()` 的轻量三态（`True / False / None`）逻辑，不得让 `CodeVerifier` 承担复杂的 C++ 语法分析负担。

---

## 3. 数据模型与唯一性规范

### 3.1 样本与声明的唯一标识符（UID）

为消除重载方法与跨版本混淆，所有物理声明必须遵循以下规范化 UID：

$$\text{UID} = \text{Owner}\text{::}\text{Method}(\text{NormalizedParams})@\text{Framework}@\text{SDKVersion}$$

*示例*：
- `CATIVisu::GiveRep()@Visualization@B28`
- `CATFrmEditor::Create(CATCommand*)@ApplicationFrame@B28`
- `CATFrmEditor::Create(CATCommand*,CATString&)@ApplicationFrame@B28`

### 3.2 数据结构解耦模型

```
API Declaration (物理声明事实)
    ├── uid: string
    ├── owner: string
    ├── declared_in: string
    ├── raw_signature: string
    ├── parsed_signature: {
    │     return_type: string,
    │     method_name: string,
    │     parameters: [ { type: string, name: string, default_val: string } ],
    │     is_const: bool,
    │     is_pure_virtual: bool
    │   }
    ├── header_path: string (CATIA_INSTALL 相对路径)
    ├── header_line: int
    └── syntax_tier: T1-A | T1-B | T1-C | T2

API Documentation (官方文档语义事实)
    ├── declaration_uid: string
    ├── refman_page: string
    ├── method_anchor: string
    ├── parameter_directions: [ { name: string, direction: IN | OUT | INOUT | UNSPECIFIED } ]
    ├── return_description: string
    ├── role_description: string
    └── ownership_claim: {
          state: DO_NOT_RELEASE | CALLER_MANAGED | CONTAINER_MANAGED | UNKNOWN,
          evidence_text: string,
          evidence_location: string
        }

API Usage Evidence (样例实证事实)
    ├── declaration_uid: string
    ├── usecase_entries: [
          { file: string, line: int, receiver_expr: string, context_snippet: string }
        ]

API Contract View (对外查询视图)
    ├── query_target: string (例如 CATI3DGeoVisu)
    ├── method: string (例如 GiveRep)
    ├── resolved_declaration: API Declaration
    ├── resolved_documentation: API Documentation
    ├── resolved_usage: API Usage Evidence
    ├── inheritance_path: [ string ] (例如 [CATI3DGeoVisu, CATIVisu])
    ├── adapter_hint: string (例如 CATExtIVisu，提取自 @CAA2Usage，不作为 C++ 基类)
    └── verification_verdict: GROUNDED | AMBIGUOUS | UNPARSED
```

---

## 4. 语法解析与消歧规则

### 4.1 Header 语法解析分级 (Syntax Tiers)

| 级别 | 语法范围 | 允许提取字段 | 降级行为 |
|:---|:---|:---|:---|
| **T1-A** | 标准无宏、无函数指针、无复杂模板的虚函数与导出成员函数 | 完整结构化签名（返回类型、参数类型/名称、const、=0） | 不允许失败 |
| **T1-B** | 带有标准导出宏（如 `ExportedByXxx`）的类与方法声明 | 结构化签名，宏剥离并独立记录 | 无法识别的宏降为 T2 |
| **T1-C** | 位于预处理器条件分支（如 `#if / #ifdef`）中的声明 | 结构化签名，显式记录预处理条件上下文 | 嵌套过深时标记条件未定 |
| **T2** | 宏生成方法（`CATDeclareInterface` 等展开）、函数指针参数、深度模板嵌套、行内注释破坏 | 仅保留原始单行字符串，标记 `UNPARSED` 或 `AMBIGUOUS` | 严禁强行正则拆解字段 |

### 4.2 Refman DOM 结构与重载消歧规则

1. **DOM 结构定位**：
   - 提取 Methods Detail 区的 `<a name="...">` 锚点块。
   - 参数方向严格从 `<dt><b>Parameters:</b></dt>` 下对应参数名 `<dt><tt>paramName</tt></dt>` 后的 `<dd>` 文本中提取前缀 `[in]`, `[out]`, `[in, out]`；无前缀的一律标为 `DIRECTION_UNSPECIFIED`，**严禁跨参数文本全局正则搜寻**。
   - 返回值说明严格从 `<dt><b>Returns:</b></dt>` 下紧邻的 `<dd>` 提取。
2. **重载与同名消歧**：
   - 关联 Header 声明与 Refman 方法时，必须使用 `(Owner, Method, NormalizedParams)` 三元组联合寻址。
   - 若参数列表无法 100% 对应，该方法标记为 `OVERLOAD_AMBIGUOUS`，阻断参数方向的自动绑定，防止不同重载参数错位。

### 4.3 继承与适配器隔离

- **继承关系**（`base_classes`）：仅源于 `class A : public B` 语法，用于查询时的方法沿链上溯。
- **适配器提示**（`adapter_hint`）：源于头文件注释 `@CAA2Usage U4 CATExtIXxx`，仅作为代码生成时的架构建议，**严禁混入 C++ 继承图参与方法存在性判定**。

---

## 5. 验收指标体系与离线测试口径规范

未来验证必须严格区分以下统计口径，禁止将选择性指标与全样本指标混用：

| 评估维度 | 指标名称 | 计算公式 | 质量目标 |
|:---|:---|:---|:---:|
| **Header 声明** | 声明解析全样本覆盖率 | $\frac{\text{PASS}}{\text{Total Declarations}}$ | $\ge 85\%$ |
| | 声明解析选择性准确率 | $\frac{\text{PASS}}{\text{Total} - \text{UNPARSED}}$ | $\ge 98\%$ |
| | 声明解析错误率 | $\frac{\text{FAIL}}{\text{Total Declarations}}$ | $\le 2\%$ |
| **Refman 语义** | 参数方向适用样本覆盖率 | $\frac{\text{PASS}}{\text{Applicable Refman Declarations}}$ | $\ge 85\%$ |
| | 参数方向选择性准确率 | $\frac{\text{PASS}}{\text{Evaluated Declarations}}$ | $\ge 98\%$ |
| **多源整合** | 全样本三源错误关联率 | $\frac{\text{MIS\_ATTRIBUTED}}{\text{Total Declarations}}$ | $\le 2\%$ |
| **生命周期** | Ownership 判定误判率 | $\frac{\text{FALSE\_POSITIVE\_LIFECYCLE}}{\text{Total Declarations}}$ | **$= 0\%$ (绝对红线)** |
| | Ownership 证据提升率 | $\frac{\text{PROMOTED\_EVIDENCE}}{\text{Total Declarations}}$ | 不设硬性下限（宁缺毋滥） |

---

## 6. 100 API 离线原型基准（Benchmark 基线结果备忘）

在针对 CATIA B28 本地 SDK（484 个 Frameworks）与 Refman HTML 进行的 100 个分层抽样离线测试中（覆盖简单类型、指针修饰、`_var`、重载、非纯虚实现类、`@return`、明确 Ownership、COM 基础、继承边界 9 大类别），实测指标如下：

- **声明解析全样本覆盖率**: **89.0%** (89/100)
- **声明解析选择性准确率**: **97.8%** (89/91)
- **声明解析错误率**: **2.0%** (2/100，根因为自定义导出宏挤压及行内注释污染)
- **参数方向适用样本覆盖率**: **88.5%** (69/78)
- **参数方向选择性准确率**: **98.6%** (69/70)
- **全样本三源错误关联率**: **1.0%** (1/100，根因为同名重载缺少参数类型归一化导致锚点误绑)
- **Ownership 实测误判率**: **0.0%** (0/100，7 个样本依据文本证据成功提升，93 个样本正确保持 `UNKNOWN`)

*注：上述测试基线证实了在严格遵守降级与隔离原则下，增量构建结构化契约的工程可行性。*

---

## 7. 结论与后续指引

1. **当前处置**：本课题正式闭环并冻结为技术储备。主干代码不修改、缓存不重建、现有轻量索引不改动。
2. **GiveRep 结论**：维持关闭状态。`GiveRep` 属于现有架构正常工作范畴，头文件与样例完备，无需进行单点代码修补。
3. **唤醒条件**：未来仅当 CADE 核心流水线在实际项目中遇到高频的“返回类型/参数方向错误生成”或“显式内存管理错误排错损耗”，且取得明确开发授权时，方可以本 Spec 为输入启动工程化集成。
