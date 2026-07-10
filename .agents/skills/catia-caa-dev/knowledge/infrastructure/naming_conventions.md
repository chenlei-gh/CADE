# CAA Naming Conventions

## Frameworks

| Rule | Pattern | Example |
|------|---------|---------|
| 后缀 | `.edu` | `MyFramework.edu` |
| 全大写简写 | Framework 首字母大写 | `CATIA_AutoTools.edu` |
| IdentityCard | `IdentityCard/IdentityCard.h` | 固定位置 |

## Modules

| Rule | Pattern | Example |
|------|---------|---------|
| 后缀 | `.m` | `MyModule.m` |
| 命名风格 | 首字母大写，用下划线分隔 | `AT_Core.m` |
| 功能前缀 | 按功能域分类 | `AT_Geom.m`（几何）、`AT_UI.m`（界面） |

## Interfaces (Public)

| Rule | Pattern | Example |
|------|---------|---------|
| 前缀 | `I` + 功能描述 | `IATNamingService` |
| 文件位置 | `PublicInterfaces/I*.h` | `PublicInterfaces/IATNamingService.h` |
| 导出宏 | `ExportedBy{ModuleName}` | `ExportedByAT_Core` |
| 继承 | `CATBaseUnknown` | `class IATNamingService : public CATBaseUnknown` |

## Components (Implementation)

| Rule | Pattern | Example |
|------|---------|---------|
| 命名 | 接口名去掉 `I` 前缀 | `ATNamingService`（实现 `IATNamingService`） |
| 文件位置 | `LocalInterfaces/*.h` + `src/*.cpp` | `LocalInterfaces/ATNamingService.h` |
| BOA 宏 | `CATImplementClass(Name, Implementation, Parent, CATNull)` | |
| TIE 宏 | `CATImplementBOA` | |

## Commands

| Rule | Pattern | Example |
|------|---------|---------|
| 命名 | 功能前缀 + 动词/名词 | `ATAutoRenameCmd` |
| 状态命令 | 末尾无特殊标记 | 默认 StateCommand |
| 文件位置 | `LocalInterfaces/{Name}.h` + `src/{Name}.cpp` | |
| Header 源文件 | `src/{Name}Header.cpp` | 注册文件 |
| 状态命令类 | `CATStateCommand` | `class ATAutoRenameCmd : public CATStateCommand` |

## Dialogs

| Rule | Pattern | Example |
|------|---------|---------|
| 命名 | 关联命令名 + `Dlg` | `ATAutoRenameDlg` |
| 文件位置 | `LocalInterfaces/{Name}.h` + `src/{Name}.cpp` | |
| 继承 | `CATDlgDialog` | `class ATAutoRenameDlg : public CATDlgDialog` |

## Features

| Rule | Pattern | Example |
|------|---------|---------|
| 命名 | 功能前缀 + 名词 | `ATTimeTable` |
| Factory | `{Name}Factory` | `ATTimeTableFactory` |
| 接口 | `I{Name}` | `IATTimeTable` |
| 文件位置 | `LocalInterfaces/{Name}.h` + `src/{Name}.cpp` | |
| 继承 | `CATBaseUnknown` + 功能接口 | |

## Catalog Entries

| Rule | Pattern | Example |
|------|---------|---------|
| 格式 | `ClassName  TAB  BaseClass  TAB  Library` | `ATAutoRenameCmd	CATStateCommand	libAT_UI` |
| 位置 | `CNext/code/dictionary/{Framework}.dico` | |

## Files

| Rule | Pattern | Example |
|------|---------|---------|
| Header | `{ClassName}.h` | `ATAutoRenameCmd.h` |
| Source | `{ClassName}.cpp` | `ATAutoRenameCmd.cpp` |
| Interface header | `I{Name}.h` | `IATNamingService.h` |
| Interface source | `I{Name}.cpp` | `IATNamingService.cpp` |
| Command header注册 | `{Name}Header.cpp` | `ATAutoRenameCmdHeader.cpp` |

## AI Generation Checklist

生成任何 CAA 代码前确认：

- [ ] Framework 后缀 `.edu`
- [ ] Module 后缀 `.m`
- [ ] Interface 前缀 `I`
- [ ] Command 用 `CATStateCommand` 基类
- [ ] Component 用 `CATBaseUnknown` 基类
- [ ] 文件名和类名一致
- [ ] Public 放 `PublicInterfaces/`，Private 放 `LocalInterfaces/`
- [ ] 勿用 `_` 连接（用驼峰），模块名除外
