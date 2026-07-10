---
id: fta.auto_annotate
title: Auto Annotation & Check
category: pattern
domain: fta
keywords: [auto, annotation, dimension, tolerance, check, capture, 3D, PMI]
apis: [CATITPSSet, CATITPSView, CATITPSDimension, CATITPSTolerance, CATITPSDatum]
requires: [fta.basics, mecmod.topology]
patterns: [analyzer.geometry]
examples: []
release: [R19, R28]
tags: [pattern, fta, annotation, check]
---

# Auto 3D Annotation Pattern (自动3D标注模式)

基于间隙检测和模板规则，自动生成 3D PMI 标注（尺寸/公差/基准）。

## 适用场景

- 零部件量产前自动标注
- 基于模板的标准化标注
- 间隙/配合面自动标注
- 3D Check 报告中标注关键尺寸

## 流程

```
加载 Part
    ↓
读取标注模板/规则表
    ↓
遍历几何
    ↓
├── 检测间隙面 → 标注间隙尺寸
├── 检测孔特征 → 标注孔径/深度
├── 检测配合面 → 标注形位公差
├── 检测基准面 → 标注 Datum
└── 检测对称体 → 标注对称符号
    ↓
创建 Capture + View
    ↓
输出标注报告（哪些标注了/哪些跳过）
```

## 实现框架

```cpp
class ATAutoAnnotation {
public:
    struct AnnotationRule {
        CATUnicodeString featureType;  // "Hole", "Pocket", "Gap"
        CATUnicodeString annotationType;  // "Diameter", "Distance"
        double tolerance;
        CATUnicodeString datumRef;
    };
    
    struct AnnotationReport {
        int totalFeatures;
        int annotatedCount;
        int skippedCount;
        CATListValCATUnicodeString skippedReasons;
    };
    
    HRESULT LoadRules(const CATUnicodeString &iRuleFile);
    HRESULT Execute(CATISpecObject *iPart,
                      AnnotationReport &oReport);
    
private:
    HRESULT AnnotateHoles(CATISpecObject *iPart, CATITPSView *iView);
    HRESULT AnnotateGaps(CATISpecObject *iPart, CATITPSView *iView);
    HRESULT AnnotateDatums(CATISpecObject *iPart, CATITPSView *iView);
    CATITPSDimension *CreateDimensionWithTolerance(
        CATITPSView *iView, CATISpecObject *iElem1,
        CATISpecObject *iElem2, CATMathPoint &iPos,
        double upperTol, double lowerTol);
};

// 自动标注孔特征
HRESULT ATAutoAnnotation::AnnotateHoles(
    CATISpecObject *iPart, CATITPSView *iView) {
    
    CATListValCATISpecObject holes;
    FindFeaturesByType(iPart, "Hole", holes);
    
    for (int i = 1; i <= holes.Size(); i++) {
        CATISpecObject *pHole = holes[i];
        
        // 获取孔的参数
        CATIHole_var spHole = GetInterface<CATIHole>(pHole);
        double diameter = spHole->GetDiameter();
        double depth = spHole->GetDepth();
        
        // 标注直径
        CATMathPoint pos = GetAnnotationPosition(pHole);
        CATITPSDimension *pDim = CreateDiameterDim(
            iView, pHole, pos);
        
        // 加公差
        CreateTolerance(iView, pDim,
            diameter + 0.01, diameter - 0.0);
        
        m_report.annotatedCount++;
    }
    return S_OK;
}
```

## 关键设计点

1. **规则驱动** — 标注规则从外部配置文件读取，不硬编码
2. **间隙检测** — 遍历相邻面，间隙 < 阈值则自动标注
3. **公差模板** — 按特征类型预定义公差带（H7, H8, +0.01/-0 等）
4. **视图分组** — 尺寸按视图方向（Front/Top/Right）自动分组
5. **跳过报告** — 记录哪些特征未标注及原因

## AI 生成规则

- [ ] 标注规则外置为 JSON/CSV 配置文件
- [ ] 特征遍历用 `IsATypeOf` 检测
- [ ] 每个 Annotate 方法处理一种特征类型
- [ ] 标注位置自动计算，避免重叠
- [ ] 输出标注摘要：total / annotated / skipped
