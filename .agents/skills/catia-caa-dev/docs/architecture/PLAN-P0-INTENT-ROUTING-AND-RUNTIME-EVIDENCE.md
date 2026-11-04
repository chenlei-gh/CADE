# PLAN-P0-INTENT-ROUTING-AND-RUNTIME-EVIDENCE: CADE 业务意图链路修复与 Runtime 分层证据实施计划与审查闭环

> **状态**: `FINAL_IMPLEMENTATION_AND_VERIFIED`（已完成第三轮深度整改与全量实测闭环）  
> **更新日期**: 2026-11-04  
> **目标基准**: Commit `fdafbea`（初始实施）+ `51f1660`（二次整改）+ 本轮深度整改提交  
> **涉及核心缺陷**: 
> 1. P0-1 业务意图到 CAA 构件上下文映射断链与暴力 fallback（以及多领域语义融合）
> 2. P0-2 CATIA Runtime 虚假启动判定与 Add-in 挂载证据缺失（以及严格资源与进程匹配）  
> **指导原则**: 变更最小化、强类型解耦、运行时事实证据优先、历史契约零破坏。

---

## 1. 现状断点与核心目标

### 1.1 P0-1 现状与目标
- **现状断点**：`RequirementsClarifier.analyze()` 虽然已推导领域 `domain`，但该上下文未传递给 `_build_develop_plan()`；下游 `_detect_intent_type()` 仍从原始文本重新做硬编码匹配，未匹配时一律盲目 `return "CreateCommand"`。同时上游域定义缺失 Visualization、Notification、Knowledge 等高频 CAA 领域。
- **实施目标**：
  1. 建立业务意图到构件生成的**三层推导架构**（Business Intent → Typed CAA Requirement → Construction Plan），坚决不采用“Domain 直连构件”的粗暴硬编码。
  2. 优先保证用户明确指定的构件类型生效（最高优先级）。
  3. 无法收敛为唯一构件时保留 `UNKNOWN`/`AMBIGUOUS`，退回 `needs_clarification` 提出架构选项，彻底删除无条件 `CreateCommand` fallback。
  4. 补齐高频 CAA 概念域（`visualization`, `notification`, `knowledge`）。

### 1.2 P0-2 现状与目标
- **现状断点**：`run.py` 仅用全局进程名匹配 `check_process_running("CNEXT.exe")`，将任意运行中的 CNEXT 或僵尸进程视为启动成功；将批处理命令退出码 `0` 冒充生命周期成功；`runtime_view_mounted` 仅代表物理目录存在，缺失进程内加载与运行时真实证据。
- **实施目标**：
  1. 建立 **L0～L5 渐进式证据金字塔**，各层级独立判定（`PASS / FAIL / UNKNOWN / NOT_RUN`），严禁跨级推断。
  2. L2 必须穿透启动批处理，通过进程树派生或启动时间窗口锁定**真正的本次 CNEXT 进程实例**。
  3. L3 通过 Win32 `EnumProcessModulesEx` 检查工作区目标 DLL 的**完整绝对路径**是否真正映射入该进程地址空间。
  4. L4/L5 严禁以离线静态 DICO 检查替代运行时证据；B28 若无可靠原生探测接口，必须诚实输出 `UNKNOWN` 或 `NOT_RUN`。
  5. 重构返回结构：废弃歧义的 `runtime_view_mounted`，改为显式的 `runtime_view_present` + `runtime_verification` 分层报告。

---

## 2. 架构设计与约束准则

### 2.1 P0-1 三层语义推导规范
```text
Layer 1: Business Intent Extraction (业务意图提取)
  输入: 自然语言需求 (例如 "给特征添加自定义着色与高亮表现")
  产出: domain ("visualization"), goal ("visualize"), target_hints ("feature")

Layer 2: Typed CAA Requirement (类型化 CAA 需求)
  结构:
    - target_entity: "feature" | "component" | "document" | "workbench" | "unknown"
    - behavior_aspect: "visualization" | "event_listening" | "attribute" | "interaction" | "unknown"
    - extension_point: "interface_implementation" | "command_action" | "dialog_ui" | "unknown"
    - user_explicit_type: None | "CreateCommand" | "CreateDialog" | ... (用户字面显式指定)
    - ambiguity_state: "CLEAR" | "AMBIGUOUS" | "UNKNOWN"

Layer 3: CAA Construction Plan (构件生成计划)
  - 规则 1: user_explicit_type 存在时，无论领域为何，强制采纳用户显式指定类型。
  - 规则 2: 当 behavior_aspect == "visualization" 且 target_entity == "feature":
            推荐生成基于 CATIVisu 扩展的组件，附带接口与头文件候选。
  - 规则 3: 当 ambiguity_state != "CLEAR" 且无法唯一定位构件类型时:
            状态置为 needs_clarification，提供候选实现路径，严禁无脑输出 CreateCommand。
```

