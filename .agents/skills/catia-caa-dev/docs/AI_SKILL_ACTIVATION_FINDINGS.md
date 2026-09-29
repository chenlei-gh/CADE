# CADE Skill 自动激活调查报告

**文档性质**: 调查记录（findings）。**不是** CADE 架构契约，**不是** ADR，**不是** 使用约定。
**Status**: Closed（2026-09-29）
**调查对象**: 为什么一次 CATIA/CAA 请求没有触发 `catia-caa-dev` skill 自动激活
**环境**: Zed 1.21.0（commit `33c95853ed2b6956f339733c63a8220964ecbeb6`），Windows
**结论效力**: 本文描述的机制属于 **AI 宿主平台行为**，不是 CADE 的设计决策。
**Supersedes**: 无。相关既有决策见 `ADR-CADE-UI-Semantic-Layer.md`（无关）与 commit `74742c3`（激活后的入口仲裁，保留有效）。

> ⚠️ **不得据此修改 CADE 架构。**
> 本文件存在的目的是：(1) 防止后续 agent 重复调查同一问题；(2) 防止把"宿主行为"误读为"CADE 缺陷"。
> 它**不构成**任何要求 CADE 实现"强制激活"的授权。

---

## 0. TL;DR

| 命题 | 结论 | 等级 |
|---|---|---|
| 宿主**不存在**强制注入 / 自动加载 skill 的机制 | 确认不存在 | 事实（源码） |
| 改 `SKILL.md` **正文**能影响「是否被调用」 | **不能**（正文在调用发生前不在上下文里） | 事实（源码） |
| `SKILL.md` 的 `triggers:` 字段有消费者 | **没有**（宿主不解析该字段） | 事实（源码） |
| 存在 always-apply / auto-load / 强制注入 | **不存在** | 事实（源码） |
| 能否配置某 skill 默认加载 | **不能** | 事实（源码） |
| 自然语言"请使用 CADE"是 guarantee | **不是**，只是 hint | 事实（源码 + 实测） |
| 上文一致、metadata 正确 ⇒ 一定激活 | **不成立**（观测到可见且被讨论仍不调用） | 事实（实测） |
| 本机 16 次 CADE 激活的证据形态 | 全部为 `skill` 工具主动调用；`/` 与 `@` 注入通道实测 **0 次** | 事实（实测） |
| 「是否调用 skill」由**模型**自主判断 | 行为上成立（16 次 CADE 激活全部为模型主动调用） | **推断**（源码只证明宿主无强制路径，未证明模型内部决策机制） |

**净结论**：CADE 侧无法实现"保证自动激活"。不要再在 `SKILL.md` 正文/`triggers` 上投入。

---

## 1. 问题来源

一次 CATIA/CAA 请求中，agent 未调用 `catia-caa-dev` skill，而是直接进入通用文件探索。
初始假设是"入口仲裁规则写得不够好"，因此调查先从 CADE 自身文档出发，随后逐层上溯到宿主平台。

调查路径：

```
CADE SKILL.md 正文规则
        ↑ 无法控制
skill 激活 / 选择
        ↑
宿主 tool catalog + 模型
        ↑
用户请求
```

---

## 2. 宿主机制（源码事实）

以下均读取自 Zed 仓库 `crates/agent_skills/`、`crates/agent/src/`、`crates/agent/src/templates/system_prompt.hbs`。

### 2.1 frontmatter 只解析 3 个字段

```rust
pub struct SkillMetadata {
    pub name: String,
    pub description: String,
    #[serde(default, rename = "disable-model-invocation")]
    pub disable_model_invocation: bool,
}
```

没有 `deny_unknown_fields`，未知字段被静默忽略。官方 README 原文：

> Unknown fields are silently ignored, which is the standard YAML behavior.
> The only field beyond the spec that we honor is `disable-model-invocation`.

实测 CADE `SKILL.md` 的 `triggers:` 为 **206 个条目 / 207 行**。

⇒ **该列表是惰性数据，宿主从未读取。**

> 双向对照：CADE 自身确实有 frontmatter 解析器（`skills/api_registry.py`、`skills/catalog.py`），
> 但它们只解析 `capabilities/*.md` 与 `knowledge/**/*.md` 的 frontmatter，**不解析 `SKILL.md`**。
> `skills/kernel.py::_determine_evidence_demand` 中的 `domain_triggers` 是**内联的领域词表**，
> 与 `SKILL.md` 的 `triggers:` **无关**。⇒ 两侧都无人消费该字段。

