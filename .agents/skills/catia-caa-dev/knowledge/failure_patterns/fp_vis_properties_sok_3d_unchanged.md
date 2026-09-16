---
id: fp.vis_properties_sok_3d_unchanged
title: VisProperties API Returns S_OK but 3D Color Unchanged (VisProperties 返回成功但 3D 视图未生效)
category: knowledge
domain: failure_patterns
severity: silent_failure
apis: [CATIVisProperties, CATModifyVisProperties, Selection, VisPropertySet]
frameworks: [Visualization, CATGraphicProperties]
keywords: [color, visualization, S_OK, 3D unchanged, 未生效, 颜色不变, override, BRep Face, Refresh, CommitNow, CATModify]
tags: [failure_pattern, runtime, visualization, override]
release: [R28]
automation: guide
---

# VisProperties API Returns S_OK but 3D Color Unchanged (VisProperties 返回成功但 3D 视图未生效)

## 症状

在编写 CAA 命令或脚本对模型进行着色时，API 调用完全正常，所有返回值均指示成功，但 CATIA 3D 视口中模型颜色完全没有改变：

- 调用 `CATIVisProperties::SetPropertiesAtt(...)` 返回 `S_OK`。
- 调用 `Selection.VisProperties.SetColor(...)` 返回 `S_OK`。
- 3D 视图未报错，未发生崩溃，但视觉外观没有任何更新。

---

## 常见误区与排查路径校准

### ❌ 常见的错误推理

开发者在看到“S_OK 但视图未改变”时，极易直觉性地认为是“未触发刷新”，从而开始盲目尝试各种刷新或更新 API：
- 连续调用 `CATModifyVisProperties`
- 反复调用 `CommitNow` / `Viewer::Update`
- 调用 `CATISpecObject::Update` 甚至全局重建

**修正原则**：
> **在该症状成立后，不应把继续堆叠刷新/更新调用作为默认排查路径。**
> 
> 盲目堆叠刷新不仅无法解决渲染覆盖问题，还可能引起性能损耗或触发不必要的特征重算副作用。应当优先检查属性覆盖层级。

---

## 真正根因分析

在 CATIA V5 R2018 / B28 实测验证中，该症状绝大多数情况下源自**图形属性覆盖（Property Override）**：

1. **细粒度拓扑覆盖优先**：
   目标 Feature 或 Body 内部的部分拓扑面（BRep Face）先前已被赋予了显式颜色（例如通过交互选面着色或特定历史操作）。
2. **底层覆盖屏蔽上层赋值**：
   在 Feature 或 Body 级赋予的新属性虽然已成功写入数据结构并返回 `S_OK`，但渲染引擎在绘制时，BRep Face 上的显式属性覆盖具有更高的呈现优先级，直接屏蔽了上层新颜色的显示。

---

## 正确修复与处理步骤

1. **第一步：确认操作的目标层级**
   排查传入 `CATIVisProperties` 的对象是 Part、Body、Feature 还是具体的 BRep 子元素。
2. **第二步：排查是否存在局部面覆盖**
   在交互界面选中模型进入“图形属性”面板，观察是否有部分面标记为特异颜色；或通过 CAA 检查其拓扑面的属性是否为“继承”。
3. **第三步：清除或重置子拓扑覆盖**
   - 若要让整件统一着色，必须先清除底层面的覆盖属性，使其恢复继承状态。
   - 官方标准方案应确保在特征级着色前，拓扑单元未被施加私有属性覆盖。