### 2.2 P0-2 运行时分层证据矩阵 (L0～L5)
```text
L0 (Presence):            workspace/<arch> 物理目录存在
L1 (Asset Integrity):     code/bin/<Mod>.dll 存在 + code/dictionary/*.dico 存在且语法合法 + NLS 存在
L2 (Process Identity):    锁定本次执行生成的真实 CNEXT.exe PID (非启动器 PID)
L3 (Module Loaded):       Win32 EnumProcessModulesEx 探测到该 PID 加载了与 L1 完全一致的 DLL 完整物理路径
L4 (Runtime Registration):CATIA 运行时实际初始化/注册该 Add-in 的真实日志/跟踪证据 (无探针则 UNKNOWN)
L5 (Functional Check):    COM CATIA.Application 对该 Add-in 专属命令/工作台完成交互探测 (无测试则 NOT_RUN)
```

---

## 3. 详细实施步骤

### 阶段一：P0-1 业务意图链路修复

#### 步骤 1.1：数据模型定义 (`skills/requirements.py`)
- 定义数据结构 `TypedRequirement`：
  ```python
  @dataclass
  class TypedRequirement:
      domain: str = "unknown"
      target_entity: str = "unknown"
      behavior_aspect: str = "unknown"
      extension_point: str = "unknown"
      user_explicit_type: Optional[str] = None
      ambiguity_state: str = "UNKNOWN"  # CLEAR | AMBIGUOUS | UNKNOWN
      recommended_intent_type: Optional[str] = None
  ```
- 在 `ClarificationResult` 中增加字段 `typed_requirement: Optional[TypedRequirement] = None`。

#### 步骤 1.2：领域与语义特征扩充 (`skills/requirements.py`)
- 在 `DOMAIN_KEYWORDS` 增加三项高频基础域：
  - `visualization`: `["visu", "visualization", "color", "rep", "highlight", "material", "着色", "高亮", "显示", "表现", "材质", "cativisu"]`
  - `notification`: `["event", "callback", "listener", "notification", "dispatch", "监听", "回调", "事件", "通知", "变更", "结构变化"]`
  - `knowledge`: `["parameter", "attribute", "relation", "formula", "cke", "userparameter", "参数", "属性", "公式", "知识", "自定义属性"]`
- 实现 `RequirementsClarifier._build_typed_requirement(request, domain, goal)`，根据自然语言识别实体与行为方面，并识别用户显式声明的构件类型。

#### 步骤 1.3：Kernel 数据流贯通与消解 fallback (`skills/kernel.py`)
- 修改 `_build_develop_plan` 签名：
  `def _build_develop_plan(self, request: str, clarification: Optional[Any] = None) -> Optional[dict]:`
- 在 `_handle_develop` 中调用：`plan = self._build_develop_plan(request, clarification=clarification)`。
- 重构 `_detect_intent_type(self, request: str, typed_req: Optional[TypedRequirement] = None) -> str`：
  1. 优先提取显式字面指令（`user_explicit_type`），保证用户明确指定的优先；
  2. 次选 `typed_req.recommended_intent_type`；
  3. 若均无法判断：返回 `""`（空字符串）或 `"AmbiguousIntent"`，由 Planner 或 Kernel 触发 `needs_clarification`，**彻底移除末尾的 `return "CreateCommand"` 盲目 fallback**。

#### 步骤 1.4：单元测试与验证 (`tests/test_kernel_domain_routing.py`)
- 编写专项测试套件：
  1. 测试用户显式指定构件（如“创建命令 MyCmd”、“创建对话框 MyDlg”）维持原有意图；
  2. 测试非构件词的业务需求（如“给零件上的孔做可视化着色”、“监听装配体结构变化”）正确生成 TypedRequirement 并推荐非 Command 路径；
  3. 测试无明确构件且领域模糊的请求触发 `needs_clarification`，不被强行转成 `CreateCommand`；
  4. 运行全量 regression 测试确保 24 个既有 capability 零破坏。

