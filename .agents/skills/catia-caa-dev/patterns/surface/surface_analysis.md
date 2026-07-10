---
id: surface.analysis
title: Surface Analysis & Automation
category: pattern
domain: surface
keywords: [surface, analysis, flatten, develop, continuity, checker, gap]
apis: [CATIGSMFactory, CATIGSMDevelop, CATIGSMConnectChecker, CATBody]
requires: [surface.basics, mecmod.topology]
patterns: [analyzer.geometry]
examples: []
release: [R19, R28]
tags: [pattern, surface, analysis, flatten]
---

# Surface Analysis Pattern (曲面分析自动化)

遍历曲面特征，检查连续性、间隙、可展平性，输出分析报告。

## 适用场景

- 曲面质量检查（Class A 标准）
- 表皮展平预处理
- 模具分型面分析
- 间隙/干涉检测

## 流程

```
遍历 Body 中所有 Face
    ↓
├── 周长/面积计算
├── 曲率检查（G0/G1/G2）
├── 相邻面间隙检查
├── 可展平性评估（Gaussian曲率≈0）
└── 展平预览（可选）
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

## 展平自动化

```cpp
// 展平指定曲面
HRESULT FlattenFaces(CATBody *iBody,
                       CATListValCATISpecObject &oFlattened) {
    CATIGSMFactory *pFactory = CreateFactory(iBody);
    
    CATListValCATFace faces;
    GetAllFaces(iBody, faces);
    
    for (int i = 1; i <= faces.Size(); i++) {
        // 检查可展平性
        if (!IsDevelopable(faces[i])) {
            continue;  // 跳过双曲率面
        }
        
        // 展平
        CATISpecObject *pFlat = NULL;
        CATMathDirection dir = GetBestDirection(faces[i]);
        pFactory->CreateDevelop(faces[i], dir, &pFlat);
        oFlattened.Append(pFlat);
    }
    return S_OK;
}
```

## 关键设计点

1. **分级检查** — G0(位置) → G1(切矢) → G2(曲率)
2. **展平前验证** — 双曲率面不可精确展平，需近似
3. **可视化输出** — 颜色映射曲率/间隙分布
4. **批量处理** — 支持多 Body、多 Part 批量分析

## AI 生成规则

- [ ] 先用 `CATBody::GetSurfaceArea` 快速筛除小面
- [ ] 展平前检查 Gaussian 曲率
- [ ] 间隙检查用 `CATIGSMConnectChecker`
- [ ] 不可展平面标记警告，不强制展平
- [ ] 分析结果输出结构化报告
