---
id: fp.template_feature_apis
title: "Feature/Catalog 模版成建制捏造（B28 全目录核实）"
severity: error
category: knowledge
domain: infrastructure
release: [R19, R28]
tags: [template, feature, catalog, fabricated, mecmod]
apis: [CATIMmiResultFeature, CATIMmiUseMechFeat, CATMmrInterfaces, CATFeatCont, CATICatalog, CATAfrCommandHeader, CATFrmIdentityCard, CATTopBooleanOperator, CATTopRevolve, CATIGeometricalElement, CATOsmSUHandler]
frameworks: [CATMecModUseItf, MecModInterfaces, ComponentsCatalogsInterfaces, ApplicationFrame]
keywords: [feature, template, SetResult, GetBodyResult, StartUp, catalog, fabricated, AddHeaderAddin]
---

# Feature/Catalog 模版成建制捏造

## 背景

2026-07 对 `templates/feature/*`、`templates/command/CommandHeader.cpp`、
`templates/workbench/WorkbenchIdentityCard.h` 做全量 dogfood 时发现：
这批模版不是个别头文件拼错，而是**整套 API 链路按"看起来合理"的命名
规律脑补**，经 B28 全目录 `find` 搜索证实全部不存在。

## 判决清单（B28 全目录搜索零命中）

### 头文件（9 个，全 B28 无任何位置存在）

| 捏造 | 脑补规律 | 真相 |
|---|---|---|
| `CATIMmiResultFeature.h` | Mmi 前缀 + Result 功能 | 只有 `CATIMmiResultFreeze`（冻结状态，功能完全不同） |
| `CATIMmiUseMechFeat.h` | MmiUse 前缀缩写 | 不存在；真实接口全在 `CATMecModUseItf`/`CATMecModLiveUseItf` |
| `CATMmrInterfaces.h` | "Mmr" 前缀 | 该前缀不存在 |
| `CATFeatCont.h` | 特征容器缩写 | 不存在 |
| `CATICatalog.h` | catalog 应有主接口 | 真实是拆分接口：`CATICatalogChapter`/`CATICatalogDescription`/`CATICatalogLink`/`CATICatalogChapterFactory` |
| `CATAfrCommandHeader.h` | Afr 前缀 + CommandHeader | 只有 `CATAfrCommandHeaderRep`（内部表示）和 `CATAfrDialogCommandHeader`（自定义 header 基类） |
| `CATFrmIdentityCard.h` | Frm 前缀 + IdentityCard | IdentityCard.h 是 mkCreateIC 生成的 prereq 声明文件，无对应公共头文件 |
| `CATTopBooleanOperator.h` | Top + Boolean | 真实是 `CATTopOperator.h` 派生体系 |
| `CATTopRevolve.h` | 英文全拼 | 真实是 `CATTopRevol.h`（法文截断） |

### 方法归属（头文件原文 grep 证实）

| 模版写法 | 真相 |
|---|---|
| `CATIMmiMechanicalFeature::GetBodyResult()` | 该方法在 **`CATIGeometricalElement`** 上，签名 `CATBody_var GetBodyResult()`（MecModInterfaces，头文件 L93） |
| `CATIMmiResultFeature::SetResult(body)` | 接口本身不存在；**自定义特征结果写入无公开 SetResult API** |
| `CATICatalogChapter::CreateStartUp()/GetStartUp()` | 接口无此方法（全部方法已列出：chapter 关键词/默认值管理 + `AddDescription`）；StartUp 由 `CATOsmSUHandler`/`CATISpecObject::GetStartUp` 管理 |
| `CATISpecAttrAccess::AddAttribute()` | 在 `CATISpecObject` 上 |
| `CATISpecAttrKey::SetElementType()` | 不存在 |
| `CATICatalogDescription::SetDescription()` | 不存在（只有 Get 类方法） |
| 全局函数 `::CreateCatalog()`/`::AccessCatalog()` | 不存在（ComponentsCatalogsInterfaces 全目录 grep 零命中） |
| `AddHeaderAddin`/`AddHeaderWorkshop` 宏 | 不存在（全 B28 + CAADoc 索引零命中）；Addin/Workbench 注册在 **.dic 字典**：`XxxAddin CATIWorkbenchAddin libXxx` / `XxxWorkbench CATIPrtWksConfiguration libXxx` |

### 语法错误

`StartUpCatalog.cpp` 原 L52：`hr = ::<CreateCatalog(&piCatalog);`——多个 `<`，
即使 API 存在也无法编译。

## 正确的替代事实

1. **读取特征结果几何**：`CATIGeometricalElement::GetBodyResult()` → `CATBody_var`
2. **Command Header**：用 `MacDeclareHeader(Name)` 宏（`CATCommandHeader.h` L1138，
   文档原话 "In most cases it is sufficient"）；自定义时派生
   `CATAfrDialogCommandHeader`（真实存在）
3. **Addin/Workbench 注册**：写框架 .dic 文件，不用任何宏
4. **Catalog/StartUp**：`CATOsmSUHandler` + `ComponentsCatalogsInterfaces` 的
   Chapter/Description 接口体系（模版整体待重写）

## 处置（2026-07）

- 6 个坏代码文件加 ⚠️ 标记并修掉可修部分（`templates/feature/` 5 个 +
  `templates/command/CommandHeader.cpp`）
- `templates/workbench/WorkbenchIdentityCard.h` 按真实模式重写
- `generator.py::_gen_feature_spec` 熔断：拒绝渲染 feature 模版
- `intents/objects.py::create_feature` 路由降级：提前返回错误说明
- 模版重写等遥测证明 feature 需求高频后，基于 CATMecModUseItf 教程进行

## 教训

**"前缀 + 功能名"的命名规律外推是 AI 捏造 CAA API 的最高发模式**
（CATIMmi + Result、CAT + FeatCont、CATAfr + CommandHeader）。
任何"看起来就该存在"的接口名，必须过 `header_map.py` + `method_index.py`
双重核实才允许写入模版——这次正是这两件工具抓住了整批捏造。
