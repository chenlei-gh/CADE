# Build Time vs Run Time 环境使用指南

## 📋 目录

1. [概述](#概述)
2. [Build Time 环境](#build-time-环境)
3. [Run Time 环境](#run-time-环境)
4. [决策树：何时使用哪个环境](#决策树何时使用哪个环境)
5. [完整工作流示例](#完整工作流示例)
6. [常见场景和最佳实践](#常见场景和最佳实践)
7. [故障排除](#故障排除)

---

## 概述

CATIA CAA 开发中有两个独立的环境，每个环境有不同的用途和初始化方式：

| 环境 | 用途 | 初始化方式 | 主要工具 | Skill 调用 |
|------|------|-----------|---------|-----------|
| **Build Time** | 编译 CAA 代码 | `mkinit.bat` | `mkmkM.exe`, `cl.exe`, `link.exe` | `build.py`, `clean.py` |
| **Run Time** | 运行 CATIA | `mkrun.bat` | `CNEXT.exe`, Runtime View | `run.py`, `runtime_view.py` |

**核心原则：**
- ✅ 编译时使用 Build Time
- ✅ 运行时使用 Run Time
- ❌ 不要混用

---

## Build Time 环境

### 🎯 目的

Build Time 环境用于 **编译 CAA 代码**，它需要：

1. Visual Studio 编译器 (`cl.exe`)
2. Windows SDK 链接器 (`link.exe`)
3. CATIA 构建工具 (`mkmkM.exe`)
4. 相关环境变量 (PATH, INCLUDE, LIB)

### 🔧 初始化方式

```batch
# Build Time Prompt 调用链 (B28)
cmd.exe
  → mkinit.bat                  # 检测 VS2012, Windows Kit
  → 设置 PATH, INCLUDE, LIB
  → 现在可以运行 mkmkM.exe
```

**在 Python 中调用：**

```python
from env import CAAEnvironment

caa_env = CAAEnvironment()
cmd, cmd_display = caa_env.build_time_command(workspace_path, "-u")

# cmd = ["cmd", "/c", "call mkinit.bat && cd workspace && mkmkM -u"]
subprocess.run(cmd, ...)
```

### 📂 使用 Build Time 的 Skills

#### 1. **build.py** (主要使用者)

**使用场景：**
- 编译整个 workspace
- 编译单个 framework
- 编译单个 module

**调用方式：**
```bash
python skills/build.py D:\test\TestFramework.edu
```

**内部实现：**
```python
# build.py 内部流程
caa_env = CAAEnvironment()
cmd, cmd_display = caa_env.build_time_command(workspace_path, options)
# cmd = ["cmd", "/c", "call mkinit.bat && mkmkM -u"]

subprocess.run(cmd, timeout=600)
```

**关键点：**
- ✅ 每次编译都必须初始化 Build Time 环境
- ✅ 使用 `mkinit.bat` 而不是 `tck_init.bat`
- ✅ 必须在 cmd.exe 中调用（环境变量只在该 shell 有效）

---

#### 2. **clean.py** (次要使用者)

**使用场景：**
- 清理 Objects 目录

**调用方式：**
```bash
python skills/clean.py D:\test\TestFramework.edu
```

**内部实现：**
```python
# clean.py 可以选择两种方式
# 方式 1: 直接删除 Objects 目录 (不需要 Build Time)
shutil.rmtree(objects_dir)

# 方式 2: 使用 mkmk -u (需要 Build Time)
caa_env = CAAEnvironment()
cmd, _ = caa_env.build_time_command(workspace_path, "-u")
subprocess.run(cmd)
```

**推荐：**
- 简单清理：直接删除 Objects 目录（不需要 Build Time）
- 完整清理：使用 `mkmk -u`（需要 Build Time）

---

### ⚠️ Build Time 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `'mkmkM' is not recognized` | PATH 未设置 | 必须通过 `mkinit.bat` 初始化 |
| `0xC0000142` (DLL_INIT_FAILED) | 直接运行 mkmkM.exe | 必须在 cmd.exe 中通过 `mkinit.bat` 初始化 |
| `Cannot find Visual Studio` | mkinit.bat 未检测到 VS | 检查 VS2012 是否安装 |
| `error C2143: missing ';'` | 代码语法错误 | 修复代码后重新编译 |

---

## Run Time 环境

### 🎯 目的

Run Time 环境用于 **运行 CATIA**，它需要：

1. CATIA 运行时库 (DLLs)
2. Runtime View (包含你的 CAA 组件)
3. 许可证配置
4. 相关环境变量 (CATInstallPath, CATDLLPath)

### 🔧 初始化方式

```batch
# 带工作区的启动链 (B28)
run.py <workspace>
  → tck_init → tck_profile → mkinit
  → Runtime View
  → mkrun                      # 设置 CATDLLPath / CATDictionaryPath / CATMsgCatalogPath
  → CNEXT
```

不要自己 `Popen` 安装目录里的 `CNEXT.exe` 或 `CATSTART.exe`。那不会挂 Runtime View。

**在 Python 中调用：**

```python
from run import start_catia_runtime

result = start_catia_runtime(workspace_path="D:/workspace")
# 看 runtime_view_mounted，不要只看 status == "started"
```

### 📂 使用 Run Time 的 Skills

#### 1. **run.py** (主要使用者)

**使用场景：**
- 启动 CATIA 测试 CAA 组件
- 检查 CATIA 是否正在运行
- 等待 CATIA 退出

**调用方式：**
```bash
python skills/run.py D:\workspace            # 启动并挂载该工作区 Runtime View
python skills/run.py D:\workspace --wait     # 挂载后启动并等待退出
python skills/run.py --check                 # 只检查是否运行，不启动
python skills/run.py --stop                  # 停止，不启动
```

`workspace` 是位置参数，不是 `--workspace`。不带路径会回退到裸 `CATSTART.exe`：CATIA 起来，自定义 CAA DLL 不加载，`status` 仍可能是 `started`。

**内部实现：**
```python
# 带 workspace：mkrun，挂 CATDLLPath / CATDictionaryPath / CATMsgCatalogPath
result = start_catia_runtime(workspace_path="D:/workspace")
assert result["runtime_view_mounted"] is True
```

**关键点：**
- ✅ 验证自定义工具时必须带 workspace
- ✅ 看 `runtime_view_mounted`，不要只看 `status`
- ✅ 禁止直接运行安装目录里的 `CATSTART.exe` / `CNEXT.exe`

---

#### 2. **runtime_view.py** (辅助工具)

**使用场景：**
- 创建 Runtime View
- 检查 Runtime View 是否存在

**调用方式：**
```bash
python skills/runtime_view.py --create    # 创建 Runtime View
python skills/runtime_view.py             # 检查 Runtime View
```

**内部实现：**
```python
# runtime_view.py 使用 Build Time 工具创建 Runtime View
# 注意：mkCreateRuntimeView 是 Build Time 工具
caa_env = CAAEnvironment()
cmd, _ = caa_env.build_time_command(workspace_path, "")
# 修改命令为 mkCreateRuntimeView

subprocess.run(cmd)
```

**特殊说明：**
- `mkCreateRuntimeView` 虽然创建的是 Runtime View，但它本身是 Build Time 工具
- 所以 `runtime_view.py` 需要 Build Time 环境来创建 Runtime View

---

### ⚠️ Run Time 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `CNEXT.exe not found` | CATIA 路径错误 | 检查 `caa_env_config.txt` |
| `No licenses available` | 许可证未配置 | 配置 CATIA 许可证服务器 |
| `Runtime View not found` | 未创建 Runtime View | `python skills/runtime_view.py <workspace> --create` |
| `CATIA is already running` | CATIA 已在运行 | 使用 `--check` 检查状态 |

---

## 决策树：何时使用哪个环境

```mermaid
graph TD
    Start[用户请求] --> Question{任务类型?}
    
    Question -->|编译代码| BuildTime[使用 Build Time 环境]
    Question -->|运行CATIA| RunTime[使用 Run Time 环境]
    Question -->|清理构建| Clean[使用 Build Time 或直接删除]
    Question -->|创建Runtime View| BuildTime2[使用 Build Time 工具]
    Question -->|检查工作区| None[不需要特殊环境]
    
    BuildTime --> BuildPy[python skills/build.py]
    RunTime --> RunPy["python skills/run.py workspace"]
    Clean --> CleanPy[python skills/clean.py]
    BuildTime2 --> RuntimeViewPy[python skills/runtime_view.py]
    None --> WorkspacePy[python skills/workspace.py]
    
    BuildPy --> Success{编译成功?}
    Success -->|是| RunPy
    Success -->|否| Fix[修复错误]
    Fix --> BuildPy
```

### 快速参考表

| 用户请求 | 使用的 Skill | 需要的环境 | 命令 |
|---------|------------|-----------|------|
| "编译我的代码" | `build.py` | Build Time | `python skills/build.py` |
| "清理构建" | `clean.py` | Build Time (可选) | `python skills/clean.py` |
| "运行CATIA" | `run.py` | Run Time | `python skills/run.py <workspace>` |
| "创建Runtime View" | `runtime_view.py` | Build Time | `python skills/runtime_view.py --create` |
| "检查工作区" | `workspace.py` | 无 | `python skills/workspace.py` |
| "检查CATIA是否运行" | `run.py` | Run Time | `python skills/run.py --check` |

---

## 完整工作流示例

### 示例 1：标准开发周期（修改代码 → 编译 → 测试）

```mermaid
sequenceDiagram
    participant User
    participant AI
    participant BuildTime as Build Time Env
    participant RunTime as Run Time Env
    participant CATIA

    User->>AI: 修改 MyComponent.cpp
    AI->>AI: 编辑代码
    AI->>BuildTime: python skills/build.py
    BuildTime->>BuildTime: mkinit.bat 初始化
    BuildTime->>BuildTime: mkmkM -u 编译
    BuildTime-->>AI: {"status":"success"}
    AI->>RunTime: python skills/run.py workspace
    RunTime->>RunTime: mkrun 挂载 Runtime View
    RunTime->>CATIA: 启动 CNEXT
    CATIA-->>AI: runtime_view_mounted=true
    AI-->>User: 编译成功，CATIA已启动
```

**代码示例：**

```python
# AI 的完整流程
# Step 1: 修改代码
edit_file("TestFramework.edu/TestModule.m/src/MyComponent.cpp", changes)

# Step 2: 编译 (使用 Build Time)
result = subprocess.run(["python", "skills/build.py", "TestFramework.edu"], 
                       capture_output=True, text=True)
build_result = json.loads(result.stdout)

if build_result["status"] == "success":
    # Step 3: 运行。workspace 是位置参数，不带则自定义 DLL 不加载。
    result = subprocess.run(["python", "skills/run.py", "D:/workspace"],
                           capture_output=True, text=True)
    run_result = json.loads(result.stdout)
    print(f"mounted: {run_result.get('runtime_view_mounted')}")
else:
    # Step 4: 修复错误
    for error in build_result["errors"]:
        print(f"Error in {error['file']} line {error['line']}: {error['message']}")
```

---

### 示例 2：首次设置工作区

```mermaid
graph LR
    A[用户: 设置新工作区] --> B[检查环境配置]
    B --> C{config存在?}
    C -->|否| D[运行 initialize_caa_env.bat]
    C -->|是| E[检查工作区结构]
    D --> E
    E --> F[python skills/workspace.py]
    F --> G{工作区有效?}
    G -->|否| H[报告错误]
    G -->|是| I[创建 Runtime View]
    I --> J[python skills/runtime_view.py --create]
    J --> K[Build Time: mkCreateRuntimeView]
    K --> L[首次编译]
    L --> M[python skills/build.py]
    M --> N[Build Time: mkmkM]
    N --> O{编译成功?}
    O -->|是| P[测试运行]
    O -->|否| Q[修复错误]
    P --> R["python skills/run.py workspace"]
    R --> S[Run Time: CNEXT]
```

**代码示例：**

```python
# Step 1: 检查环境
if not Path("caa_env_config.txt").exists():
    subprocess.run(["initialize_caa_env.bat"])

# Step 2: 检查工作区
result = subprocess.run(["python", "skills/workspace.py", workspace_path])
workspace_info = json.loads(result.stdout)

if workspace_info["status"] != "ok":
    print("Workspace errors:", workspace_info["errors"])
    exit(1)

# Step 3: 创建 Runtime View (使用 Build Time 工具)
result = subprocess.run(["python", "skills/runtime_view.py", workspace_path, "--create"])
runtime_info = json.loads(result.stdout)

if runtime_info["status"] == "success":
    # Step 4: 编译 (使用 Build Time)
    result = subprocess.run(["python", "skills/build.py", workspace_path])
    build_info = json.loads(result.stdout)
    
    if build_info["status"] == "success":
        # Step 5: 运行。必须把 workspace_path 作为位置参数传进去。
        subprocess.run(["python", "skills/run.py", workspace_path])
```

---

### 示例 3：快速迭代（多次编译）

```python
# 快速迭代场景：修复多个编译错误
workspace = "TestFramework.edu"
max_attempts = 5

for attempt in range(max_attempts):
    print(f"\n=== Attempt {attempt + 1} ===")
    
    # 编译 (Build Time)
    result = subprocess.run(
        ["python", "skills/build.py", workspace],
        capture_output=True, text=True
    )
    build_result = json.loads(result.stdout)
    
    if build_result["status"] == "success":
        print("✓ Build successful!")
        
        # 运行测试。不带 workspace 是裸机启动。
        subprocess.run(["python", "skills/run.py", workspace])
        break
    else:
        print(f"✗ Build failed with {build_result['error_count']} errors")
        
        # 修复第一个错误
        first_error = build_result["errors"][0]
        print(f"Fixing: {first_error['file']} line {first_error['line']}")
        
        # AI 修复代码...
        fix_error(first_error)
        
        # 继续下一次尝试
        continue
else:
    print("Failed after maximum attempts")
```

---

## 常见场景和最佳实践

### ✅ 正确的做法

#### 场景 1：编译前检查工作区

```python
# 正确：先检查，再编译
subprocess.run(["python", "skills/workspace.py", workspace])  # 无需特殊环境
subprocess.run(["python", "skills/build.py", workspace])      # Build Time
```

#### 场景 2：编译成功后运行

```python
# 正确：分离 Build Time 和 Run Time
result = subprocess.run(["python", "skills/build.py"], capture_output=True)
build_info = json.loads(result.stdout)

if build_info["status"] == "success":
    subprocess.run(["python", "skills/run.py", "D:/workspace"])  # 位置参数，走 mkrun
```

#### 场景 3：检查 CATIA 是否运行再启动

```python
# 正确：避免多实例
result = subprocess.run(["python", "skills/run.py", "--check"], capture_output=True)
check_result = json.loads(result.stdout)

if check_result["status"] == "not_running":
    subprocess.run(["python", "skills/run.py", "D:/workspace"])
else:
    print(f"CATIA already running (PID: {check_result['processes'][0]['pid']})")
```

---

### ❌ 错误的做法

#### 错误 1：尝试在同一个进程中混用环境

```python
# ❌ 错误：环境变量会冲突
env = {}
env.update(build_time_env)  # Build Time 变量
env.update(run_time_env)    # Run Time 变量 (会覆盖)

subprocess.run(["mkmkM"], env=env)  # 可能失败
```

**原因：** Build Time 和 Run Time 的 PATH、DLL 路径可能冲突。

**正确做法：** 每个任务使用独立的环境。

---

#### 错误 2：直接运行 mkmkM.exe 不初始化环境

```python
# ❌ 错误：会报 0xC0000142 错误
subprocess.run(["C:\\...\\mkmkM.exe", "-u"])
```

**原因：** mkmkM.exe 依赖 Build Time 环境变量。

**正确做法：** 使用 `env.build_time_command()` 通过 mkinit.bat 初始化。

---

#### 错误 3：假设编译成功就运行

```python
# ❌ 错误：没有检查 Runtime View
subprocess.run(["python", "skills/build.py"])
subprocess.run(["python", "skills/run.py"])  # 裸机：自定义 DLL 不加载
```

**原因：** 即使编译成功，没有 Runtime View 就无法运行。

**正确做法：** 先检查/创建 Runtime View。

```python
# ✅ 正确
subprocess.run(["python", "skills/runtime_view.py", "D:/workspace", "--create"])
subprocess.run(["python", "skills/build.py", "D:/workspace"])
subprocess.run(["python", "skills/run.py", "D:/workspace"])
```

---

## 故障排除

### 问题 1：Build Time 初始化失败

**症状：**
```
ERROR: mkinit.bat not found
```

**检查：**
```python
python skills/env.py
# 查看输出中的 mkinit_bat 路径
```

**解决方案：**
1. 检查 `caa_env_config.txt` 中的 `CATIA_INSTALL` 路径
2. 确认 `<CATIA>\win_b64\code\command\mkinit.bat` 存在
3. 重新运行 `initialize_caa_env.bat`

---

### 问题 2：编译时找不到 Visual Studio

**症状：**
```
Cannot find Visual Studio 2012
```

**原因：** `mkinit.bat` 无法检测到 VS2012。

**解决方案：**
1. 确认 VS2012 已安装
2. 检查注册表键值（mkinit.bat 通过注册表查找 VS）
3. 手动设置环境变量后再编译

---

### 问题 3：Runtime 启动失败

**症状：**
```json
{
  "status": "crashed",
  "exit_code": -1073741819
}
```

**原因：**
- 缺少 Runtime View
- 缺少许可证
- DLL 依赖问题

**解决方案：**

```python
# Step 1: 检查 Runtime View
subprocess.run(["python", "skills/runtime_view.py", "D:/workspace"])

# Step 2: 创建 Runtime View (如果不存在)
subprocess.run(["python", "skills/runtime_view.py", "D:/workspace", "--create"])

# Step 3: 重新编译
subprocess.run(["python", "skills/build.py", "D:/workspace"])

# Step 4: 再次运行。不带 workspace 仍是裸机。
subprocess.run(["python", "skills/run.py", "D:/workspace"])
```

---

### 问题 4：CATIA 多实例冲突

**症状：**
```json
{
  "status": "already_running",
  "pid": 12345
}
```

**解决方案：**

```python
# 方案 1: 检查后再启动
result = subprocess.run(["python", "skills/run.py", "--check"], capture_output=True)
check = json.loads(result.stdout)

if check["status"] == "running":
    print("关闭现有 CATIA 实例后再启动")
else:
    subprocess.run(["python", "skills/run.py", "D:/workspace"])

# 方案 2: 强制使用现有实例
if check["status"] == "running":
    print(f"使用现有 CATIA 实例 (PID: {check['processes'][0]['pid']})")
```

---

## 总结

### 核心要点

1. **Build Time = 编译工具**
   - 使用 `mkinit.bat` 初始化
   - 运行 `mkmkM.exe` 编译
   - 依赖 VS2012 编译器
   - 由 `build.py` 和 `runtime_view.py` 使用

2. **Run Time = 运行环境**
   - 带 workspace 走 `mkrun`，挂载 `CATDLLPath` / `CATDictionaryPath` / `CATMsgCatalogPath`
   - 不要直接运行 `CATSTART.exe` / `CNEXT.exe`
   - 由 `run.py <workspace>` 使用；看 `runtime_view_mounted`

3. **环境隔离**
   - 每个任务使用独立环境
   - 不要在同一个进程中混用
   - 通过 `env.py` 统一管理

4. **标准流程**
   ```
   workspace.py (检查) 
     → runtime_view.py --create (创建Runtime View, Build Time)
     → build.py (编译, Build Time) 
     → run.py <workspace> (mkrun 挂载后运行)
   ```

---

**版本：** 1.0.0  
**最后更新：** 2026-07-06  
**适用于：** CATIA V5 R28 (B28)
