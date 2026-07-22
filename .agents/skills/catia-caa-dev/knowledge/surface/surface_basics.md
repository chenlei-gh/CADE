---
id: surface.basics
title: Surface & GSD Basics
category: knowledge
domain: surface
keywords: [surface, GSD, Generative Shape Design, extrude, revolve, sweep, offset, trim, assemble]
apis: [CATIGSMFactory, CATIGSMExtrude, CATIGSMOffset, CATIGSMTrim, CATIGSMAssemble, CATICkeParmFactory]
requires: [mecmod.feature, part.fillet]
patterns: [surface.analysis]
examples: []
release: [R19, R28]
tags: [surface, GSD, geometry]
---

# CAA Surface Design (GSD)

Generative Shape Design (GSD) 通过 `CATIGSMFactory` 创建曲面特征。

## ⚠️ 重要修正

之前版本以下 API 经核实**不存在或签名错误**：

| 虚构/错误 | 真实 API |
|-----------|---------|
| `CreateExtrude(profile, NULL, dir, len, len, &out)` | 真实签名：`CreateExtrude(CATISpecObject_var, CATIGSMDirection_var, CATICkeParm_var len1, CATICkeParm_var len2, CATBoolean orient)` → 返回 `CATIGSMExtrude_var`。**长度参数必须是 `CATICkeParm_var`**（用 `CATICkeParmFactory::CreateLength(name, value)` 创建），不能直接传 double |
| `CreateOffset(surf, double, bool, &out)` | 真实：`CreateOffset(CATISpecObject_var, CATICkeParm_var iLittMax, CATBoolean invert=FALSE, CATBoolean suppress=FALSE)` → `CATIGSMOffset_var` |
| `CreateJoin(...)` / `CATIGSMJoin` | **均不存在**。UI 里的 Join 在 API 中叫 **Assemble**：`CATIGSMFactory::CreateAssemble(CATLISTV(CATISpecObject_var))` → `CATIGSMAssemble_var` |
| `CreateTrim(s1, s2, bool, bool, &out)` | 真实：`CreateTrim(CATISpecObject_var, CATGSMOrientation, CATISpecObject_var, CATGSMOrientation)` → `CATIGSMTrim_var` |
| `CreateSweep` | 不存在。真实：`CreateExplicitSweep` / `CreateLinearSweep` / `CreateCircularSweep` / `CreateConicalSweep` |
| `CreateDevelop` / `CATIGSMDevelop`（展平） | 均不存在于 CATIGSMFactory |
| `CATBooleanTrue` / `CATBooleanFalse` | 不存在。用标准 `TRUE` / `FALSE` |
| `CATBody::GetSurfaceArea(area)` | 不存在。面积测量用 `CATIMeasurableSurface::GetArea(double&)`（MeasureGeometryInterfaces） |
| `CATIGSMConnectChecker`（连续性检查） | 不存在 |

官方样例参考：`CAADoc/CAAGSMInterfaces.edu/CAAGsiBodyGSAndOGS.m/src/CAAGsiBodyGSAndOGS.cpp`

## 核心接口

| 接口 | 用途 |
|------|------|
| `CATIGSMFactory` | 所有曲面操作入口（对 Part 的 spec 容器 QI 获取） |
| `CATIGSMExtrude` | 拉伸曲面 |
| `CATIGSMSweep*` | 扫掠（Explicit/Linear/Circular/Conical 四种创建方法） |
| `CATIGSMOffset` | 偏移曲面 |
| `CATIGSMTrim` | 修剪 |
| `CATIGSMAssemble` | 缝合（API 名 Assemble = UI 的 Join） |
| `CATICkeParmFactory` | 创建长度/角度参数（`CreateLength`） |

## 基本操作

### 拉伸曲面（官方样例惯用法）

```cpp
#include "CATIGSMFactory.h"
#include "CATICkeParmFactory.h"

// 1. 长度参数必须经 CATICkeParmFactory 创建，不能直接传 double
CATICkeParm_var spStart = spCkeFact->CreateLength("Start", 0.0);
CATICkeParm_var spEnd   = spCkeFact->CreateLength("End",   100.0);

// 2. 方向对象
CATIGSMDirection_var spDir = spGsmFact->CreateDirection(spPlane);

// 3. 创建拉伸（返回 CATIGSMExtrude_var，不是输出参数）
CATIGSMExtrude_var spExtrude =
    spGsmFact->CreateExtrude(spProfile, spDir, spStart, spEnd, TRUE);

// 4. 当 CATISpecObject 用，插入过程视图并更新
CATISpecObject_var spSpecExtrude = spExtrude;
// ... insert in procedural view + update ...
spPrtPart->SetCurrentFeature(spSpecExtrude);
```

### 偏移曲面

```cpp
CATICkeParm_var spOffsetVal = spCkeFact->CreateLength("Offset", 5.0);

CATIGSMOffset_var spOffset =
    spGsmFact->CreateOffset(spSurface, spOffsetVal,
                            FALSE,   // invert direction
                            FALSE);  // suppress mode（TRUE=剔除错误元素）
```

### 缝合曲面（API 名 Assemble）

```cpp
CATLISTV(CATISpecObject_var) listSurfs;
listSurfs.Append(spSurf1);
listSurfs.Append(spSurf2);

CATIGSMAssemble_var spAssemble = spGsmFact->CreateAssemble(listSurfs);
```

### 修剪 (Trim)

```cpp
// 两个面互相修剪，方向枚举控制保留侧
CATIGSMTrim_var spTrim = spGsmFact->CreateTrim(
    spSurf1, CATGSMSameOrientation,      // 第1面保留侧
    spSurf2, CATGSMInvertOrientation);   // 第2面保留侧
```

## 曲面分析

### 面积/重心/周长（CATIMeasurableSurface）

```cpp
#include "CATIMeasurableSurface.h"

double GetSurfaceArea(CATISpecObject_var iSurface) {
    CATIMeasurableSurface *pMeas = NULL;
    HRESULT rc = iSurface->QueryInterface(IID_CATIMeasurableSurface,
                                          (void**)&pMeas);
    if (FAILED(rc) || !pMeas) return 0.0;

    double area = 0.0;
    pMeas->GetArea(area);          // 还有 GetArea_COfG / GetCOG / GetPerimeter
    pMeas->Release();
    return area;
}
```

### 连续性检查

`CATIGSMConnectChecker` 不存在。曲面连接/连续性分析请改用 MeasureGeometryInterfaces 的测量接口或 GSD 分析工作台对应接口（以 B28 refman 为准），不要臆造 Checker 类。

## AI 生成规则

- [ ] 所有曲面操作通过 `CATIGSMFactory`
- [ ] **长度/角度参数必须 `CATICkeParmFactory::CreateLength/CreateAngle`**，禁止直接传 double
- [ ] 方向用 `CreateDirection(参考平面/线)` 生成 `CATIGSMDirection_var`
- [ ] 创建方法返回 `CATIGSMXxx_var`（智能指针），**不是输出参数**
- [ ] 缝合 = `CreateAssemble`，不要说 Join
- [ ] 布尔用 `TRUE`/`FALSE`；方向用 `CATGSMOrientation` 枚举
- [ ] 创建后插入过程视图并 `Update()`，再 `SetCurrentFeature`
- [ ] 面积测量 QI `CATIMeasurableSurface`
