---
id: block.visitor
title: Feature Visitor
category: pattern
domain: blocks
keywords: [visitor, traverse, recursion, tree, iterate, children, feature tree, walk]
apis: [CATISpecObject, CATIPrtPart]
requires: [mecmod.feature]
patterns: [analyzer.geometry, analyzer.rule]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [block, traversal, recursion]
---

# Feature Visitor (递归遍历积木)

可复用的递归遍历 Feature 树的最小代码块。几乎所有几何分析工具都需要它。

## 核心代码

```cpp
void TraverseFeatures(CATISpecObject_var pParent) {
    CATListValCATISpecObject_var children;
    pParent->GetChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var child = children[i];

        // 回调：处理当前 Feature
        OnFeature(child);

        // 递归子节点
        TraverseFeatures(child);
    }
}
```

## 用法

```cpp
// AI 组合：Visitor + Rule
class MyAnalyzer {
    void Analyze(CATIPrtPart_var pPart) {
        CATISpecObject_var pRoot = pPart;
        TraverseFeatures(pRoot);  // ← Block: Visitor
    }

    void OnFeature(CATISpecObject_var pFeature) {
        // 这里嵌入 Rule Block
        CheckRule(pFeature);
    }
};
```

## 变体

```cpp
// 仅遍历叶子节点
void TraverseLeaves(CATISpecObject_var pParent) {
    CATListValCATISpecObject_var children;
    pParent->GetChildren(children);

    if (children.Size() == 0) {
        OnLeaf(pParent); // 叶子节点
        return;
    }

    for (int i = 1; i <= children.Size(); i++) {
        TraverseLeaves(children[i]);
    }
}

// 按类型过滤的遍历
void TraverseByType(CATISpecObject_var pParent, const CATUnicodeString& type) {
    CATListValCATISpecObject_var children;
    pParent->GetChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var child = children[i];
        if (child->IsATypeOf(type)) {
            OnFeature(child); // 仅处理匹配类型
        }
        TraverseByType(child, type);
    }
}
```
