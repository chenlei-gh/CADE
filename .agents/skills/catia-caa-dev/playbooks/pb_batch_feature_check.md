---
id: pb.batch_feature_check
title: Batch Feature Check / 批量特征检查
category: playbook
domain: part
keywords: [batch, feature, check, fillet, hole, chamfer, validate, rule, filter]
capabilities: [cap.feature_recognition, cap.parameter_system]
apis: [CATISpecObject, CATIFillet, CATIHole, CATIChamfer, CATIPrtPart, IsATypeOf]
frameworks: [ObjectModelerBase, MecModInterfaces, PartInterfaces]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, batch, check, feature]
---
# Batch Feature Check (批量特征检查)

遍历 Part 中所有特征，按规则检查并输出结果。

## 目标

- 检查所有圆角半径是否在范围内
- 检查所有孔径/深度是否符合标准
- 检查倒角角度/长度
- 输出检查报告

## 实现步骤

1. **获取 Part 容器** → `CATIPrtPart_var spPart`
2. **遍历所有特征** → `CATISpecObject` 树遍历
3. **识别特征类型** → `IsATypeOf("CATPad")`, `IsATypeOf("CATFillet")`
4. **获取参数值** → `CATISpecAttribute::GetValue()`
5. **对比规则** → 硬编码规则或配置文件
6. **输出结果** → 对话框列表 + 双击定位

## 关键代码骨架

```cpp
struct CheckResult {
    CATUnicodeString featureName;
    CATUnicodeString checkType;
    CATUnicodeString expected;
    CATUnicodeString actual;
    CATBoolean passed;
};

HRESULT CheckAllFeatures(CATISpecObject *iPart, CATListValCheckResult &oResults) {
    // 获取 Part 接口
    CATIPrtPart_var spPrtPart = iPart;
    if (NULL_var == spPrtPart) return E_FAIL;

    // 遍历机械特征集
    CATListValCATISpecObject features;
    spPrtPart->GetMechanicalFeatures(features);

    for (int i = 1; i <= features.Size(); i++) {
        CATISpecObject_var spFeat = features[i];

        if (spFeat->IsATypeOf("CATFillet")) {
            CheckFillet(spFeat, oResults);
        } else if (spFeat->IsATypeOf("CATHole")) {
            CheckHole(spFeat, oResults);
        }
    }
    return S_OK;
}
```

## 注意事项

- 大 Part（>500 特征）注意遍历性能
- 使用 Visitor 模式而非递归（避免栈溢出）
- 检查规则建议从配置文件读取而非硬编码
- 结果对话框支持导出为 HTML/CSV 报告
