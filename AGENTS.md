# 本项目开发规范（CADE）

> **优先级声明**：本文件是项目级规范，**优先于全局 `AGENTS.md`**。
> 全局规范要求「涉及 CAA 开发必须优先调用 `catia-caa-dev` Skill、严禁绕开 CADE 手动编写 CAA 代码」。
> 本规范对该要求作**可在本项目中执行**的细化，并显式开辟一条受约束的例外通道，
> 以消除「CADE 无对应能力」与「禁止绕过 CADE」之间的死锁。
> 若本文件与全局规范冲突，以本文件为准。

## 1. 唯一合法入口

涉及 CATIA CAA 的以下操作，唯一合法入口是 `catia-caa-dev` Skill 的 CADE 能力
（MCP `develop` / `analyze` / `repair`，或按 `capabilities.yaml` 登记的 binding）：

- 编译 / 构建 / 启停 CATIA / 跑宏 —— **禁止**裸跑 `mkmk`、`mkrun`、`mkcnext`
- 诊断、修复、重构、生成、回滚
- 工作区分析、依赖分析、头文件 / 方法 / API 核实

## 2. 受控资产（禁止直接写入）

以下文件禁止用脚本或编辑器**直接写入**（会被 CADE 的 Provenance Guard 判为 `UNTRACKED_EXTERNAL`）：

- `.cpp` / `.cxx` / `.h` / `.hpp`
- `Imakefile.mk`
- `IdentityCard.xml`
- `.dico`
- `.CATNls` / `.CATRsc`
- 图标资源

## 3. 例外通道：手写逻辑编辑

**适用条件**：修改对象是 CADE 当前**无能力覆盖**的手写逻辑
（例：`CAAExplodePureAlgorithm.cpp` 中的启发式几何算法），
且已确认无法通过 `develop` / `repair` / `refactor` 完成。

**必须同时满足以下 5 条，缺一不可：**

1. **前置声明（可核实）** —— 动手前说明：
   - 「已查 `capabilities.yaml`（当前 24 个能力），无覆盖能力」；
   - 拟改文件、改动意图、预期行为影响；
   - 并取得用户确认。
   > 禁止只写「CADE 无此能力」这类**无法核实**的理由。理由必须能被当场证伪，
   > 例如用户可用 `grep -c "^  - name:" capabilities.yaml` 复核能力数量。
2. **最小改动** —— 只改与任务直接相关的代码；不顺带重构、不改无关文件、
   不覆盖他人未提交改动。
3. **CADE 编译核查** —— 编辑后必须用 CADE 编译验证：
   ```bash
   python .agents/skills/catia-caa-dev/skills/build.py <module> --timeout 900
   ```
   **禁止**用其他方式编译（含 IDE 编译、裸 `mkmk`），否则资源同步与验证会被跳过。
4. **现场清理** —— 禁止在仓库内遗留任何临时脚本 / 中间产物 / 构建垃圾
   （`_tmp_*`、`*.obj`、`*.lib`、`*.exp`、`*.exe`、`*.log` 等）。
   用完即删，并用 `find` 递归确认无残留。
5. **如实汇报** —— 回复中列出被改文件、行为影响、验证方式与结果。
   **未经实测不得声称「通过」**；区分「已验证 / 推断 / 未验证」。

## 4. 已知边界（诚实记录）

本节的目的是避免后人误以为本规范具备机械强制力。

- **Provenance Guard 只审计、不阻断。** 审计结果只写入构建结果的
  `provenance_audit` 字段，**从不影响构建的 `status`**，构建照常通过。
  两种实测到的形态：
  - 无基线 / 未传预期变更集时 → `audit_state: NOT_EVALUATED`（如本项目裸跑 `build.py`，
    同时 `attached_to_maintenance: false`，即不计入维护账本）；
  - 输入完整有效时才真正比对 → `audit_state: EVALUATED`，逐个文件标出
    `UNTRACKED_EXTERNAL`。
  无论哪种，**都不阻断**。因此本规范的强制力来自**约定与人工复查**，不是机械闸门。
- **`build_gate` 已具备可用的阻断模式**（`PASS` / `WARN` / `BLOCK` / `SKIP`，
  对虚构 API 会 `BLOCK` 并中止构建），证明本工具链存在可复制的阻断模板；
  但它目前**不用于来源审计**，且留有 `--skip-gate` 逃生阀。
