# FrameworkBareName — Architecture

## 整体架构

```
FrameworkName.edu/
│
├── AT_Core.m/            ← 核心接口与服务
├── AT_Feature.m/         ← Feature 对象定义
├── AT_UI.m/              ← 工作台、命令、对话框
│
├── docs/                 ← 工程文档
├── examples/             ← 测试数据与示例
└── scripts/              ← 自动化脚本
```

## 模块依赖

```
AT_UI ──→ AT_Feature ──→ AT_Core
  │            │
  └────────────┴──→ System, ObjectModelerBase
```

## 接口清单

| 接口 | 模块 | 功能 |
|------|------|------|
| IXXXService | Core | XXX服务 |

## 命令清单

| 命令 | 模块 | 功能 |
|------|------|------|
| XXXCmd | UI | XXX命令 |

## 设计原则

- 离线单机功能，无网络依赖
- 所有数据本地处理
- 命名规则统一