### 2.2 进入 system prompt 的只有元数据

`system_prompt.hbs` 中的 `<available_skills>` 只渲染 `name` / `description` / `location`（SKILL.md 绝对路径）。
**正文不在 system prompt 中。**

### 2.3 catalog 的筛选逻辑只有两条

`select_catalog_skills()` 只做：

1. 跳过 `disable_model_invocation: true` 的 skill；
2. 按 `name + description` 长度累加，超过 **50KB** 固定预算后停止打包。

**没有关键词匹配、没有相关性打分、没有向量检索、没有基于动作的触发逻辑。**

### 2.4 正文注入全库只有 2 条路径

| 路径 | 发起者 | 性质 | 实测返回形态 |
|---|---|---|---|
| `skill` 工具 | **模型**主动调用 | 概率性 | `tool_result` 文本：`<skill_content name="…"><source>project-local</source><worktree>…</worktree><directory>…</directory>` + 正文 |
| 用户输入 `/skill-name` 或 `@skill` 提及 | 用户 | 宿主确定性注入 | 同上（官方文档："Both inject the skill's instructions as context"） |

**不存在第三条路径。**宿主不会因为"出现某关键词 / 某动作"而自动注入 skill 正文。

### 2.5 其他门控（均属"是否可见"，非"自动激活"）

- **worktree trust**: project-local skill 只从已信任的 worktree 加载（官方文档："Project-local skills only load from trusted worktrees"）；
- **`disable-model-invocation`**: 从模型 catalog 隐藏，但**仍可用 `/` 或 `@` 手动调用**（CADE 当前**未**设置该字段）；
- **50KB catalog 预算**（`name` + `description` 合计，超出者被丢弃）；
- **扁平扫描**: skill 必须是 skills 根目录的直接子目录，**不支持嵌套**（官方文档 Limitations）。

---

## 3. 实测数据（`threads.db`）

来源：`%LOCALAPPDATA%\Zed\threads\threads.db`（只读副本 + zstd 解压）。

| 指标 | 数值 |
|---|---|
| 线程总数 | 35 |
| 用户消息总数 | 1958 |
| 调用过 `skill` 工具的线程（任意 skill） | 18 |
| **其中调用 `catia-caa-dev` 的线程** | **16** |
| **以 `/` 斜杠命令开头的用户消息** | **0** |
| **真正含 `@skill` / `@catia-caa-dev` 提及的用户消息** | **0** |

> `@` 通道的**原始**扫描会命中 1 条，但逐条核对后是**元线程内对注入机制的讨论文本**（`@` 出现在"也支持 `@skill`"这样的说明句里），**非注入行为**。⇒ 有效计数为 0。

> **口径说明**：「调用过 `skill` 工具」（18）与「调用 `catia-caa-dev`」（16）是**两个不同指标**，不可混用。
> 18 条中有 2 条只调用了其它 skill（`typesafe-ai`、`lark-*`），**从未**调用 CADE。
> 二者的差额不涉及本调查结论（本调查只关心 CADE 是否被调用）。

⇒ 本机 16 次 `catia-caa-dev` 激活 **100% 为模型自主决策**，从未使用过宿主确定性注入通道（`/` 与 `@` 均为 0）。

### 3.1 最强的反例：同类任务、同类消息、结果相反

| 线程 | 任务（均只读） | msg0 CATIA/CAA 密度 | 结果 |
|---|---|---|---|
| `64e0a69d` | 分析 CATIA CAA C++ 工具运行时性能 | caa=13 catia=1 | **skill@1 激活** |
| `1f19aad2` | 分析 CADE 知识检索链路 | caa=14 catia=8 cade=9 | 36 条消息**全程不激活** |
| `aa118b17` | 分析 CADE 代码生成管线 | caa=9 catia=8 cade=9 | 33 条消息**全程不激活** |

### 3.2 "可见 + 被讨论 + 仍拒绝"的单线程自证

`1f19aad2` 的 `msg[0]` 中**明确写出了** `...\catia-caa-dev\skills\retrieval.py` 路径。
其模型 thinking（`/Agent/content/0/Thinking/text`）原文：

> 先加载 skill 看看（用户提到了 catia-caa-dev skill，但这是分析任务，可能不需要加载 skill 的完整说明。不过任务明确指向这个项目，**我直接读文件即可**）。

`a258abfd` 的 thinking 原文：