- **意图闸门已实现（2026-10-21），装在 git 提交链路而非编辑器上。**
  `tools/check_intent.py` + `commit-msg` hook 对暂存的受控资产要求一份声明。
  它**不试图判断是谁改的文件**——只看变更有没有被声明，因此「AI 手改」与
  「人工 IDE 编辑」走同一条通道，不构成差别对待：
  - 人工：在 commit message 里加一行 `CADE-Intent: <理由>` 即可（本来就在写 message）；
  - CADE：`--bless cade --rollback-id <id>`，文件清单从备份 manifest 推出；
  - 逃生阀：`git commit --no-verify`（git 原生，无需额外记忆）。
- **闸门的诚实边界（勿高估其强制力）：**
  - 它只拦 `commit -m` / 交互式提交；`--no-verify`、`git commit-tree`、
    直接推已存在的提交都不经过它。它提高的是「无声明变更」的显性成本，不是不可绕过。
  - 它**不判断声明内容是否属实**，只判断声明是否存在、是否覆盖了这些路径。
  - 内部故障一律 fail-open（缺分类器、非 git 目录、索引不可读、提交信息文件读不到
    → `DEGRADED` 放行）。理由：闸门因自身故障锁死仓库，比没有闸门更糟。
  - 合并提交放行（`WARN`）：被合并的提交已各自过闸。
- 本规范约束的是 **Agent 行为**；用户本人或非 Zed 工具直接编辑文件时不受其约束。

## 5. 待补（暂缓项）

1. ~~**机械闸门**：`pre-commit` 声明式校验（要求受控资产变更附 `.cade/intent/` 下的意图声明，
   无匹配声明才拦截）。~~ **已实现（2026-10-21）**，见第 4 节与第 6 节。
   实现选择的声明载体是 **commit message trailer**（而非强制单独的声明文件），
   正是因为单独的声明文件会误伤人工编辑：人不会为了改一行 `.cpp` 先去写一个 JSON。
2. **CADE 逻辑编辑能力**：为 CADE 增加手写代码合法编辑入口
   （开 ChangeSet + 备份 + 回滚点 + 登记）。此为**治本**方案；
   补齐后，「走 CADE」才第一次真正可行，第 3 节的例外通道即可收窄甚至取消。
   当前 `--bless cade` 已能接受 CADE 备份 manifest 作为凭据，但来源仍是
   「事后登记」而非「CADE 自己改的」，两者不可混为一谈。

## 6. 意图闸门：安装与声明

`.git/hooks` 不随仓库分发，**每台机器 / 每个 clone 都要装一次**。
安装命令同时打印可重放的那一行，照它复制即可：

```bash
python .agents/skills/catia-caa-dev/tools/check_intent.py \
    --install-hooks --workspace "D:/Vault/FSWorkspaces"
```

它会写入两个 hook（都是对同一个闸门的薄包装）：

| hook | 作用 |
|---|---|
| `pre-commit` | **仅提示**（固定 `--warn-only`）。此时提交信息还不存在，看不到 trailer，拦截会误伤 |
| `commit-msg` | **正式判定**。能读到提交信息中的 `CADE-Intent` |

声明方式二选一：

```bash
# 1) commit message trailer（推荐：随历史走，不需要额外文件）
git commit -m "<subject>" -m "CADE-Intent: <为什么这么改>"
#   只想声明其中几个文件时再加一行（逗号分隔）：
#   CADE-Intent-Files: a/b.cpp, c/d.h

# 2) 本地声明文件（复用型 / CADE 自动写）
python .agents/skills/catia-caa-dev/tools/check_intent.py \
    --workspace "D:/Vault/FSWorkspaces" --bless manual --reason "<理由>"
# CADE 产生的改动可用 --bless cade --rollback-id <备份 id>（文件清单取自 manifest）
```

`.cade/intent/*.json` 的 schema（`schema_version: 1`）：

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 必须为 `1`；不匹配的声明被忽略 |
| `kind` | 否 | `manual` 或 `cade` |
| `reason` | 建议 | 人类可读理由 |
| `files` | 二选一 | 覆盖的路径列表（相对工作区、正斜杠） |
| `expires_at` | 二选一 | ISO 时间；到期后声明失效 |

`files` 与 `expires_at` **至少给一个**：既无文件列表又无期限的声明会永续覆盖
所有受控资产，属配置事故，闸门会拒绝（`claim_problems` 会写明原因）。

验证与排错：

```bash
python .agents/skills/catia-caa-dev/tools/check_intent.py \
    --workspace "D:/Vault/FSWorkspaces" --json     # 看当前暂存区判定
```

退出码：`0` = 放行（PASS / WARN / DEGRADED），`1` = BLOCK，`2` = 无法判定。
