---
id: philo.late_types
title: Late Type Mechanism / Late Type 派生链
category: knowledge
domain: philosophy
keywords: [late type, derivation, CATDerivation, CATISpecObject, TIE, BOA, inheritance]
apis: [CATISpecObject, CATIDerivation, CATDerivation, CATBaseUnknown]
frameworks: [ObjectModelerBase, ObjectSpecsModeler]
release: [R19, R28]
tags: [philosophy, late_type, core]
---
# Late Type Mechanism

Late Type 是 CATIA 对象模型的类型派生机制。它允许在不修改原始类代码的情况下，给已有类型添加新的接口和行为。

## 核心概念

```text
CATBaseUnknown
    │
    ▼
CATISpecObject  (基础规格对象)
    │
    ▼
Late Type: Pad  ─── 实现: CATIPad, CATIMechanicalFeature, CATIPrtFeature
    │
    ▼
Late Type: Draft ─── 继承 Pad + 实现: CATIDraft
```

## StartUp Catalog 和 Late Type

```cpp
// 注册 Late Type
CATImplementClass(MyFeature, DataExtension, CATBaseUnknown, MyFeatureStartUp);
```

StartUp Catalog（`CATICatalog`）记录 Late Type 的"原型"：
- 属性默认值
- 父类型引用
- 必须实现的接口列表

## Reference vs Instance

CAA 中每个 Feature 有两个层面：
- **Reference** (`CATISpecObject` on Reference) — 模板/定义
- **Instance** (`CATISpecObject` on Instance) — 实际出现的位置

```cpp
// 获取 Reference
CATISpecObject_var spRef = spInstance;
CATIDerivation_var spDeriv = spRef;
spDeriv->GetReference(spRefRoot);

// 判断是 Reference 还是 Instance
CATBoolean isRef = FALSE_VAR;
spDeriv->IsReference(isRef);
```

## AI 生成规则

- [ ] 创建 Feature 时必须指定 StartUp 对象
- [ ] 使用 `CATDeclareClass` / `CATImplementClass` 声明 Late Type
- [ ] 在 Dictionary 中注册 Late Type 映射
- [ ] Late Type 的父类型决定默认行为和可用的接口
- [ ] IsATypeOf / IsAKindOf 用于类型检查（不是 dynamic_cast）
