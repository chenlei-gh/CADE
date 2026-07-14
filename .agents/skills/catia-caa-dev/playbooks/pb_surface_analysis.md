---
id: pb.surface_analysis
title: Surface Analysis Report / 曲面分析报告
category: playbook
domain: surface
keywords: [surface, GSD, analysis, curvature, flatten, area, report, export, offset, sweep, extrude]
capabilities: [cap.surface_operations, cap.geometry_query, cap.document_export, cap.parameter_system]
apis: [CATIGSMFactory, CATIGSMSweep, CATIGSMOffset, CATBody, CATFace, CATMathCurve]
frameworks: [CATGSMUseItf, CATMecModUseItf, AutomationInterfaces]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, surface, GSD, analysis, report]
---

# Surface Analysis Report (曲面分析报告)

对 GSD 曲面进行系统分析：展平面积、曲率分布、最小曲率半径检测、拔模角度检查，并生成分析报告。

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
2. **拓扑分解**：`CATBody` → `CATFace` → 获取各面几何数据
3. **执行分析**：
   - 曲面面积 → `CATMathCurve::GetLength()` + 积分
   - 最小曲率半径 → 采样点检查
   - 拔模角 → 检查法向与拔模方向的夹角
4. **展平（可选）**：`CATIGSMFactory::CreateDevelop()`
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
HRESULT AnalyzeSurface(CATISpecObject *iGsmFeature,
                       SurfaceAnalysisItem &item) {
    // 1. 获取 Body
    CATIGeometricalElement_var spGeom = iGsmFeature;
    if (NULL_var == spGeom) return E_FAIL;

    CATBody_var spBody = spGeom->GetBodyResult();
    if (NULL_var == spBody) return E_FAIL;

    // 2. 遍历 Face
    CATListPtrCATFace faces;
    spBody->GetAllFaces(faces);
    
    for (int i = 1; i <= faces.Size(); i++) {
        CATFace *pFace = faces[i];
        // 曲率采样...
        // 面积积分...
    }
    return S_OK;
}
```

## 注意事项

- 曲面展平（Develop）计算量大，建议对大曲面降采样
- GSD 曲面可能引用其他 Feature（如 Sweep 引用 Guide Curve），修改前做影响分析
- CATBody 的 Face 遍历用 `GetAllFaces()` 而非 `ListCells()`（性能更好）
- 报告生成建议用 JSON 格式（比 CSV 更适合嵌套曲面数据）

## 相关 Playbook

- `pb.geometry_quality_check` — 类似思路，针对 Part Design 而非 GSD