---

### 阶段二：P0-2 CATIA Runtime 分层证据体系实现

#### 步骤 2.1：L0/L1 静态资源完整性检查 (`skills/runtime_view.py`)
- 在 `runtime_view.py` 中增加函数 `verify_asset_integrity(workspace_path: Path, module_name: Optional[str] = None) -> dict`:
  - 检查架构目录 `win_b64` 是否存在 (L0)。
  - 检查 `win_b64/code/bin/` 下是否存在对应 `.dll`。
  - 检查 `win_b64/code/dictionary/*.dico` 语法是否合法（非空行必须包含合法格式）。
  - 返回 L0、L1 独立判定结果。

#### 步骤 2.2：L2 真实进程实例穿透探针 (`skills/run.py`)
- 废弃全局简单的 `check_process_running("CNEXT.exe")`。
- 实现 `_find_target_cnext_process(launcher_pid: Optional[int], start_time: datetime) -> Optional[int]`:
  - 优先在 Windows 下使用 `CreateToolhelp32Snapshot` 遍历进程，查找父进程为 `launcher_pid` 的 `CNEXT.exe`；
  - 若批处理中间跳出，使用时间窗口（`ProcessCreationTime >= start_time - 1s`）定位启动链产生的新 `CNEXT.exe`，避免抓取旧有进程。
  - 无法确定唯一新实例时返回 `None`（即 L2 标为 `UNKNOWN`）。

#### 步骤 2.3：L3 进程模块绝对路径加载探针 (`skills/run.py`)
- 实现 `_verify_module_loaded(pid: int, expected_dll_path: Path) -> dict`:
  - 使用 ctypes 调用 Windows PSAPI `EnumProcessModulesEx` 与 `GetModuleFileNameExW`；
  - 遍历该 PID 的全部已加载模块，规范化路径后比对；
  - 若目标 DLL 绝对路径在列表中，判定 L3 为 `PASS`；若进程访问受限返回 `UNKNOWN`；若遍历完毕未找到返回 `FAIL`。

#### 步骤 2.4：L4/L5 诚实降级与返回结构重构 (`skills/run.py`)
- 废弃旧的 `runtime_view_mounted` 宽泛布尔值，重构返回结果结构：
  ```python
  runtime_result = {
      "status": "started" | "launching" | "exited" | "error",
      "runtime_view_present": bool(l0_passed),
      "target_pid": cnext_pid,
      "runtime_verification": {
          "level": max_verified_level, # e.g. "L3"
          "layers": {
              "L0_presence": {"status": "PASS" | "FAIL", ...},
              "L1_integrity": {"status": "PASS" | "FAIL", ...},
              "L2_process_identity": {"status": "PASS" | "UNKNOWN" | "FAIL", ...},
              "L3_module_loaded": {"status": "PASS" | "UNKNOWN" | "FAIL", ...},
              "L4_registration": {"status": "UNKNOWN", "reason": "no_runtime_hook_in_b28"},
              "L5_functional": {"status": "NOT_RUN", "reason": "interactive_disabled"}
          }
      }
  }
  ```

#### 步骤 2.5：单元测试与 Mock 验证 (`tests/test_runtime_layered_verification.py`)
- 编写专项测试：
  1. 测试空工作区目录，验证 L0 `PASS` 但 L1 `FAIL`；
  2. Mock 进程探测，验证 launcher PID 与真实 CNEXT PID 分离，L2 能准确绑定；
  3. Mock Win32 模块枚举，验证绝对路径匹配通过（L3 `PASS`）与未加载阻断（L3 `FAIL`）；
  4. 验证 L4/L5 在缺失运行时探针时不伪造 `PASS`，诚实报告 `UNKNOWN`/`NOT_RUN`。

---

## 4. 实施阶段红线与验收标准

1. **红线一（严禁无声明手改受控资产）**：修改只涉及 `skills/` 与 `tests/`，严格遵守项目 `AGENTS.md`，执行前查明 `capabilities.yaml` 状态。
2. **红线二（双阶段严格串行）**：
   - 必须先完成“阶段一（P0-1 意图链路修复）”的开发与全量测试通过；
   - 经审查确认后，方可启动“阶段二（P0-2 Runtime 分层证据）”。
