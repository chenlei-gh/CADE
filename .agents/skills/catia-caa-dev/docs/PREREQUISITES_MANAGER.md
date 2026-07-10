# CADE Prerequisites Manager

## 概述

CADE Prerequisites Manager 是一个完整的框架依赖管理系统，用于管理 CAA 框架之间的依赖关系（`AddPrereqComponent` 声明）。

---

## 🎯 功能特性

| 功能 | 说明 |
|------|------|
| **添加依赖** | 自动修改 `IdentityCard.h`，添加 `AddPrereqComponent` 声明 |
| **移除依赖** | 从 `IdentityCard.h` 中移除指定依赖 |
| **列出依赖** | 显示框架的所有依赖关系 |
| **验证依赖** | 检测循环依赖、缺失依赖 |
| **智能推荐** | 基于代码分析推荐需要的框架 |
| **一键初始化** | 为新框架添加默认依赖 |

---

## 🔧 使用方法

### 1. 添加依赖

```bash
# 添加 Public 依赖（默认）
cade prereq add FSAutomation.edu FSCore

# 添加 Private 依赖
cade prereq add FSAutomation.edu InternalUtils --visibility Private

# 添加 CATIA 标准框架
cade prereq add FSCore.edu System
cade prereq add FSCore.edu ObjectModelerBase
cade prereq add FSCore.edu Visualization
```

**效果：**
```cpp
// FSAutomation.edu/IdentityCard/IdentityCard.h
AddPrereqComponent("FSCore", Public);
AddPrereqComponent("System", Public);
```

---

### 2. 移除依赖

```bash
cade prereq remove FSAutomation.edu InternalUtils
```

---

### 3. 列出依赖

```bash
cade prereq list FSCore.edu
```

**输出：**
```
📋 Prerequisites for FSCore.edu:

  • System (Public)
  • ObjectModelerBase (Public)
  • Visualization (Public)

Total: 3
```

---

### 4. 验证依赖

```bash
# 验证当前 workspace 所有框架的依赖关系
cade prereq validate

# 验证指定 workspace
cade prereq validate /path/to/workspace
```

**输出示例（有问题）：**
```
🔍 Validation Results:

  ❌ Circular dependencies detected:
     FSCore -> FSAutomation -> FSCore

  ⚠️  Missing dependencies:
     FSProductData requires 'UnknownFramework' (not found)

Scanned 4 frameworks
```

**输出示例（无问题）：**
```
🔍 Validation Results:

  ✅ All prerequisites are valid

Scanned 4 frameworks
```

---

### 5. 智能推荐

基于模块代码分析，推荐需要的框架：

```bash
cade prereq suggest FSCore.edu/FSUtils.m
```

**输出：**
```
💡 Suggested Prerequisites:

  • ProductStructure
    Product/Assembly (CATIProduct)
      Used in: CreateProduct.cpp

  • MechanicalModeler
    Part modeling (CATBody, CATIPart)
      Used in: PartUtils.cpp
      Used in: BodyAnalyzer.cpp

  • ApplicationFrame
    UI framework (CATCommand, etc.)
      Used in: MyCommand.cpp
```

---

### 6. 一键初始化

为新创建的框架添加默认依赖：

```bash
cade prereq init FSCore.edu
```

**自动添加：**
- `System` (Public)
- `ObjectModelerBase` (Public)
- `Visualization` (Public)

---

## 📋 常用 CATIA 框架

### 基础框架

| 框架 | 用途 |
|------|------|
| `System` | 核心系统框架（必需） |
| `ObjectModelerBase` | 对象模型基础 (`CATISpecObject`) |
| `Visualization` | 可视化框架 |
| `Mathematics` | 数学工具 |

### UI 框架

| 框架 | 用途 |
|------|------|
| `ApplicationFrame` | 命令框架 (`CATCommand`, `CATCommandHeader`) |
| `Dialog` | 对话框 (`CATDlgDialog`) |
| `InteractiveInterfaces` | 交互选择 (`CATPathElement`, `CATISelect`) |

### 建模框架