> There's a skill available for CATIA CAA dev - **let me check if I should use it.** The task is debugging/analysis, not development, but the skill might have useful context. Let me first read the key files.

`64e0a69d` 则**逐字引用了 description**，随后调用 `skill`。

⇒ 模型**能看见**、**会显式评估**、然后**可以选择不用**。

---

## 4. 已推翻的假说（勿重犯）

| 假说 | 推翻依据 | 等级 |
|---|---|---|
| 「编译 / 启动 CATIA 动作触发激活」 | `01529cfc`（纯调研）、`4bb2ec5d`（只读审查）无任何 compile/build/start 词，仍 `skill@1`；且源码中不存在"动作→激活"映射 | 事实 |
| 「CATIA/CAA 关键词是必要条件」 | 9 条首条消息含 CATIA/CAA 字样却从未激活 | 事实 |
| 「是 CLI 抢了 MCP 入口」 | `d03f79b4`(09-15) 早于 MCP 注册（FSW `.zed/settings.json` mtime 2026-09-21），当时无 MCP 可选 | 强推断（mtime 非注册时刻的直接证据） |
| 「`d03f79b4` 可作基线回归」 | 其 `msg[0]`（4372 字符）在本库 35 线程中唯一；且含 **19 次** `Compaction` 事件（`messages[N].Compaction`，**dict 键**）——该机制会改写历史上下文，不适合作回归基线 | 事实（可见性仅限本库） |
| 「FSW 副本陈旧 / description 未同步」 | 2026-09-29 复核：两侧 `SKILL.md` sha256 一致，按脚本排除规则 804/804 文件哈希全一致，戳 = `74742c3` | 事实 |

---

## 5. 方法教训（本次调查中实际犯过的错）

1. **不要把线程 id 当普通子串搜索。**
   用 8 位前缀在整行 JSON 里做子串匹配，会命中"元线程"（某条线程的正文列出了其它线程 id 与调查全文），且脚本取"最后一个命中"时会取到错误线程。
   ⇒ 必须用数据库 `id` 列精确取值。

2. **模型裁量文本不在 `reasoning_details`。**
   本次样本中 `reasoning_details` 恒为 `null`，thinking 原文位于 `/Agent/content/N/Thinking/text`。
   ⇒ 必须递归遍历所有字段，不能只看固定 key。

3. **关键字统计要固定大小写策略。**
   大小写敏感的子串匹配会对 `CATIA` / `caa` 产生假阴性。
   ⇒ 统一转小写后统计。

4. **历史线程读数 ≠ 当前文件状态。**
   曾用一条 09-15 的历史线程读数推断"FSW 副本仍陈旧"，实为误判。
   ⇒ 结论涉及"现状"时必须实测当前文件。

---

## 6. 三层控制模型与确定性通道

```
                  用户 CAA 任务
                        │
          ┌─────────────┴─────────────┐
          │                           │
       自然语言                   确定性入口
          │                    ┌──────┴──────┐
          ▼                    │             │
   模型自行判断            / 或 @        MCP / CLI
          │                    │             │
       不确定性            宿主注入      绕过宿主
          │                    │             │
          └──────────┬─────────┴─────────────┘
                     ▼
                CADE 工作流
                     │
            MCP 优先 / CLI fallback
```

| 层 | 内容 | 控制者 | 能否保证 |
|---|---|---|---|
| 1 | skill 是否进入候选 catalog | 宿主 | 可配置/影响（当前正常） |
| 2 | **模型是否调用 skill** | **模型** | **不能保证** |
| 3 | 激活后 MCP / CLI 如何走 | CADE | 可控制（`74742c3`） |

### 确定性通道的准确表述

| 入口 | 性质 | 确定性 | 依赖宿主 |
|---|---|---|---|
| 自然语言"请使用 CADE" | Hint | ❌ | — |
| `/catia-caa-dev`、`@` | 宿主注入 | ✅ | 是 |
| **CLI**（`cade dev` 等） | CADE 自身入口 | ✅ | **否** |
| MCP | CADE 自身入口 | ✅ | **是**（stdio server，需宿主拉起） |

> 注：`skills/mcp_server.py` 的 `main()` 为 **MCP stdio server entry point**（L325–326），
> 无法由人手工调用，必须由 MCP 客户端宿主连接。**宿主无关性由 CLI 提供，不是 MCP。**

---

## 7. Non-Goals / 禁止推断

以下**不得**从本调查推出：