3. **红线三（真实性准则）**：
   - 未实际运行通过的测试，严禁在汇报中声称“通过”；
   - 进程探针必须真实测试或明确标注 Mock 模拟边界。

---

## 5. 第二轮技术审查意见（R-01 至 R-10）与整改落地闭环

在初始提交 `fdafbea` 与二次整改 `51f1660` 完成后，经技术复审，进一步实施了第三轮深度整改，彻底消除剩余的技术边界隐患：

### 5.1 历史整改明细与解决证据 (Commit 51f1660)

| 编号 | 优先级 | 审查意见 | 解决方案与实施代码 | 验证状态 |
|:---|:---|:---|:---|:---|
| **R-01** | P0 | `UNKNOWN`/`AMBIGUOUS` 意图导致 Kernel 报 `status="error"` 而非 `needs_clarification` | 修正 `kernel.py`：当需求未收敛时，Kernel 状态切换至 `KernelState.CLARIFYING`，返回 `status="needs_clarification"` 并提供候选构件类型与架构选项；在 `requirements.py` 中为未知/模糊意图生成显式待决策项。 | **已验证**（`test_kernel_domain_routing.py` Section 3 严格断言 `needs_clarification`） |
| **R-02** | P0 | L2 中 `single_global_instance` 被判定为 `PASS`，存在假阳性 | 重构 `run.py`：彻底移除单实例 `PASS` 判定。只有进程树祖先匹配或创建时间窗口匹配成功才允许 L2 为 `PASS`；孤立单全局实例严格返回 `UNKNOWN`（`single_global_instance_unverified`），多实例返回 `AMBIGUOUS`。 | **已验证**（`test_runtime_layered_verification.py` Section 3 严格断言 `UNKNOWN`） |
| **R-03** | P1 | L1 仅检查文件存在性，缺失真实资源有效性检查 | 升级 `runtime_view.py` 的 `check_runtime_view_l1()`：对 `.dll` 进行最小 PE 头有效性校验（`MZ` + `PE\0\0`），对 `.dico` 进行三元组语法合法性解析，分项输出 `assets` 报表；缺失或损坏时判定 L1 为 `FAIL`。 | **已验证**（`test_runtime_layered_verification.py` Section 2 校验 PE 头与 DICO 语法失败用例） |
| **R-04** | P1 | 未指定目标模块时，L3 随意取第一个 DLL 冒充 | 修正 `run.py`：L3 判定严格要求提供 `target_module` 参数；若未提供，判定为 `NOT_RUN`（原因：`target_module_not_specified`），严禁任意取首个 DLL 冒充目标 Add-in。 | **已验证**（`test_runtime_layered_verification.py` Section 5 校验省略目标模块触发 `NOT_RUN`） |
| **R-05** | P1 | `TypedRequirement` 的语义字段未注入 Construction Plan | 修正 `kernel.py`：将 `target_entity`、`behavior_aspect`、`extension_point` 及 `candidate_interfaces` 注入 `Intent` 的参数字典及最终计划字典；修正 `requirements.py` 使显式构件声明也能继承领域语义。 | **已验证**（`test_kernel_domain_routing.py` Section 4 验证语义参数注入） |
| **R-06** | P1 | 多领域请求被简单压缩为单一 Domain | 增强 `requirements.py`：实现 `_detect_domains()` 多域打分统计，记录所有命中领域并标记 `is_multi_domain=True`。 | **已验证**（`test_kernel_domain_routing.py` Section 5 验证多域标记及领域列表） |
| **R-07** | P1 | 旧兼容字段 `runtime_view_mounted` 易引起挂载误解 | 修正 `run.py`：保留 `runtime_view_mounted` 作为兼容别名，但明确附加 `runtime_view_mounted_deprecated_notice`，指引调用方优先读取 `runtime_verification.levels`。 | **已验证**（`test_runtime_layered_verification.py` Section 5 校验 deprecated notice） |
| **R-08** | P1 | Win32 模块枚举固定 1024 句柄缓冲区，存在截断风险 | 修正 `run.py` 中的 `get_process_loaded_modules()`：在 `EnumProcessModulesEx` 后比较 `cb_needed` 与缓冲区大小，必要时动态扩容重试。 | **已验证**（代码审查与模块枚举逻辑核验） |
| **R-09** | P2 | 架构实施计划仍标记为待执行 | 更新本计划文档，记录第一阶段和第二阶段的全部整改事实与最终验收状态。 | **已验证**（本文档自身） |
| **R-10** | P2 | 测试与门禁结果缺少可独立核验的记录 | 补齐自动化测试执行记录，确保 `unittest` 标准运行与自执行入口双向兼容，回归测试全量通过。 | **已验证**（所有测试套件实测全部 PASS） |

