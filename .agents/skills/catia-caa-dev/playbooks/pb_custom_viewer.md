---
id: pb.custom_viewer
title: Custom 3D Viewer / 自定义查看器
category: playbook
domain: ui
keywords: [viewer, 3D, visualization, CATNavigation3DViewer, CAT3DViewer, CATViewer, render, camera, viewpoint]
capabilities: [cap.visualization, cap.selection]
apis: [CATNavigation3DViewer, CAT3DViewpoint, CATViewer, CATIVisProperties]
frameworks: [Visualization, VisualizationBase, Dialog]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, viewer, 3D, visualization]
---
# Custom 3D Viewer (自定义查看器)

在对话框中嵌入自定义 3D Viewer，实现独立视角和渲染。

## 目标

- 在 Dialog 中嵌入 3D 视图
- 独立于主窗口的视角控制
- 点选和高亮

## 类层次（已核实）

```
CATViewer
  └── CAT3DViewer
        └── CATNavigation3DViewer   ← 带导航工具条的开箱即用 3D 视图组件
```

`CATNavigation3DViewer` 构造时会自动创建自己的 `CATBasic3DViewpointEditor` 并关联到主视角，自带 TurnAround/Walk/Fly 导航工具条和 Reframe/上一视角/下一视角按钮，不需要自己再拼一个导航 UI。

## 实现步骤

1. **创建 Dialog 容器** → `CATDlgFrame`（内嵌于父 Dialog）
2. **创建 Navigation Viewer** → `new CATNavigation3DViewer(pFatherDialog, "MyViewer", NULL, width, height, iViewerStyle)`
3. **添加图形表示（Rep）** → `CATViewer::AddRep(CAT2DRep*)`/`AddRepFurtive()`，或通过 `SetMainViewpoint()` 关联一个已建好的 `CAT3DViewpoint`
4. **渲染/背景设置** → `CATViewer::SetBackgroundColor()`、`SetViewMode(int,int)`（线框/着色模式码，具体常量见 `Visualization/PublicInterfaces` 头文件，不是一个独立枚举类型）
5. **点选** → `CATViewer::Pick(CATPickingStyle, ...)` 阻塞式拾取，返回 `CATPickPathList`
6. **应用图形属性** → 通过 `CATIVisProperties`/`CATVisPropertiesValues`（见 `capabilities/visualization.md`），**不是**一个叫 `CATVisProperties` 的独立类

## 关键代码骨架

```cpp
CATDlgFrame *pFrame = new CATDlgFrame(pFatherDialog, "MyViewerFrame");

CATNavigation3DViewer *pViewer = new CATNavigation3DViewer(
    pFrame, "MyViewer", NULL, 800, 500, NULL);

// 自定义背景色
pViewer->SetBackgroundColor(0.9f, 0.9f, 0.9f, 0);

// 关联一个已有的视角（或使用 pViewer 自带的主视角）
CAT3DViewpoint *pViewpoint = new CAT3DViewpoint();
pViewer->SetMainViewpoint(pViewpoint);

// 点选（阻塞，等待用户点击）
CATPickPathList pickResult;
CATPathElement pickedPath;
float x, y;
pViewer->Pick(CATPicking, 0, 0, 0, 0, pickResult, &pickedPath, NULL, 1, 0);
```

## 图形属性（着色/透明度/高亮）

`CATNavigation3DViewer`/`CATViewer` 本身不提供 `SetColor`/`SetOpacity`/`SetMaterial` 这类方法；对象的颜色、透明度、显示/隐藏状态是通过 `CATIVisProperties::SetPropertiesAtt(CATVisPropertiesValues&, CATVisPropertyType, CATVisGeomType)` 施加到具体的 spec object 上，与 Viewer 无关。完整用法见 `capabilities/visualization.md`。

## 注意事项

- `CATVisProperties`（作为一个独立的类）**不存在**；颜色/透明度走 `CATIVisProperties` + `CATVisPropertiesValues`
- `CATVisManager` 是底层可视化调度器（`AttachTo`/`DetachFrom`/`Commit`/`BuildRep`），面向 rep-path/viewpoint 连接管理，日常业务代码一般不直接调用，Viewer 层已经封装好了这些细节
- Viewer 生命周期需手动管理（`delete` 或随父 Dialog 销毁）
- 多个 Viewer 可以共享同一份模型数据（通过 `AddRep` 挂载相同的 Rep），不需要复制模型
- `SetViewMode(int,int)` 的模式码不是一个命名枚举，使用前确认具体版本头文件中的常量定义，不要凭直觉猜测线框/着色对应的数值
- 具体图形属性/选择相关的真实 API 详见 `capabilities/visualization.md`（颜色/透明度/显示隐藏）与 `capabilities/selection.md`（CATCSO 当前选择集）
