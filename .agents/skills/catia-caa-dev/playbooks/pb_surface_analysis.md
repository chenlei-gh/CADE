---
id: pb.surface_analysis
title: Surface Analysis Report / 曲面分析报告
category: playbook
domain: surface
keywords: [surface, GSD, analysis, curvature, flatten, area, report, export, offset, sweep, extrude]
capabilities: [cap.surface_operations, cap.geometry_query, cap.document_export, cap.parameter_system]
apis: [CATIGeometricalElement, CATBody, CATFace, CATIGSOFactory, CATIGSMDevelop]
frameworks: [MecModInterfaces, GMModelInterfaces, GSOInterfaces, AutomationInterfaces]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, surface, GSD, analysis, report]
---

# Surface Analysis Report (曲面分析报告)

对 GSD 曲面进行系统分析：展平面积、曲率分布、最小曲率半径检测、拔模角度检查，并生成分析报告。

## ⚠️ 重要修正

本文档早期版本存在多处虚构/错误 API，已根据 `capabilities/geometry-query.md`、`capabilities/surface-operations.md` 的已核实结论修正：

| 旧写法（虚构/错误） | 真实情况 |
|---------------|---------|
| `spBody->GetAllFaces(faces)` | `CATBody` 没有 `GetAllFaces()` 方法。真实做法是 `CATBody::GetAllCells(list, 2)` 拿到所有 2 维 Cell，再逐个 `IsATypeOf(CATFaceType)` 过滤出 `CATFace`（参考 `capabilities/geometry-query.md` 4.1） |
| `CATMathCurve::GetLength()` + 积分 求曲面面积 | `CATMathCurve` 只有 4 个方法（`GetMathType()`/`IsA()`/`IsATypeOf()`/析构），没有 `GetLength()`，也不需要靠曲线长度积分算面积。真实方法是直接调用 `CATFace::CalcArea()` 拿到面积（`GMModelInterfaces` 框架） |
| `CATIGSMFactory::CreateDevelop()` | 归属接口错误。`CATIGSMFactory`（`GSMInterfaces`）没有 `CreateDevelop()`。真实的展平创建方法是 **`CATIGSOFactory::CreateDevelop(CATGSMDevelopMethod iMode, CATISpecObject_var iToDevelop, CATISpecObject_var iSupport, boolean iInstanciateTransfo=TRUE)`**，属于 **`GSOInterfaces`** 框架的另一个工厂接口，返回 `CATIGSMDevelop_var` |
| `CATBody` 的 Face 遍历用 `GetAllFaces()` 而非 `ListCells()`（性能更好） | 两个方法名都不存在。唯一真实的 Cell 遍历方法是 `GetAllCells(list, dimension)` |

## 目标

选中一组曲面 → 自动执行多项分析 → 生成包含数值和可视化结果的报告（Excel/JSON）。

## 前置条件

- 已加载包含 GSD 曲面 Feature 的 CATPart
- 可选：通过 Selection 预选曲面
- 可选：报告输出路径

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.surface_operations` | 展平、偏移、扫掠等曲面操作 |
| `cap.geometry_query` | 获取曲面拓扑和几何数据 |
| `cap.parameter_system` | 读取 Feature 参数（面积/曲率） |
| `cap.document_export` | 导出分析报告 |

## 实现步骤

1. **获取选中曲面**：遍历 Part 中的 GSM Feature（Extrude/Sweep/Offset/Blend...）
2. **拓扑分解**：Feature QI 到 `CATIGeometricalElement`，`GetBodyResult()` 拿到 `CATBody`，再 `GetAllCells(list, 2)` + `IsATypeOf(CATFaceType)` 取出各 `CATFace`
3. **执行分析**：
   - 曲面面积 → 逐面 `CATFace::CalcArea()` 累加
   - 最小曲率半径 → 采样点检查（需用 `CATSurface::EvalLocal()` 拿一阶/二阶导数手动计算曲率，没有现成的"一步取曲率"方法）
   - 拔模角 → 检查法向与拔模方向的夹角
4. **展平（可选）**：`CATIGSOFactory::CreateDevelop(mode, pFeatureToDevelop, pSupportSurface)`（注意这是 `CATIGSOFactory`，不是 `CATIGSMFactory`）
5. **生成报告**：按曲面 ID 输出分析表
6. **可视化标记**：高亮不合格曲面（如曲率过大、面积异常）

## 分析项

```cpp
struct SurfaceAnalysisItem {
    CATUnicodeString featureId;
    CATUnicodeString surfaceType;   // Extrude, Sweep, Offset...
    double area;                     // 曲面面积
    double minCurvatureRadius;       // 最小曲率半径
    double maxCurvatureRadius;       // 最大曲率半径
    double draftAngle;               // 拔模角（如果是模具面）
    CATUnicodeString status;         // PASS, WARN, FAIL
};
```

## 关键代码

```cpp
HRESULT AnalyzeSurface(CATISpecObject_var iGsmFeature,
                       SurfaceAnalysisItem &item) {
    // 1. 获取 Body
    CATIGeometricalElement_var spGeom = iGsmFeature;
    if (NULL_var == spGeom) return E_FAIL;

    CATBody_var spBody = spGeom->GetBodyResult();
    if (NULL_var == spBody) return E_FAIL;

    // 2. 遍历 Face：CATBody 没有 GetAllFaces()，真实方法是 GetAllCells(list, dim)
    CATListOfCATCells cells;
    spBody->GetAllCells(cells, 2);   // dimension 2 = faces

    double totalArea = 0.0;
    for (int i = 1; i <= cells.Size(); i++) {
        CATCell* cell = cells[i];
        if (!cell || !cell->IsATypeOf(CATFaceType)) continue;
        CATFace* pFace = (CATFace*)cell;

        totalArea += pFace->CalcArea();   // 直接取面积，不是靠曲线长度积分
        // 曲率采样：需要 CATSurface::EvalLocal() 手动求导计算，此处从略
    }
    item.area = totalArea;
    return S_OK;
}

// 展平：真实工厂是 CATIGSOFactory（GSOInterfaces），不是 CATIGSMFactory
HRESULT FlattenFeature(CATISpecObject_var iToDevelop,
                        CATISpecObject_var iSupport,
                        CATIGSMDevelop_var &oResult) {
    CATIGSOFactory_var spGSOFactory = ...;   // 从 GeometricalSet/OrderedGeometricalSet QI 获取
    if (NULL_var == spGSOFactory) return E_FAIL;

    oResult = spGSOFactory->CreateDevelop(
        CATGSMDevelopMethod_DevDev,   // 展平方式（枚举，非任意 int）
        iToDevelop, iSupport, TRUE);
    return (NULL_var != oResult) ? S_OK : E_FAIL;
}
```

## 注意事项

- 曲面展平（Develop）计算量大，建议对大曲面降采样
- GSD 曲面可能引用其他 Feature（如 Sweep 引用 Guide Curve），修改前做影响分析
- `CATBody` 的 Face 遍历唯一真实方法是 `GetAllCells(list, 2)` + `IsATypeOf(CATFaceType)` 过滤，没有 `GetAllFaces()`/`ListCells()` 这类捷径
- 报告生成建议用 JSON 格式（比 CSV 更适合嵌套曲面数据）

## 相关 Playbook

- `pb.geometry_quality_check` — 类似思路，针对 Part Design 而非 GSD