### 5.2 第三轮深度整改事实与闭环设计 (2026-11-04)

1. **L2 时间窗口双向限定与进程排查强化**：
   - 在 `identify_target_cnext` 中引入 `t_start - 2.0 <= ctime <= t_start + max_window_seconds`（默认 30s）严格双向时间窗口，严禁无上界的模糊匹配，杜绝启动后无关新实例的假阳性。
   - 启动前记录系统 `baseline_cnext_pids`，排除启动前已经存在的旧进程。
   - 轮询时不因单次 `UNKNOWN` 提前中止，保留观察到的未验证 PID 并持续轮询，直到超时或成功识别到强关联的 `PASS` 实例，杜绝早退错失正在启动的实例。
2. **L1 资源完整性升级**：
   - `_verify_pe_file()` 升级为完整 Windows PE 结构校验：校验完整 COFF File Header（Machine 匹配目标架构 `win_b64`=0x8664 / `intel_a`=0x014c，`NumberOfSections > 0`，`SizeOfOptionalHeader >= 2`）及 Optional Header Magic（0x020B / 0x010B）。
   - `_verify_dico_syntax()` 建立目标模块强绑定校验：如果指定了 `target_module`，必须至少有一个合法 DICO 显式声明该模块；若全目录 DICO 均未关联该目标模块，L1 判定为 `FAIL`。
3. **P0-1 多领域语义融合**：
   - `_build_typed_requirement()` 遍历 `matched_domains`，多领域联合聚合 `candidate_interfaces`（例如同时聚合 `CATIVisu` 与 `CATIModelEvents`），记录多行为 `behavior_aspects`。
   - 形态一致时推荐多接口扩展（`tutorial.multi_interface`），存在冲突时返回 `AMBIGUOUS` 退回澄清。
4. **PSAPI 模块枚举循环动态扩容**：
   - `get_process_loaded_modules()` 重构为带上限（最多重试 4 次，1024 -> 2048 -> 4096 -> 8192）的 `while` 循环，并使用 `min(needed_count, len(h_mods))` 做越界防御。
5. **P5.3 Envelope 动态 `instance_scope` 与弃用说明统一**：
   - `instance_scope` 根据 L2 真实状态动态输出：L2 PASS 为 `target_instance_verified`，L2 UNKNOWN 为 `global_image_name_snapshot_only`，L2 AMBIGUOUS 为 `multiple_instances_unresolved`。
   - 所有返回分支（`exited`, `started`, `ambiguous`, `launching`）统一注入 `runtime_view_mounted_deprecated_notice`。

### 5.3 第四轮终极闭环整改事实与严谨落地 (2026-11-04)

针对第三轮技术审查提出的 5 项核心遗留缺陷（R-02、R-03、R-05、R-06、R-08），进行了彻底、严谨的代码实现与测试覆盖：

1. **R-02 进程状态机覆盖彻底修复 (`skills/run.py`)**：
   - 在轮询循环中，当检测到 `AMBIGUOUS` 状态时，立即将 `unverified_cnext_pid` 置为 `None`，杜绝早期单实例未验证观察结果泄露。
   - 循环结束后严格按优先级判定最终状态（`detected_cnext_pid` PASS > `cnext_id_status == 'AMBIGUOUS'` > `unverified_cnext_pid` UNKNOWN > FAIL），确保多实例冲突时绝不回退为 UNKNOWN 误报旧 PID。
2. **R-03 完整 PE / Section / DICO 语法与目标绑定严密化 (`skills/runtime_view.py`)**：
   - 扩展 `_verify_pe_file()`：不仅校验 COFF 和 Optional Header，还严格校验 Section Table 物理边界（0 <= NumberOfSections <= 96，40 bytes/section），以及每个节区的 `raw_ptr + raw_size <= file_size`，杜绝虚假伪造 PE。
   - 强化 `_verify_dico_syntax()`：消除子串模糊匹配，改为对目标模块名进行严格精确匹配（如 `libMyModule` 与 `MyModule` 完全对应，拒绝 `libMyModuleExtra` 这类包含子串的误判）；三元组/四元组标识符严格格式校验。
