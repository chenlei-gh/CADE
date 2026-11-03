# PLAN-P0-INTENT-ROUTING-AND-RUNTIME-EVIDENCE: CADE 业务意图链路修复与 Runtime 分层证据实施计划

> **状态**: `PROPOSED_ACTIVE_PLAN`（待执行实施计划）  
> **创建日期**: 2026-11-03  
> **目标基准**: Commit `0711a055`（主干 `main`）  
> **涉及核心缺陷**: 
> 1. P0-1 业务意图到 CAA 构件上下文映射断链与暴力 fallback
> 2. P0-2 CATIA Runtime 虚假启动判定与 Add-in 挂载证据缺失  
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
