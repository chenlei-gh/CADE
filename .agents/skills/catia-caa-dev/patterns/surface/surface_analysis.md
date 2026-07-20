---
id: surface.analysis
title: Surface Analysis & Automation
category: pattern
domain: surface
keywords: [surface, analysis, flatten, develop, continuity, checker, gap]
apis: [CATIGeometricalElement, CATBody, CATFace, CATIGSOFactory, CATIGSMDevelop, CATICGMHealGaps]
requires: [surface.basics, mecmod.topology]
patterns: [analyzer.geometry]
examples: []
release: [R19, R28]
tags: [pattern, surface, analysis, flatten]
---

# Surface Analysis Pattern (曲面分析自动化)

遍历曲面特征，检查连续性、间隙、可展平性，输出分析报告。

## ⚠️ 重要修正

本文档早期版本存在多处虚构 API，已根据 `capabilities/geometry-query.md`、`capabilities/surface-operations.md`、`playbooks/pb_surface_analysis.md` 的已核实结论修正：

| 旧写法（虚构/错误） | 真实情况 |
|---------------|---------|
| `CATIGSMConnectChecker` 接口 | 完全虚构，工具索引在类型名、方法名、`.dic`、SDK 枚举里均零匹配 |
| `GetAllFaces(iBody, faces)` | `CATBody` 没有 `GetAllFaces()`。真实做法是 `CATBody::GetAllCells(list, 2)` + 逐个 `IsATypeOf(CATFaceType)` 过滤 |
| `CATBody::GetSurfaceArea` | 不存在。面积是逐个 `CATFace::CalcArea()` 取得，没有 Body 级别的一步汇总方法 |
| `pFactory->CreateDevelop(faces[i], dir, &pFlat)`（`CATIGSMFactory`） | `CATIGSMFactory`（`GSMInterfaces`）没有 `CreateDevelop()`。真实方法在**另一个工厂接口 `CATIGSOFactory`**（`GSOInterfaces`），签名是 `CreateDevelop(CATGSMDevelopMethod, CATISpecObject_var iToDevelop, CATISpecObject_var iSupport, boolean=TRUE)`，按 Feature（不是按 Face）展开，返回 `CATIGSMDevelop_var` |
| 间隙检查用 `CATIGSMConnectChecker` | 没有这个高层接口。真实的间隙检测/修复是低层 CGM 算子 `CATICGMHealGaps`（`GMOperatorsInterfaces`）：`GetEdgesWithGaps()`/`GetGap(CATEdge*)`/`GetMaxGap()`/`SetMaxGapToHeal()` 等；这是几何建模层的算子，不是 GSM Feature 级别的简单封装 |

## 适用场景

- 曲面质量检查（Class A 标准）
- 表皮展平预处理
- 模具分型面分析
- 间隙/干涉检测

## 流程

```
遍历 Body 中所有 Face（GetAllCells + IsATypeOf(CATFaceType)）
    ↓
├── 面积计算（CATFace::CalcArea()）
├── 曲率检查（G0/G1/G2，需 CATSurface::EvalLocal() 手动求导）
├── 相邻面间隙检查（CATICGMHealGaps，低层 CGM 算子）
├── 可展平性评估（Gaussian曲率≈0，无现成方法，需手动计算）
└── 展平预览（CATIGSOFactory::CreateDevelop()，可选）
    ↓
输出分析报告
```

## 实现框架

```cpp
class ATSurfaceAnalyzer {
public:
    HRESULT AnalyzeBody(CATBody *iBody);
    HRESULT SetContinuityThreshold(double iGapTol, double iAngTol);

    struct FaceAnalysis {
        double area;
        double minCurvature, maxCurvature;
        CATBoolean isDevelopable;  // 可展平？
        CATListValCATEdge boundaries;
    };

    struct GapAnalysis {
        CATISpecObject *face1, *face2;
        double minGap, maxGap;
        CATBoolean isTangent;  // G1 连续？
    };

    CATListValFaceAnalysis Results();
    CATListValGapAnalysis Gaps();
};
```

## 面积统计

```cpp
// CATBody 没有 GetAllFaces()/GetSurfaceArea()；真实做法：GetAllCells + IsATypeOf 过滤 + CalcArea 累加
HRESULT ComputeTotalArea(CATBody *iBody, double &oTotalArea) {
    oTotalArea = 0.0;
    CATListOfCATCells cells;
    iBody->GetAllCells(cells, 2);   // dimension 2 = faces

    for (int i = 1; i <= cells.Size(); i++) {
        CATCell* cell = cells[i];
        if (cell && cell->IsATypeOf(CATFaceType)) {
            CATFace* pFace = (CATFace*)cell;
            oTotalArea += pFace->CalcArea();
        }
    }
    return S_OK;
}
```

## 展平自动化

```cpp
// 展平的真实工厂是 CATIGSOFactory（GSOInterfaces），不是 CATIGSMFactory；
// 且是按 Feature（CATISpecObject）展开，不是按单个 CATFace*
HRESULT FlattenFeature(CATIGSOFactory_var iGSOFactory,
                        CATISpecObject_var iToDevelop,
                        CATISpecObject_var iSupport,
                        CATIGSMDevelop_var &oFlattened) {
    if (NULL_var == iGSOFactory) return E_FAIL;

    oFlattened = iGSOFactory->CreateDevelop(
        CATGSMDevelopMethod_DevDev,   // 展开方式：枚举，非任意 int
        iToDevelop, iSupport, TRUE);

    return (NULL_var != oFlattened) ? S_OK : E_FAIL;
}
```

## 间隙检测（低层 CGM 算子）

```cpp
// 没有 GSM 级别的 "CATIGSMConnectChecker"；间隙检测是 CGM 算子 CATICGMHealGaps
// 通常需要通过 CATCGMCreateHealGaps 之类的算子创建函数获取（GMOperatorsInterfaces 框架）
HRESULT CheckGaps(CATICGMHealGaps *iHealGaps, CATListOfDouble &oGaps) {
    CATLISTP(CATEdge) edgesWithGaps;
    iHealGaps->GetEdgesWithGaps(edgesWithGaps);

    for (int i = 1; i <= edgesWithGaps.Size(); i++) {
        double gap = iHealGaps->GetGap(edgesWithGaps[i]);
        oGaps.Append(gap);
    }
    return S_OK;
}
```

## 关键设计点

1. **分级检查** — G0(位置) → G1(切矢) → G2(曲率)
2. **展平前验证** — 双曲率面不可精确展平，需近似；可展平性本身没有现成的一步判定方法
3. **可视化输出** — 颜色映射曲率/间隙分布
4. **批量处理** — 支持多 Body、多 Part 批量分析

## AI 生成规则

- [ ] Face 遍历统一用 `GetAllCells(list, 2)` + `IsATypeOf(CATFaceType)`，不要臆造 `GetAllFaces()`
- [ ] 面积用 `CATFace::CalcArea()` 逐面累加，不要臆造 Body 级别的 `GetSurfaceArea()`
- [ ] 展平用 `CATIGSOFactory::CreateDevelop()`（`GSOInterfaces`），不要与 `CATIGSMFactory`（`GSMInterfaces`）混淆
- [ ] 间隙检查用低层算子 `CATICGMHealGaps`，不要臆造高层 GSM 封装接口
- [ ] 不可展平面标记警告，不强制展平
- [ ] 分析结果输出结构化报告