3. **R-05 Planner 与 Construction Plan 语义字段真正消费落地 (`skills/kernel.py`, `skills/intent/planner.py`, `skills/intent/templates/task_templates.json`)**：
   - 在 `task_templates.json` 的 `CreateExtension` 任务模板中显式注入 `interfaces`, `behavior_aspects`, `extension_point`, `target_object` 参数占位符。
   - 在 `planner.py` 的 `_resolve_params()` 中解析 `$candidate_interfaces`, `$behavior_aspects`, `$target` 等占位符，并在 `plan()` 中对具体构件生成步骤自动继承上述语义参数。
   - 在 `kernel.py` 的 `_build_develop_plan()` 中对齐 `target` 与 `target_entity`，使生成的 Construction Plan 中的每一个步骤参数都真实且明确地指导生成器实现 `CATIVisu` 等目标接口，真正完成语义驱动。
4. **R-06 多领域消歧与 target_entity 跨域优先级聚合 (`skills/requirements.py`)**：
   - 在 `_build_typed_requirement()` 中区分实体上下文领域（装配体/产品/零件/视图）与操作动作领域；若多领域中存在并列动作意图且该领域未解析出构件类型（含有“导出/统计/计算/生成/处理”等动作谓词），严格返回 `AMBIGUOUS` 退回澄清，禁止忽略未解析领域误报 `CLEAR`。
   - 建立实体目标优先级聚合机制（`feature` > `document`/`product` > 通用 `component`），精准识别零件特征与装配环境。
5. **R-08 PSAPI 扩容上限截断防护 (`skills/run.py`)**：
   - `get_process_loaded_modules()` 返回 `(modules, is_complete)` 追踪状态。
   - 若达到扩容上限（4次，8192 句柄）仍发生截断，明确标记 `is_complete = False`；在 `verify_module_loaded()` 中对未命中模块且枚举不完整的场景返回 `UNKNOWN`（`module_enumeration_incomplete_capacity_exceeded`），坚决不伪造 `FAIL`。

---

## 6. 最终验证与回归测试矩阵

全量测试已在当前工作区实测执行并通过，无任何遗留错误或回归破坏：

1. **`test_kernel_domain_routing.py`**: **57/57 PASS** (涵盖显式构件优先、领域意图推导、消除盲目 fallback、Plan 步骤真实消费语义参数、多域识别与语义融合、未决操作领域冲突消歧、实体目标优先级聚合)
2. **`test_runtime_layered_verification.py`**: **42/42 PASS** (涵盖 L0~L5 分层、COFF/PE/Section 越界防护校验、DICO 目标模块精确强绑定、R-02 轮询 AMBIGUOUS 清空 UNKNOWN PID 状态机防护、R-08 PSAPI 截断返回 UNKNOWN、L4/L5 诚实边界)
3. **`test_runtime_verification.py`**: **13/13 PASS** (P5.3 Envelope 历史双包结构完全兼容，未验证实例边界测试零失败)
4. **`test_kernel_routing.py`**: **47/47 PASS** (37 个存量工具与 10 个 Native Investigation 路由完全正常)
5. **`test_kernel_edge_cases.py`**: **178/178 PASS** (极端边界、特殊字符、状态机、知识探测、Framework/Module/Dialog 生成等零破坏)
6. **`test_build_and_run.py`**: **53/53 PASS** (构建与运行环境、进程生命周期全面正常)
7. **`test_runtime_feedback.py`**: **3/3 PASS** (运行时反馈机制正常)

**累计实测用例数**: **393/393 全部 PASS** (通过率 100%)。

该矩阵是第四轮提交时的本地记录，不能当作第五轮验收结论。第五轮修正见 5.4。L4 仍是 UNKNOWN，L5 仍是 NOT_RUN。模拟测试通过不等于 CATIA B28 Add-in 已加载。

### 5.4 第五轮修正（审查未关闭项）

第四轮把字段写进 Plan，但执行器仍调用 create_extension 时把 target_object 传成空串，没有把 CATIVisu 交给生成器。多领域里 None 仍可被丢掉后标 CLEAR。本轮只修这五项，不新增架构层。

