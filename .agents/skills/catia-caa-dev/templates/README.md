# CADE 模板目录契约

磁盘目录名**全小写**。`ctx.tpl("module", "Imakefile.mk")` 解析为
`templates/module/Imakefile.mk`。不要按类型名拼 PascalCase
（`templates/Module/`、`templates/Framework/` 都不存在）。

Windows 资源管理器不区分大小写，所以 `dir Module` 仍能进 `module/`。
Zed `list_directory` / git / 多数 Agent 工具按字面路径，PascalCase 会看成空。

## 类型 → 目录

| Intent / CLI | 目录或根文件 | 生产入口实际读的文件 |
|---|---|---|
| CreateFramework | `framework/` | `IdentityCard.h`, `Framework.edu.dico`, `FrameworkImakefile.mk`, `CATIAV5Level.lvl` |
| CreateModule | `module/` | `Imakefile.mk`（`AddinClass.*` 给后续 create_command 挂 addin） |
| CreateCommand | `command/` | `CommandClass.*`, `CommandHeader.*`, NLS/Rsc |
| CreateDialog | `dialog/` | `DialogClass.*`, NLS |
| CreateWorkbench | `workbench/` | `WorkbenchClass.*`, `AddinClass.*` |
| CreateInterface | 根级 `IInterface.h` / `IInterface.cpp` | 不在 `interface/` 子目录 |
| CreateFeature | `feature/` | Feature / Factory 骨架 |
| CreateExtension | 由 intents 组合现有模板 | 无独立 `extension/` 目录 |

没有 `StateCommand/` 目录：状态命令走 `command/` + `is_stateful`。

## 生成结果看起来“空”不是模板空

`create_module` 只落 `Imakefile.mk`，再在 `src/`、`LocalInterfaces/`、
`PublicInterfaces/`、`resources/` 放 `.gitkeep`。源文件要等
`create command / dialog / interface` 才写入。
