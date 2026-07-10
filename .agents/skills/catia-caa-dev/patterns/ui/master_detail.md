---
id: ui.master_detail
title: Master-Detail Layout
category: pattern
domain: ui
keywords: [dialog, list, detail, selectorlist, grid, master-detail, properties]
apis: [CATDlgDialog, CATDlgSelectorList, CATDlgFrame, CATDlgEditor, CATDlgCombo, CATDlgPushButton]
requires: [ui.dialog]
patterns: [block.visitor]
examples: []
release: [R19, R28]
tags: [pattern, ui, layout, master-detail]
---

# Master-Detail Pattern (列表-详情模式)

左侧选择条目，右侧编辑详情。CAA 中对标 CATIA 自身的 Properties 对话框。

## 适用场景

- BOM 编辑（左侧产品列表 → 右侧属性修改）
- 配置管理（左侧配置项 → 右侧参数编辑）
- 批量重命名预览（左侧原名 → 右侧新名预览）
- 检查结果（左侧问题列表 → 右侧详情描述）

## 布局结构

```
┌──────────────────────────────────────────────┐
│ [Search: ________________________] [🔍]       │
├──────────────────┬───────────────────────────┤
│  SelectorList    │  Properties                │
│  ┌──────────────┐│  ┌───────────────────────┐ │
│  │ ■ Item 1     ││  │ Name:  [___________]  │ │
│  │   Item 2     ││  │ Type:  [Combo ▼]      │ │
│  │   Item 3     ││  │ Value: [Spinner]      │ │
│  │   Item 4     ││  └───────────────────────┘ │
│  └──────────────┘│                            │
│  [Add] [Remove]  │  [Apply] [Reset]           │
├──────────────────┴───────────────────────────┤
│ Status: 3 items selected             [OK] [Cancel] │
└──────────────────────────────────────────────┘
```

## 三层嵌套框架

```
Dialog
 ├── SearchFrame   (CATDlgGridLayout, Row 0)
 ├── MainFrame     (水平, Row 1)
 │    ├── LeftPanel  (CATDlgSunkenFrame)
 │    │    ├── List
 │    │    └── AddBtn / RemoveBtn
 │    └── RightPanel (CATDlgGroupFrame)
 │         ├── NameEditor
 │         ├── TypeCombo
 │         └── ApplyBtn / ResetBtn
 └── BottomFrame   (水平, Row 2) → Status + OK/Cancel
```

## 实现模板

完整实现参考: [layout_advanced.md §1](../../knowledge/ui/layout_advanced.md)

## 关键设计点

1. **左侧列表使用 `CATDlgSelectorList` + `CATDlgLstSingleSelection`**
2. **右侧详情用 `CATDlgFraGroupFrame` 带标题 "Properties"**
3. **选择联动**: List 选中 → 填充右侧控件 → RemoveBtn 启用
4. **数据缓存**: 内存中保留当前选中项的数据，切换时无需重新读取
5. **搜索过滤**: 顶部的 SearchEditor 过滤列表内容
6. **底部按钮栏独立**: Status/OK/Cancel 在单独的 BottomFrame

## AI 生成规则

- [ ] 三层嵌套: SearchFrame / MainFrame(左+右) / BottomFrame
- [ ] 左侧 Frame 用 `CATDlgFraSunkenFrame`
- [ ] 右侧 Frame 用 `CATDlgFraGroupFrame` + `SetTitle`
- [ ] 绑定 SelectorList 的 selection notification
- [ ] 搜索用 `GetEditorNotification` 实时过滤，不需要点击搜索按钮
