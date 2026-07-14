---
id: pb.auto_annotate_3d
title: Auto 3D Annotation / 自动3D标注
category: playbook
domain: fta
keywords: [FTA, 3D annotation, PMI, tolerance, dimension, capture, annotate, auto, GD&T]
capabilities: [cap.annotation, cap.geometry_query, cap.selection]
apis: [CATITPSView, CATITPSAnnotation, CATITPSDimension, CATITPSTolerance, CATBody, CATFace]
frameworks: [CATAnalysisGPSInterfaces, CATMecModUseItf, ApplicationFrame]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, FTA, annotation, 3D, PMI, automation]
---

# Auto 3D Annotation (自动3D标注)

自动为零件几何特征生成 3D 标注（PMI）：尺寸、公差、基准、表面粗糙度。

## 目标

选中零件 → 识别关键几何特征（孔、槽、曲面） → 自动创建对应的 3D 标注 → 组织到 Capture 中。

## 前置条件

- 已加载 CATPart（含实体几何）
- FTA 工作台已激活（或通过 API 创建 Annotation Set）
- 可选：标注规范（公差标准、精度等级）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.annotation` | 创建 3D 标注对象（尺寸/公差/基准） |
| `cap.geometry_query` | 获取几何体的拓扑元素 |
| `cap.selection` | 定位标注附着点 |

## 实现步骤

1. **创建 Annotation Set**：`CATITPSFactory::CreateView()`
2. **遍历几何特征**：识别 Hole/Pad/Pocket/Surface
3. **生成标注**：
   - 孔 → 直径尺寸 + 位置公差
   - 槽 → 长度/宽度尺寸
   - 曲面 → 轮廓度公差
   - 平面 → 基准符号
4. **组织到 Capture**：`CATITPSCapture::AddAnnotation()`
5. **Update 视图**：`CATITPSView::Update()`

## 标注结构

```cpp
struct AnnotationDef {
    CATUnicodeString type;       // "diameter", "distance", "tolerance"...
    CATMathPoint attachPoint;    // 3D 附着点
    CATMathVector direction;     // 标注方向
    double nominalValue;         // 公称值
    double upperTolerance;       // 上偏差
    double lowerTolerance;       // 下偏差
    CATUnicodeString datumRef;   // 基准引用（可选）
};
```

## 关键代码

```cpp
HRESULT AutoAnnotatePart(CATISpecObject *iPart) {
    // 1. Create FTA view
    CATITPSFactory_var spFactory = GetTPSFactory();
    CATITPSView_var spView = spFactory->CreateView("Auto Annotations");

    // 2. Get main body
    CATIPrtPart_var spPrt = iPart;
    CATBody_var spBody = spPrt->GetMainBody();

    // 3. Identify cylindrical faces → hole annotations
    CATListPtrCATFace faces;
    spBody->GetAllFaces(faces);
    for (int i = 1; i <= faces.Size(); i++) {
        CATFace *pFace = faces[i];
        if (IsCylindrical(pFace)) {
            // Create diameter dimension
            CATITPSDimension_var spDim = spFactory->CreateDimension(
                "Diameter", GetCenterPoint(pFace), GetNormal(pFace));
            spDim->SetNominalValue(GetDiameter(pFace));
            spDim->SetTolerance(0.0, 0.1);  // H7 fit example
            spView->AddAnnotation(spDim);
        }
    }

    spView->Update();
    return S_OK;
}
```

## 注意事项

- FTA 标注依赖 Annotation Set 和 Capture 层级结构
- 标注附着点必须在几何面上（`CATMathPoint` on surface）
- 公差标准（ISO/ASME）影响标注符号样式
- 大批量标注建议设置合理的标注间距避免重叠

## 相关 Playbook

- `pb.geometry_quality_check` — 可与质量检查结合，不合格特征标红
