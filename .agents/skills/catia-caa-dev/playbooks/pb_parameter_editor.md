---
id: pb.parameter_editor
title: Parameter Editor / 批量参数编辑
category: playbook
domain: part
keywords: [parameter, formula, relation, edit, modify, batch, attribute, property]
capabilities: [cap.parameter_system, cap.selection, cap.update_mechanism]
apis: [CATICkeParm, CATICkeParmFactory, CATIParmPublisher, CATCSO, CATFrmEditor, CATISpecObject]
frameworks: [KnowledgeInterfaces, ApplicationFrame, InteractiveInterfaces, ObjectSpecsLegacy]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, parameter, editor, batch, formula]
---

# Parameter Editor (批量参数编辑)

用户选择多个 Feature，一次性修改它们的公共参数或公式。支持 Excel/CSV 批量导入。

## ⚠️ 重要修正

本文档早期版本存在多处虚构 API，已根据 `capabilities/parameter-system.md`、`capabilities/selection.md`、`knowledge/philosophy/updates.md` 的已核实结论修正：

| 旧写法（虚构/错误） | 真实情况 |
|---------------|---------|
| `CATISelection::GetSelection()` | `CATISelection` 接口不存在。真实当前选择集是 `CATCSO`（Current Selection of Objects），通过 `CATFrmEditor::GetCSO()` 获取，用 `InitElementList()`/`NextElement()` 遍历 |
| `CATICkeParm_var spParm = spFeat;`（直接从 Feature QI 到参数接口） | `CATICkeParm` 是参数对象本身的接口，不是 Feature 的接口，Feature 不能直接 QI 成一个参数。要拿到参数需通过具体 Feature 接口的 Get 方法（不同 Feature 类型各异，如 `CATINewHole::GetDiameter(CATICkeParm_var&)`），或者 QI 到 `CATIParmPublisher` 后用 `GetAllChildren()` 遍历已发布的参数树 |
| `spParm->SetFormula(name, value)` | 方法虚构，`CATICkeParm` 没有 `SetFormula()` | 公式是一次性创建并求值的：`CATICkeParmFactory::CreateFormula(iRelationName, iComment, iFamily, iOutputParameter, iListOfParameters, iBody, iRoot, iRealnames)`，没有分步 set |
| `CATIModelEvents::Dispatch()` 触发 Update | 方法/用途均错误 | 真实的 Update 入口是 `CATISpecObject::Update()` |
| `GetListOfParameters()` | 虚构，工具索引零匹配 | 没有通用的按名列参数方法；用 `CATIParmPublisher::GetAllChildren()` 遍历已发布参数树来确认实际参数名 |

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

1. **获取选中对象**：`CATFrmEditor::GetCSO()` 拿到 `CATCSO*`，用 `InitElementList()`/`NextElement()` 遍历，逐个 QI 到 `CATISpecObject_var`
2. **过滤 Feature**：QI 失败（结果为 `NULL_var`）的元素跳过
3. **读取公共参数**：对每个 Feature QI 到 `CATIParmPublisher`，用 `GetAllChildren()` 遍历已发布参数树，按 `Name()` 收集参数名并集
4. **展示编辑对话框**：列表显示 参数名 → 当前值（`Show()` 取带单位的显示字符串）→ 新值
5. **批量赋值**：直接赋数值用 `CATICkeParm::Valuate()` 的字符串/数值重载；绑定公式用 `CATICkeParmFactory::CreateFormula()` 一次性创建并求值
6. **触发 Update**：`CATISpecObject::Update()`（不是 `CATIModelEvents::Dispatch()`）

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
HRESULT BatchEditParams(CATIPrtPart_var spPart,
                        CATListValCATBaseUnknown_var &selectedFeatures,
                        CATListValParamEditItem &edits) {
    CATICkeParmFactory_var spFactory = spPart;   // Factory 通常从 Part/Document QI 一次，循环内复用
    if (NULL_var == spFactory) return E_FAIL;

    for (int i = 1; i <= selectedFeatures.Size(); i++) {
        CATISpecObject_var spFeat = selectedFeatures[i];
        if (NULL_var == spFeat) continue;

        // 参数挂在 Feature 的已发布参数树上，不能直接从 Feature QI 到 CATICkeParm
        CATIParmPublisher_var spPublisher = spFeat;
        if (NULL_var == spPublisher) continue;

        CATListValCATBaseUnknown_var *pChildren = spPublisher->GetAllChildren();
        if (NULL == pChildren) continue;

        for (int j = 0; j < edits.Size(); j++) {
            CATICkeParm_var spParm = NULL_var;
            for (int k = 1; k <= pChildren->Size(); k++) {
                CATICkeParm_var spCandidate = (*pChildren)[k];
                if (spCandidate != NULL_var && spCandidate->Name() == edits[j].paramName) {
                    spParm = spCandidate;
                    break;
                }
            }
            if (NULL_var == spParm) continue;

            if (edits[j].isFormula) {
                // 公式是一次性创建 + 求值，没有分步 SetFormula()
                CATCkeListOfParm inputParams;   // 公式体中引用到的输入参数需先收集
                CATICkeRelation_var spFormula = spFactory->CreateFormula(
                    edits[j].paramName + "_Formula", "", "",
                    spParm, inputParams, edits[j].newValue, NULL_var, 1);
            } else {
                spParm->Valuate(edits[j].newValue);   // 字符串重载，支持带单位输入，如 "12.5mm"
            }
        }
        delete pChildren;

        spFeat->Update();   // 真实触发入口：CATISpecObject::Update()
    }
    return S_OK;
}
```

## 注意事项

- 公式引用可能跨 Feature/跨 Part，修改前检查引用完整性
- 参数名区分大小写；用 `CATIParmPublisher::GetAllChildren()` 遍历确认实际发布的参数名，没有通用的 `GetListOfParameters()` 方法
- 不是所有 Feature 都实现 `CATIParmPublisher`；部分参数需要通过具体 Feature 接口单独获取（如 `CATINewHole::GetDiameter(CATICkeParm_var&)`）
- 批量操作建议加入 Transaction（Undo/Redo 支持）
- CSV 导入时注意编码（`CATUnicodeString` 使用 UTF-8 输入）

## 相关 Failure Pattern

- `fp.undeclared_class` — 跨文档引用公式可能暴露接口缺失

## 相关 Playbook

- `pb.batch_update_save` — 参数修改后统一 Update + Save