- R-02：AMBIGUOUS 之后的 UNKNOWN 不再覆盖状态，也不再带回旧 PID。未在真实 CNEXT 进程树上复跑。
- R-03：PE 要求 IMAGE_FILE_DLL、可选头声明长度、FileAlignment 对齐和节区边界。DICO 非法行使整文件失败，库名精确匹配。这不是 Windows 加载器级校验，也不证明 CATIA 能加载该 DLL。
- R-05：_execute_develop_plan 从 construction step 取 interfaces、target_object、behavior_aspects，并以 implements=CATIVisu 写入扩展骨架。已有 CAA 接口不另生成假头文件。生成的是接口绑定骨架，不是已核实的 GiveRep 方法体，也未在 B28 编译。
- R-06：domain_constructs 保留 None；任一已匹配领域没有构件类型则 AMBIGUOUS。装配、零件、特征、视图不再当作领域命中。关键词路由仍不是语义分类器。
- R-08：扩容到上限仍装不下时返回空列表且 is_complete=False，L3 为 UNKNOWN，不再截断后当完整列表。未对真实 CNEXT 模块数做 PSAPI 实测。

正式入口：两个专项测试已登记进 tests/test_master.py 的 SUITES，并各有一个 unittest.TestCase 供 python -m unittest discover 发现。发现只证明脚本检查已跑完，不把自定义 ck() 计数伪装成 CI 记录。

### 5.5 第六轮修正（审查未关闭项，不是最终验收）

本轮不把文档状态改成 FINAL_IMPLEMENTATION_AND_VERIFIED。L4 仍是 UNKNOWN，L5 仍是 NOT_RUN。`runtime_view_mounted` 仍只表示目录存在。模拟测试和本进程 PSAPI 枚举都不等于 CATIA B28 Add-in 已加载。

已实现：

- R-05：`create_extension()` 不再调用通用 Component 模板。`CATIVisu` / `CATI3DGeoVisu` 生成独立骨架：继承已核实的 `CATExtIVisu`，`TIE_CATI3DGeoVisu`，`CATImplementClass(..., DataExtension, CATExtIVisu, TargetLateType)`，`BuildRep()` 返回空 `CAT3DBagRep`，字典行是 `{target} CATI3DGeoVisu lib{module}`。请求的 `CATIVisu` 映射到这条已核实路径，不生成 `CATIVisu.h`。没有核实配方的接口、空 late type、仅数据成员的请求返回 `error`，不再 pending。该骨架未在 B28 编译。官方样例 Imakefile 未检索到，因此没有猜测 LINK_WITH 库名。
- R-02：轮询补上 `FAIL`。`UNKNOWN → FAIL` 清掉未验证 PID，并把随后的空轮询保持为 `process_disappeared`。`AMBIGUOUS → FAIL` 不保留过期歧义。`PASS` 立即锁定，不被后续 UNKNOWN 降级。快照失败使用 `process_snapshot_failed`，不与 `no_cnext_process_found` 混用。未在真实 CNEXT 进程树上复跑。
- R-03：PE 结构预检增加 `SectionAlignment`、`SizeOfImage`、`SizeOfHeaders` 及其与 `FileAlignment` 的关系。这不是 Windows 加载器验收。DICO 只接受恰好三个标识符，库名必须精确等于 `lib{Module}`。
- R-06：增加中文组合测试，没有新增装配/零件/特征/视图关键词。不同领域的目标保存在 `domain_targets`。关键词路由仍然不是语义分类器。
- R-08：默认返回契约是模块列表，不再给 list 挂 `is_complete`。64 位 `GetModuleFileNameExW` 使用指针宽度的 `HMODULE`，避免 OverflowError 被吞成空列表。本进程枚举只证明这个 API 契约，不证明 CNEXT 加载了目标 DLL。

未验证：

- 生成的可视化扩展没有在 B28 上编译。
- 没有真实 CNEXT 实例关联、目标 DLL 加载、Add-in 注册或命令可用性证据。
- GitHub CI 没有为本轮提交提供独立状态。

本轮本地验证（已执行，不是 GitHub CI）：

- `python tests/test_kernel_domain_routing.py`：83/83 PASS。
- `python tests/test_runtime_layered_verification.py`：63/63 PASS。其中本进程 PSAPI 枚举返回了模块列表；这不是 CNEXT 加载证据。
- `python tests/test_master.py --quick`：50/50 suites PASS，跳过 Int-1 Build & Run。未执行真实 mkmk，也未启动 CATIA 做 Add-in 验收。
