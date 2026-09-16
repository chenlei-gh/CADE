---
id: mecmod.vis_properties_hierarchy
title: B28 Verified Property-Override Behavior (B28 实测属性覆盖行为)
category: knowledge
domain: mecmod
keywords: [visualization, color, graphic properties, BRep Face, override, CATIVisProperties, CATModifyVisProperties, Selection, VisPropertySet, 属性覆盖, 颜色优先级, B28]
apis: [CATIVisProperties, CATModifyVisProperties, Selection, VisPropertySet]
frameworks: [Visualization, CATGraphicProperties, MecModInterfaces]
requires: [cap.visualization]
patterns: []
examples: []
release: [R28]
tags: [visualization, mecmod, override, b28_verified]
---

# B28 Verified Property-Override Behavior (B28 实测属性覆盖行为)

## 证据边界 (Evidence Scope)

- **测试环境**：CATIA V5 R2018 / B28
- **实测场景**：Part / Assembly 环境下针对几何体与 BRep 元素的显式图形属性赋予与覆盖测试
- **适用说明**：本文档记录的是**在特定测试场景中观察到的覆盖表现（observed override behavior）**，**绝不能**外推为 CATIA 的全局渲染公理或全版本不变的优先级法则。

---

## 1. 现象与观察到的覆盖关系

在 CATIA V5 B28 环境中进行零件着色与属性管理时，对 Feature 或 Body 赋予颜色成功（返回 `S_OK`），但在 3D 视图中模型部分或全部面可能仍然显示旧颜色。

实测观察到的图形属性覆盖表现为：

```text
显式 BRep Face 属性覆盖
       ↓ (优先显示)
Feature / 几何特征级属性
       ↓ (优先显示)
Body / 实体级属性
       ↓ (优先显示)
Part / 根节点全局属性
```

### 关键机制解释

1. **BRep 细粒度覆盖**：如果用户或外部工具曾在交互界面中直接点选了面（Face）并修改了颜色，CATIA 会在底层拓扑单元（BRep Face）上记录独立的图形属性条目。
2. **高层赋予无法穿透局部覆盖**：当后续在 Feature（如 Pad/Pocket）或 Body 级别调用 `CATIVisProperties::SetPropertiesAtt` 或 `Selection.VisProperties.SetColor` 时，高层级的属性虽然成功写入并返回 `S_OK`，但渲染管道在遍历到存在显式 Face Override 的拓扑元素时，优先采用面级属性，导致宏观视觉上“设置成功但 3D 未改变”。

---

## 2. 权威排查与验证思路

当遇到颜色设置不生效时，排查重点不应是反复调用刷新，而是验证目标拓扑是否已有局部覆盖：

1. **检查属性层级**：确认当前目标对象是在哪个层级被着色（Part / Body / Feature / Face）。
2. **排查子拓扑覆盖**：若修改 Body/Feature 颜色无反应，需检查构成该特征的拓扑面是否已被独立赋色。
3. **官方规范通路**：
   - 全局着色：走规范的 `Selection.VisProperties` 或 `CATIVisProperties` 流程。
   - 局部重置：若需清除子拓扑覆盖，官方交互中通过图形属性面板的“Reset/继承”完成；在 CAA 编程中应注意避免在无需局部特异性的场景中直接对 BRep Face 赋予显式颜色。
