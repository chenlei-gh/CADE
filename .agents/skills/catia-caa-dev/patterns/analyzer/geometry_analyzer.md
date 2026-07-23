---
id: analyzer.geometry
title: Geometry Analyzer
category: pattern
domain: analyzer
keywords: [analyzer, geometry, check, inspect, traversal, visitor]
apis: [CATISpecObject, CATIPrtPart, CATINewHole, CATIEdgeFillet, CATIChamfer]
requires: [mecmod.feature, part.fillet]
patterns: [block.visitor, analyzer.rule]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [pattern, analyzer, geometry, check]
---

# Geometry Analyzer Pattern (几何分析模式)

遍历 Part Feature Tree，对特定类型的几何特征进行分析和检查。

## 适用场景

- 圆角规范检查
- 孔径合规检查
- 倒角尺寸验证
- 壁厚分析
- 拔模角度检查

## 架构模式

```
Command
  │
  ├── Analysis Class (分析逻辑)
  │     ├── Traverse Features (遍历树)
  │     ├── Filter by Type (按类型过滤)
  │     ├── Check Rules (规则检查)
  │     └── Collect Results (收集结果)
  │
  ├── Dialog (结果展示)
  │     ├── ListView (结果列表)
  │     ├── Status (通过/失败)
  │     └── Double Click Locator (双击定位)
  │
  └── Selection (交互)
        ├── Highlight (高亮)
        └── Reframe (定位)
```

## 实现步骤

### Step 1: 创建 Command

使用 CADE 创建一个标准 Command（带 Dialog）。

### Step 2: 实现 Analyzer 类

```cpp
class GeometryAnalyzer {
public:
    struct Result {
        CATISpecObject_var feature;
        CATUnicodeString name;
        CATUnicodeString type;
        CATUnicodeString problem;
        bool passed;
    };

    void Analyze(CATIPrtPart_var pPart) {
        CATISpecObject_var pRoot = pPart;
        Traverse(pRoot);
    }

    CATListValResult GetResults() { return m_results; }

private:
    void Traverse(CATISpecObject_var pParent) {
        CATListValCATISpecObject_var* pChildren = pParent->ListComponents();
        if (NULL == pChildren) return;
        int nChildren = pChildren->Size();
        for (int i = 1; i <= nChildren; i++) {
            CATISpecObject_var child = (*pChildren)[i];
            CheckFeature(child);
            Traverse(child);
        }
        delete pChildren;
    }

    void CheckFeature(CATISpecObject_var pFeature) {
        // 在此处实现具体的检查逻辑
    }

    CATListValResult m_results;
};
```

### Step 3: 连接 Dialog

在 Command 的 OK/Cancel 回调中调用 Analyzer 并填充 ListView。

### Step 4: 实现双击定位

```cpp
void Dialog::OnListDoubleClick(int line) {
    CATISpecObject_var pFeature = m_results[line].feature;

    // 将特征加入 ISO 高亮集
    CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
    if (NULL == pEditor) return;
    CATISO* pISO = pEditor->GetISO();
    if (NULL != pISO) {
        pISO->Empty();
        pISO->AddElement(pFeature);
    }

    // 通过 Viewer 定位
    CAT3DViewer* pViewer = ...; // 从当前 CATFrmWindow 获取
    if (NULL != pViewer) {
        CAT3DBoundingSphere bs = pViewer->GetGlobalBoundingSphere();
        pViewer->ReframeOn(bs);
    }
}
```

## 关键点

1. **递归遍历**是核心 —— 特征树可能有多层嵌套（如 Body、Geometrical Set）
2. **按类型过滤**使用 `IsSubTypeOf("TypeName")`
3. **结果收集**应包含完整路径，方便定位
4. **双击定位**必须同时做 Highlight（ISO AddElement）+ Reframe（Viewer ReframeOn）