| 框架 | 用途 |
|------|------|
| `MechanicalModeler` | 零件建模 (`CATBody`, `CATIPart`, `CATFace`) |
| `ProductStructure` | 产品/装配 (`CATIProduct`) |
| `CATPLMIntegration` | PLM 集成 |

### 图纸框架

| 框架 | 用途 |
|------|------|
| `DraftingInterfaces` | 工程图接口 |
| `CATAnnotationInterfaces` | 3D 标注 |

---

## 🤖 MCP 工具（AI 调用）

AI 可以通过 MCP 直接调用：

```python
# 添加依赖
prereq_add(framework="FSCore.edu", component="System", visibility="Public")

# 列出依赖
prereq_list(framework="FSCore.edu")

# 验证依赖
prereq_validate(workspace=".")

# 推荐依赖
prereq_suggest(module="FSCore.edu/FSUtils.m")
```

在 Zed/Claude/Cursor 中：
```
"为 FSAutomation 框架添加 FSCore 依赖"
"检查当前项目的循环依赖"
"推荐 FSUtils 模块需要的框架"
```

---

## 🎯 推荐工作流程

### 创建新框架时

```bash
# 1. 创建框架
cade create framework FSCore

# 2. 初始化默认依赖
cade prereq init FSCore.edu

# 3. 根据需要添加其他依赖
cade prereq add FSCore.edu ApplicationFrame  # 如果有 UI
```

### 添加模块功能时

```bash
# 1. 开发代码
# 2. 编译发现缺少依赖
# 3. 使用智能推荐
cade prereq suggest FSCore.edu/MyModule.m

# 4. 根据推荐添加依赖
cade prereq add FSCore.edu ProductStructure
```

### 重构项目时

```bash
# 1. 验证当前依赖
cade prereq validate

# 2. 发现并修复循环依赖
# 3. 重新验证
cade prereq validate
```

---

## ⚠️ 最佳实践

### ✅ 好的依赖设计

```
FSCore (基础)
  ├─ System
  ├─ ObjectModelerBase
  └─ Visualization

FSUtils (工具)
  ├─ FSCore
  └─ Mathematics

FSAutomation (业务)
  ├─ FSCore
  ├─ FSUtils
  └─ ApplicationFrame
```

**特点：**
- 清晰的层次结构
- 单向依赖
- 无循环

### ❌ 避免的问题

**循环依赖：**
```
FSCore → FSAutomation
FSAutomation → FSCore
❌ 编译失败！
```

**过度依赖：**
```
FSUtils
  ├─ System
  ├─ ObjectModelerBase
  ├─ Visualization
  ├─ ApplicationFrame
  ├─ Dialog
  ├─ ProductStructure
  ├─ MechanicalModeler
  └─ ... (20+ frameworks)
❌ 工具类不应该依赖这么多框架！
```

---

## 🔍 技术实现

### 依赖解析

自动解析 `IdentityCard.h` 中的 `AddPrereqComponent` 声明：

```cpp
// 自动识别
AddPrereqComponent("System", Public);
AddPrereqComponent("Visualization", Private);
AddPrereqComponent("FSCore", Protected);
```

### 循环检测算法

使用 DFS（深度优先搜索）检测循环依赖：

```python
def detect_cycle(node, visited, rec_stack):
    visited.add(node)
    rec_stack.add(node)
    
    for neighbor in dependencies[node]:
        if neighbor not in visited:
            if detect_cycle(neighbor, visited, rec_stack):
                return True  # Found cycle
        elif neighbor in rec_stack:
            return True  # Back edge = cycle
    
    rec_stack.remove(node)
    return False
```

### API → Framework 映射

30+ 常用 API 映射：

| API | Framework |
|-----|-----------|
| `CATIProduct` | ProductStructure |
| `CATIPart` | MechanicalModeler |
| `CATBody` | MechanicalModeler |
| `CATCommand` | ApplicationFrame |
| `CATDialog` | Dialog |
| ... | ... |

---

## 📚 参考

- [CAA Framework Dependencies](./references/CAA_REFERENCE.md)
- [Workspace Environment Setup](./PREREQUISITES_SETUP.md)

---

**版本**: 2.0.1  
**更新日期**: 2026-07-08