1. **不得**为提高激活率修改 `SKILL.md` 正文或 `triggers`——机制上不可达。
2. **不得**在 CADE 内部实现"强制激活 / 自动加载"体系——宿主无此入口，且会把宿主行为固化成 CADE 契约。
3. **不得**把本文件当作 ADR 引用为"CADE 必须如何处理 skill 激活"。
4. **不得**拓宽 description 去追求命中率——它只能提高**概率**，且会稀释 skill 的专业边界。
5. **不得**撤销 `74742c3`——它管第 3 层（激活后的入口仲裁），与本问题无关。
6. **不得**把"模型每轮主观判断"写成源码事实——源码只能证明"宿主无相关性强制注入机制"，不能证明模型内部决策机制。该表述**保持为推断**。

---

## 8. 自洽性检查（JEV，**非证据**）

使用 `jev-latest` 对结论做自洽性审查。**JEV 是审查器，不是证据源。**

| 命题 | 第 2 轮 | 第 3 轮 |
|---|---|---|
| 正文改动不可能影响激活 | 0.71 | — |
| 自然语言非 guarantee | 0.04 | 0.77 |
| 三层模型一致 | 0.91 | — |
| `74742c3` 保留有价值 | 0.70 | 0.79 |
| "主观判断"须保持推断 | 0.38 | 0.89 |
| 关键字不是可靠杠杆 | 0.72 | — |
| MCP 与 CLI 同为"不依赖宿主" | **0.19（否定）** | — |
| 不写该文档 = 自洽 | — | 0.99 |

**注意**：第 1 轮曾在**喂入事实有误**的情况下运行，结论作废。
同一命题在不同轮次得分波动明显（如"正文不影响激活" 0.22 → 0.71），说明 JEV 对喂入事实与措辞敏感。
⇒ **仅作自洽性检查，不得作为事实证据。**

---

## 9. 复现方法

```
1. 读宿主源码（权威）：
   raw.githubusercontent.com/zed-industries/zed/main/crates/agent_skills/agent_skills.rs
   raw.githubusercontent.com/zed-industries/zed/main/crates/agent/src/tools/skill_tool.rs
   raw.githubusercontent.com/zed-industries/zed/main/crates/agent/src/templates/system_prompt.hbs
   raw.githubusercontent.com/zed-industries/zed/main/crates/agent/src/agent.rs   (select_catalog_skills)

2. 读本机宿主文档：zed.dev/docs/ai/skills

3. 读线程库（只读；**务必先复制 db 及其 -journal/-wal/-shm 再打开**）：
   %LOCALAPPDATA%\Zed\threads\threads.db
   - 解压：import compression.zstd as zstd; zstd.decompress(row["data"])
   - 表：threads(id, summary, updated_at, data_type, data, parent_id, ...)；**无 title 列**（标题在 JSON 内）
   - 结构：messages[i] = {"User": {...}} | {"Agent": {"content", "tool_results", "reasoning_details"}}
   - **激活证据只认一种可靠形态**：`Agent.content` 中 `ToolUse.name == "skill"`，其返回为
     `Agent.tool_results[<id>].content[0].Text`，以 `<skill_content name="...">` 开头。
     *注意*：裸字符串 `<skill_content>` 全库另有 2 处命中，均为**宿主 Rust 源码片段**，属假阳性。
   - thinking 文本位于 `Agent.content[N].Thinking.text`（`reasoning_details` 常为 null）
   - 上下文压缩事件位于 `messages[N].Compaction.Summary`（**dict 键**，非字符串值）
   - **统计必须用数据库 `id` 列精确取值**；用 8 位前缀在整行 JSON 里做子串匹配会命中元线程

4. 同步校验：sh sync_agents.sh，然后比对 .sync_stamp
```

---

## 10. 版本与适用范围

- 源码读取自 **`main` 分支**，**非** 1.21.0 tag，**未做逐版本 diff**。
  但实测行为（progressive disclosure、`skill@1` 为模型主动调用、模型逐字引用 description）
  与 `main` 机制自洽 ⇒ 该机制在 1.21.0 成立属**强推断**。
- 本结论绑定宿主平台。**更换宿主（Codex / WorkBuddy / 其他 Agent）须重新验证。**
- 本文件本身**不影响** skill 激活：只有 `name` + `description` 进入 catalog，docs 下的文件不参与。

---

**最后更新**: 2026-09-29
**调查结论**: Closed — CADE 侧无可控杠杆，不再继续。
