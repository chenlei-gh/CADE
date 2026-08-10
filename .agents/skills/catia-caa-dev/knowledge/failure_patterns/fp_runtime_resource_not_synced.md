---
id: fp.runtime_resource_not_synced
title: Runtime Resource Not Synced / 资源未同步到 Runtime View 导致按钮消失、图标缺失
category: knowledge
domain: failure_patterns
severity: runtime_error
apis: []
frameworks: [ApplicationFrame]
keywords: [runtime view, sync, dictionary, dico, icons, msgcatalog, NLS, button missing, icon missing, 按钮消失, 图标不显示, win_b64, mkCreateRuntimeView]
tags: [failure_pattern, runtime, build, resource, dictionary, toolbar]
release: [R19, R28]
automation: manual
capabilities: [runtime_publish, build_workspace]
not_automatable_because: "同步动作本身已自动化（build.py:sync_runtime_view 在每次 build 后自动执行），但『非 build.py 编译路径』（手动 mkmk / VS 编译 / 仅拷 DLL）绕过该钩子，无法在静态侧检测——是否同步发生在构建工具的选择时刻，属于流程行为而非代码形态。可规则化方向：verifier 对比 CNext/resources 与 win_b64/resources 内容哈希，发现漂移即报警（类似 build.py:verify_build 的 DLL 校验），当前未实现。"
---

# Runtime Resource Not Synced / 资源未同步到 Runtime View 导致按钮消失、图标缺失

## 症状

编译成功后启动 CATIA：

- 工具栏上**找不到新加的命令按钮**（dictionary 未更新）
- 按钮存在但**没有图标**（icons 未同步）
- NLS 标题/提示是旧的或显示资源 key 原文（msgcatalog 未同步）

编译本身无任何报错，DLL 时间戳也是新的。

## 原因

CATIA 运行时不直接读 Framework 工作区下的 `CNext/`，而是读 **Runtime View**（`workspace/win_b64/`）下的副本：

| 源（工作区） | Runtime View 副本 | 缺失后果 |
|---|---|---|
| `*.edu/CNext/code/dictionary/*.dico` | `win_b64/code/dictionary/` | 命令/工具栏不注册 → 按钮消失 |
| `*.edu/CNext/resources/graphic/icons/` | `win_b64/resources/graphic/icons/` | 无图标 |
| `*.edu/CNext/resources/msgcatalog/` | `win_b64/resources/msgcatalog/` | NLS 文本缺失/过期 |

**图标分区约定（2026-08 起）**：`graphic/icons/` 下分两个语义区，同步逻辑（`build.py:sync_runtime_view`）按内容哈希递归同步两者，但生成逻辑区别对待——

- `icons/normal/`：**CADE 自管**。命令图标由 `icon_provider` 生成（22×22 8bpp），每次 `create_command` 用当前渲染强制刷新，手改会被覆盖。
- `icons/custom/`：**项目自管**。放手工绘制的定制图标（任意尺寸，如面板按钮的 24×24），CADE 永不自动生成、永不覆盖（`actions.py` 在生成命令图标前检查同名 custom bmp，存在即跳过）。`I_BomExport.bmp`（24×24 表格+导出箭头，`CAABOMTool.edu/Tools/gen_bomexport_icon.py` 生成）即属此类。

**编译（mkmk）只产出 DLL，从不拷贝这些资源。** 资源同步是一个独立动作，容易被漏掉。

注意（2026-07-29 核实，避免误记根因）：

- **走 `build.py` 的编译不会漏**：`build_workspace` 在每次 build 后自动调用 `sync_runtime_view()`，同步上述全部三类资源（见 `build.py` L525-531）
- 真正踩坑的路径是**绕过 build.py 的编译**：手动 mkmk、VS 内编译、或只把 DLL 拷到 `win_b64/code/bin/`——这些路径没有同步钩子
- `mkCreateRuntimeView` 可能跳过 dictionary 拷贝，`build.py:create_runtime_view` 已手动补 `_copy_dictionaries_to_runtime()`

## 修复

1. 优先走 `build.py` 编译（自动同步）
2. 若手动编译，编译后显式执行同步：

```python
from build import sync_runtime_view
sync_runtime_view(workspace_path)   # dictionary + msgcatalog + icons
```

3. 同步后**重启 CATIA**：dictionary 与图标缓存只在启动时加载，会话中替换文件不生效

## 预防规则

- [ ] "按钮消失/无图标/NLS 过期"的第一排查动作：对比 `*.edu/CNext/` 与 `win_b64/` 对应文件的**内容**（不是 mtime——git checkout 会重置 mtime）
- [ ] 手动 mkmk / VS 编译后，必须补一次 `sync_runtime_view()`，不要假设"编译了 = 同步了"
- [ ] 改了 dico/icons/NLS 但没改代码时，编译不会重链——资源同步仍必须执行
- [ ] 资源已同步但 CATIA 里没变：先重启 CATIA 再怀疑同步

## 边界与局限

- 本条只覆盖"同步缺失"这一类；按钮消失的其他常见根因见 `fp_toolbar_setaccesschild_overwrite`（命令访问链被覆盖）、`fp_undeclared_class`（dictionary 未注册组件）
- `sync_runtime_view` 自身失败此前会被 `except Exception: pass` 静默吞掉（2026-07-29 已改为 `logger.write(WARNING)`）；排查时若 build 日志出现该 WARNING，按日志中的异常信息定位
