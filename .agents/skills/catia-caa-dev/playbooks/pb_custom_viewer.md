---
id: pb.custom_viewer
title: Custom 3D Viewer / 自定义查看器
category: playbook
domain: ui
keywords: [viewer, 3D, visualization, CATNavigation3DViewer, render, camera]
capabilities: [cap.visualization, cap.selection]
apis: [CATNavigation3DViewer, CAT3DViewpoint, CATVisManager, CATViewer]
frameworks: [Visualization, VisualizationBase, ApplicationFrame]
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
- 自定义渲染效果（线框、着色、透明）
- 支持点选和高亮

## 实现步骤

1. **创建 Viewer 容器** → `CATDlgDocument` 或 `CATDlgFrame`
2. **创建 Navigation Viewer** → `CATNavigation3DViewer`
3. **加载模型** → 从当前文档或外部文件
4. **渲染设置** → 线框/着色模式、背景色、灯光
5. **交互处理** → 点选回调、高亮处理

## 关键接口

| 接口 | 用途 |
|------|------|
| `CATNavigation3DViewer` | 3D 视图容器 |
| `CAT3DViewpoint` | 视角控制（旋转、平移、缩放） |
| `CATVisManager` | 可视化属性（颜色、材质、透明度） |
| `CATVisProperties` | 图形属性设置 |

## 注意事项

- Viewer 生命周期需手动管理
- 多 Viewer 共享同一个模型数据（不是复制）
- CATIA R19-R24 和 R25+ 的 Viewer API 有差异
- 大模型在 Viewer 中需注意帧率
