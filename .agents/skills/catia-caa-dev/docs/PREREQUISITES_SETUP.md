# CADE Prerequisites Setup Feature

## 新增功能

### 自动配置 Workspace Prerequisites

CADE 现在可以自动检测 CATIA 安装并配置 workspace prerequisites，替代手动在 CATIA 中操作 "Manage prerequisites" 对话框。

---

## 功能说明

### 替代的手动操作

**CATIA 手动操作流程：**
1. 打开 CATIA
2. Tools > Workspace Explorer
3. 右键点击 workspace
4. 选择 "Manage prerequisites"
5. 手动输入 CATIA 路径（如 `C:\Program Files\Dassault Systemes\B28`）
6. 点击 OK

**CADE 自动化：**
```bash
# 一行命令完成
cade setup
```

---

## 使用方法

### 1. 自动检测并配置（推荐）

```bash
cd your_workspace
cade setup
```

**输出示例：**
```
✅ Workspace prerequisites configured successfully

Configuration:
{
  "workspace": "D:\\your_workspace",
  "catia_root": "C:\\Program Files\\Dassault Systemes\\B28",
  "cnext_exe": "C:\\Program Files\\Dassault Systemes\\B28\\win_b64\\code\\bin\\CNEXT.exe",
  "copy_prereq": false
}

Configuration saved to: D:\your_workspace/.cade_workspace.json
```

### 2. 仅检测 CATIA（不配置）

```bash
cade setup --detect
```

### 3. 查看当前配置

```bash
cade setup --show
```

### 4. 指定 CATIA 路径

```bash
cade setup --catia-root "D:\CATIA\B29"
```

---

## 生成的文件

### `.cade_workspace.json`
Workspace 配置文件，包含：
- Workspace 路径
- CATIA 安装路径
- CNEXT.exe 路径
- Prerequisites 选项

### `setup_env.bat`
Windows 环境变量设置脚本，包含：
```bat
set "CATIA_ROOT=C:\Program Files\Dassault Systemes\B28"
set "CNEXT_EXE=..."
set "WORKSPACE=D:\your_workspace"
```

---

## MCP 工具支持

AI 可以通过 MCP 调用：

```python
# 检测 CATIA
setup_workspace_prerequisites(detect_only=True)

# 配置 workspace
setup_workspace_prerequisites(workspace="path/to/workspace")
```

---

## 集成到工作流程

### 新项目创建流程

```bash
# 1. 创建项目目录
mkdir FSAI_CAA
cd FSAI_CAA

# 2. 复制 CADE
cp -r /path/to/CADE/.agents .

# 3. 配置 prerequisites（新增！）
cade setup

# 4. 创建框架和模块
cade create framework FSCore
cade create module FSUtils --framework FSCore
```

---

## 支持的检测方式

1. **环境变量** - `CATIA_ROOT`
2. **注册表**（Windows）- `HKLM\SOFTWARE\Dassault Systemes\CATIA`
3. **常用路径** - 
   - `C:\Program Files\Dassault Systemes\B28/B29/B30`
   - `D:\CATIA\B28/B29`
   - `E:\CATIA\B28`

---

## CLI 命令

```bash
cade setup [workspace]           # 配置 workspace prerequisites
cade setup --detect              # 仅检测 CATIA 安装
cade setup --show                # 显示当前配置
cade setup --catia-root <path>   # 指定 CATIA 路径
```

---

## 架构集成

新增文件：
- `tools/setup_prerequisites.py` - Prerequisites 配置工具
- `tools/setup_prerequisites.bat` - Windows 批处理包装
- `skills/cade.py` - 添加 `cmd_setup()` 函数
- `skills/mcp_server.py` - 添加 `setup_workspace_prerequisites` MCP 工具

---

## 版本

- 引入版本：CADE v2.0.1
- 日期：2026-07-08
