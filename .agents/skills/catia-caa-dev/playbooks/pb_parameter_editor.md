---
id: pb.parameter_editor
title: Parameter Editor / 批量参数编辑
category: playbook
domain: part
keywords: [parameter, formula, relation, edit, modify, batch, attribute, property]
capabilities: [cap.parameter_system, cap.selection, cap.update_mechanism]
apis: [CATICkeParm, CATICkeRelation, CATISpecAttribute, CATISelection, CATISpecObject]
frameworks: [KnowledgeInterfaces, ApplicationFrame, ObjectModelerBase]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, parameter, editor, batch, formula]
---

# Parameter Editor (批量参数编辑)

用户选择多个 Feature，一次性修改它们的公共参数或公式。支持 Excel/CSV 批量导入。

## 目标

提供类似 CATIA Knowledge Advisor 参数表的批量编辑能力：选中 → 列出参数 → 修改 → Update。

## 前置条件

- 已加载包含参数的 Part/Product 文档
- 可选：外部 CSV/Excel 参数表
- 可选：通过 Selection 预选了目标 Feature

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.selection` | 获取用户选中的 Feature 列表 |
| `cap.parameter_system` | 读写参数值/公式 |
| `cap.update_mechanism` | 修改后触发 Update |

## 实现步骤

1. **获取 Selection**：`CATISelection::GetSelection()`
2. **过滤 Feature**：排除非 SpecObject 元素
3. **读取公共参数**：收集所有选中 Feature 的参数名并集
4. **展示编辑对话框**：列表显示 参数名 → 当前值 → 新值
5. **批量赋值**：遍历每个 Feature，`SetValue()` 或 `SetFormula()`
6. **触发 Update**：`CATIModelEvents::Dispatch()`

## 参数结构

```cpp
struct ParamEditItem {
    CATUnicodeString paramName;   // 参数显示名
    CATUnicodeString paramType;   // Length, Angle, Real...
    CATUnicodeString currentValue;
    CATUnicodeString newValue;    // 用户输入
    bool isFormula;               // 是否为公式
};
```

## 关键代码

```cpp
HRESULT BatchEditParams(CATListValCATISpecObject &features,
                        CATListValParamEditItem &edits) {
    for (int i = 1; i <= features.Size(); i++) {
        CATISpecObject_var spFeat = features[i];
        CATICkeParm_var spParm = spFeat;
        if (NULL_var == spParm) continue;

        for (int j = 0; j < edits.Size(); j++) {
            CATUnicodeString name = edits[j].paramName;
            CATUnicodeString value = edits[j].newValue;
            
            if (edits[j].isFormula) {
                spParm->SetFormula(name, value);
            } else {
                spParm->Valuate(value);  // 设置数值
            }
        }
    }
    return S_OK;
}
```

## 注意事项

- 公式引用可能跨 Feature/跨 Part，修改前检查引用完整性
- 参数名区分大小写，建议先 `GetListOfParameters()` 确认
- 批量操作建议加入 Transaction（Undo/Redo 支持）
- CSV 导入时注意编码（CATUnicodeString 使用 UTF-8 输入）

## 相关 Failure Pattern

- `fp.undeclared_class` — 跨文档引用公式可能暴露接口缺失

## 相关 Playbook

- `pb.batch_update_save` — 参数修改后统一 Update + Save
