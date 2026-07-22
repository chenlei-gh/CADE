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

## ⚠️ 重要修正

之前版本使用的 `CATDlgSunkenFrame` / `CATDlgGroupFrame` / `CATDlgFraGroupFrame` / `CATDlgFraSunkenFrame` / `CATDlgLstSingleSelection` 经核实**均不存在**。Frame 真实风格只有 `CATDlgFraNoTitle`/`CATDlgFraNoFrame`/`CATDlgFraNoMargin`；列表多选风格只有 `CATDlgLstMultisel`（不加即单选）。分组标题效果 = 默认 Frame（不加 NoTitle）+ `SetTitle()`。

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
│  SelectorList    │  Properties（带标题 Frame） │
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
 ├── SearchFrame   (CATDlgFraNoFrame | CATDlgGridLayout, Row 0)
 ├── MainFrame     (CATDlgFraNoFrame 水平, Row 1)
 │    ├── LeftPanel  (CATDlgFraNoFrame | CATDlgGridLayout)
 │    │    ├── SelectorList
 │    │    └── AddBtn / RemoveBtn
 │    └── RightPanel (默认带标题 Frame + SetTitle("Properties"))
 │         ├── NameEditor
 │         ├── TypeCombo
 │         └── ApplyBtn / ResetBtn
 └── BottomFrame   (CATDlgFraNoFrame 水平, Row 2) → Status + OK/Cancel
```

## 实现模板

```cpp
void MasterDetailDlg::Build() {
    // --- Row 0: 搜索栏 ---
    CATDlgFrame *pSearchFrame = new CATDlgFrame(this, "SearchF",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pSearchEditor = new CATDlgEditor(pSearchFrame, "SearchEdt");
    _pSearchEditor->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));

    // --- Row 1: 主区 ---
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainF", CATDlgFraNoFrame);

    // 左侧列表（不加风格位 = 单选；多选用 CATDlgLstMultisel）
    CATDlgFrame *pLeft = new CATDlgFrame(pMain, "LeftF",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pList = new CATDlgSelectorList(pLeft, "ItemList");
    _pList->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 2, CATGRID_4SIDES));
    _pAddBtn    = new CATDlgPushButton(pLeft, "AddBtn");
    _pAddBtn->SetGridConstraints(CATDlgGridConstraints(1, 0, 1, 1, CATGRID_LEFT));
    _pRemoveBtn = new CATDlgPushButton(pLeft, "RemoveBtn");
    _pRemoveBtn->SetGridConstraints(CATDlgGridConstraints(1, 1, 1, 1, CATGRID_LEFT));

    // 右侧详情：默认 Frame 带标题栏（不要加 CATDlgFraNoTitle）
    CATDlgFrame *pRight = new CATDlgFrame(pMain, "RightF", CATDlgGridLayout);
    pRight->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_PROPS"));

    _pNameEditor = new CATDlgEditor(pRight, "NameEdt");
    _pNameEditor->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));
    _pTypeCombo = new CATDlgCombo(pRight, "TypeCbo");
    _pTypeCombo->SetGridConstraints(CATDlgGridConstraints(1, 0, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));

    // --- Row 2: 底部按钮栏 ---
    CATDlgFrame *pBottom = new CATDlgFrame(this, "BottomF", CATDlgFraNoFrame);
    _pStatusLabel = new CATDlgLabel(pBottom, "StatusLbl");

    // 选择联动：列表选中 → 填充右侧
    AddAnalyseNotificationCB(_pList, _pList->GetListSelectNotification(),
        (CATCommandMethod)&MasterDetailDlg::OnItemSelected, NULL);
}
```

## 关键设计点

1. **左侧列表 `CATDlgSelectorList`**：不加风格位 = 单选；多选加 `CATDlgLstMultisel`
2. **右侧详情分组**：默认 Frame（保留标题栏）+ `SetTitle("Properties")`，不要发明 GroupFrame 风格
3. **选择联动**: List 选中通知 → 填充右侧控件 → RemoveBtn `SetSensitivity(CATDlgEnable)`
4. **数据缓存**: 内存中保留当前选中项数据，切换时无需重新读取
5. **搜索过滤**: 顶部 SearchEditor 的修改通知实时过滤列表
6. **底部按钮栏独立**: Status/OK/Cancel 在单独的 BottomFrame

## AI 生成规则

- [ ] 三层嵌套: SearchFrame / MainFrame(左+右) / BottomFrame
- [ ] Frame 风格只用 `CATDlgFraNoTitle`/`NoFrame`/`NoMargin`，标题用 `SetTitle`
- [ ] `SetGridConstraints` 单参；水平填充 `CATGRID_LEFT|CATGRID_RIGHT`
- [ ] 绑定 SelectorList 的 `GetListSelectNotification`
- [ ] 搜索用 Editor 修改通知实时过滤，不需要点击搜索按钮
