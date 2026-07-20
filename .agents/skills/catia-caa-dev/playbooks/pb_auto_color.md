---
id: pb.auto_color
title: Auto Color Parts / 零件自动着色
category: playbook
domain: product
keywords: [color, auto, random, visualization, graphic properties, material, shade]
capabilities: [cap.visualization, cap.geometry_query, cap.assembly_tree]
apis: [Selection, VisPropertySet, CATIProduct]
frameworks: [InfInterfaces, ProductStructure]
difficulty: beginner
effort: small
release: [R19, R28]
tags: [playbook, color, automation]
---

# Auto Color Parts (零件自动着色)

遍历装配体中的所有子零件，通过 Automation 层的 `Selection.VisProperties` 为每个零件分配随机/固定颜色。

## 目标

一键给装配中所有子零件赋予不同颜色，便于区分和检查。

## 前置条件

- 已加载 CATPart 或 CATProduct 文档
- 可选：颜色映射表（零件名→颜色）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历装配树获取所有子零件 |
| `cap.geometry_query` | 获取每个零件的 Body/几何体 |
| `cap.visualization` | 修改图形属性（颜色/透明度） |

> ⚠️ **重大修正（改变了本 Playbook 的整体方案）**：经查证 CAADoc 全部字典文件
> （`*.dico`），全库范围内声明实现 `CATIVisProperties` 接口的组件只有 3 个——
> `CAAPstINFPoint`/`CAAPstINFLine`/`CAAPstINFWire`（见 `CAAProductStructure.edu.dico`）
> 和 `CAAMmrMultiMeasure`（见 `CAAMechanicalModeler.edu.dico`），**均为 Feature/几何元素
> 级组件**。`CATIProduct` 接口自身的方法列表中没有任何 Vis/Color/Graphic 相关方法，也没有
> 找到任何官方样例或字典条目证明装配树节点（`CATIProduct`）可以直接
> `QueryInterface(IID_CATIVisProperties, ...)`。
>
> 原方案中 `CATIVisProperties_var spVis = (*pChildren)[i];`（把子 Product 隐式转换为
> `CATIVisProperties`）**不成立**，已被替换为下方的正确方案。
>
> 真正支持"任意选中对象（包括装配节点/Product 实例）"着色的官方机制是 **Automation
> 层的 `Selection` 对象**：先把目标对象加入 `Selection`，再通过
> `Selection.VisProperties` 拿到 `VisPropertySet` 自动化对象，调用其
> `SetRealColor(iRed, iGreen, iBlue, iInheritance)` 方法设置颜色（定义在
> `InfInterfaces` 框架 `interface_VisPropertySet_21585.htm`，`Selection` 对象定义在
> `interface_Selection_15704.htm`）。这是 CATIA VBA/Automation 中给任意选中元素
> （包含 Product 装配节点）设置图形属性的标准做法，与 `CATIVisProperties`（C++层，仅供
> Feature 组件自身实现）是两条不同的技术路线，不要混用。

## 实现步骤（VBA / Automation，推荐方案）

1. **获取根 Product**：`Set spRoot = CATIA.ActiveDocument.Product`
2. **遍历子零件**：`Product.Products`（`Products` 集合对象，`Count`/`Item(i)`）
3. **将每个子零件加入 Selection**：`CATIA.ActiveDocument.Selection.Add oChildProduct`
4. **通过 `Selection.VisProperties` 拿到 `VisPropertySet`**，调用
   `SetRealColor(r, g, b, iInheritance)` 设置真实颜色（`iInheritance` 传 0 表示该
   节点自己的颜色不继承自父节点）
5. **清空 Selection**，处理下一个零件：`Selection.Clear`

## 完整代码（VBA）

```vb
Sub AutoColorParts(oRootProduct As Product)
    Dim oSel As Selection
    Set oSel = CATIA.ActiveDocument.Selection

    Dim oChildren As Products
    Set oChildren = oRootProduct.Products

    Dim i As Integer
    Randomize
    For i = 1 To oChildren.Count
        Dim oChild As Product
        Set oChild = oChildren.Item(i)

        oSel.Clear
        oSel.Add oChild

        Dim r As Long, g As Long, b As Long
        r = Int(Rnd * 256)
        g = Int(Rnd * 256)
        b = Int(Rnd * 256)

        Dim oVisProps As VisPropertySet
        Set oVisProps = oSel.VisProperties
        oVisProps.SetRealColor r, g, b, 0
    Next i

    oSel.Clear
End Sub
```

## C++ 层的替代方案（仅适用于自定义 Feature，不适用于 Product 节点）

如果需要给**自定义 Feature/几何元素**（而非装配节点）着色，才应该在 C++ 层用
`CATIVisProperties`，前提是该 Feature 组件已通过数据扩展（Data Extension）+ 字典条目
声明实现了该接口（参考 `cap.visualization` 中记录的
`CATIVisPropertiesAbstract::SetPropertiesAtt` 用法与 `CAAGviApplyProperties.cpp` 官方样例）。
装配树遍历得到的 `CATIProduct` 对象不适用此路线。

## 注意事项

- `Selection.VisProperties` 是每次选择集内容变化后才生效的只读属性，务必先 `Add` 再取
  `VisProperties`，且处理完一个零件后要 `Clear` 选择集，避免颜色被应用到多个已选对象上
- `SetRealColor` 修改的是"Real"（真实）图形属性；还存在"Visible"（继承后显示）图形属性，
  两者的区别与继承机制见 `VisPropertySet` 接口说明
- 大装配建议用进度条
- 可预先定义调色板（按零件类型/材质匹配颜色）
- 装配体中 Reference/Instance 共用几何体，如果对 Reference 上色会影响所有实例；建议明确
  区分对 Instance 还是 Reference 着色

## 相关 Playbook

- `pb.export_bom` — 导出 BOM 可同时记录颜色信息
