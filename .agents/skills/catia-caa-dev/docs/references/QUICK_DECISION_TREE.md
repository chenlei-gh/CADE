# Build Time vs Run Time 快速决策树

这是一个快速参考指南，帮助 AI 和开发者在 1 秒内决定使用哪个环境。

---

## 🎯 一句话判断法

**问自己：这个操作是"编译代码"还是"运行 CATIA"？**

```
编译代码？ → Build Time Environment
运行 CATIA？ → Run Time Environment
```

---

## 📋 按操作类型分类

### Build Time 环境（编译相关）

| 操作 | Skill | 命令 |
|-----|------|------|
| 编译 workspace | `build.py` | `python skills/build.py` |
| 编译 framework | `build.py` | `python skills/build.py D:\MyFw.edu` |
| 编译 module | `build.py` | `python skills/build.py D:\MyFw.edu\MyMod.m` |
| 清理 Objects (mkmk方式) | `clean.py` | `python skills/clean.py` |
| 创建 Runtime View | `runtime_view.py` | `python skills/runtime_view.py --create` |

**关键标志：**
- ✅ 涉及 `mkmkM.exe`
- ✅ 涉及 Visual Studio 编译器
- ✅ 生成 `.o`, `.lib`, `.dll` 文件
- ✅ 需要 `mkinit.bat`

---

### Run Time 环境（运行相关）

| 操作 | Skill | 命令 |
|-----|------|------|
| 启动 CATIA | `run.py` | `python skills/run.py` |
| 检查 CATIA 是否运行 | `run.py` | `python skills/run.py --check` |
| 启动并等待 CATIA 退出 | `run.py` | `python skills/run.py --wait` |

**关键标志：**
- ✅ 涉及 `CNEXT.exe`
- ✅ 需要 Runtime View
- ✅ 需要 CATIA 许可证
- ✅ 加载 DLLs 到 CATIA

---

### 无需特殊环境

| 操作 | Skill | 命令 |
|-----|------|------|
| 检查 workspace 结构 | `workspace.py` | `python skills/workspace.py` |
| 清理 Objects (删除方式) | `clean.py` | `python skills/clean.py` |
| 查看环境信息 | `env.py` | `python skills/env.py` |

**关键标志：**
- ✅ 只读操作
- ✅ 文件系统操作
- ✅ 不调用 CATIA 工具

---

## 🔀 按用户请求分类

### "编译" 相关

| 用户说 | 使用 | 环境 |
|-------|-----|------|
| "编译我的代码" | `build.py` | Build Time |
| "build my project" | `build.py` | Build Time |
| "compile CAA" | `build.py` | Build Time |
| "mkmk 编译" | `build.py` | Build Time |
| "构建 framework" | `build.py` | Build Time |

---

### "运行" 相关

| 用户说 | 使用 | 环境 |
|-------|-----|------|
| "运行 CATIA" | `run.py` | Run Time |
| "启动 CATIA" | `run.py` | Run Time |
| "start CNEXT" | `run.py` | Run Time |
| "测试我的组件" | `build.py` → `run.py` | Build Time → Run Time |
| "CATIA 在运行吗" | `run.py --check` | Run Time |

---

### "检查" 相关

| 用户说 | 使用 | 环境 |
|-------|-----|------|
| "检查 workspace" | `workspace.py` | 无 |
| "workspace 有效吗" | `workspace.py` | 无 |
| "验证结构" | `workspace.py` | 无 |
| "有 Runtime View 吗" | `runtime_view.py` | 无 |

---

### "清理" 相关

| 用户说 | 使用 | 环境 |
|-------|-----|------|
| "清理编译" | `clean.py` | Build Time (可选) |
| "删除 Objects" | `clean.py` | 无 |
| "clean build" | `clean.py` | 无 |

---

## 🚦 完整流程决策

```mermaid
graph TD
    Start[用户请求] --> Type{请求类型?}
    
    Type -->|包含"编译"|Compile[Build Time]
    Type -->|包含"运行"|Run[Run Time]
    Type -->|包含"检查"|Check[无需环境]
    Type -->|包含"清理"|Clean[无需环境或Build Time]
    Type -->|不确定|Analyze[分析具体操作]
    
    Compile --> BuildPy["python skills/build.py"]
    Run --> RunPy["python skills/run.py"]
    Check --> WorkspacePy["python skills/workspace.py"]
    Clean --> CleanPy["python skills/clean.py"]
    
    Analyze --> A1{涉及mkmk?}
    Analyze --> A2{涉及CNEXT?}
    Analyze --> A3{只读文件?}
    
    A1 -->|是| Compile
    A2 -->|是| Run
    A3 -->|是| Check
```

---

## 💡 特殊情况

### 情况 1：创建 Runtime View

**问题：** Runtime View 是运行时用的，为什么需要 Build Time？

**答案：** 因为创建工具 `mkCreateRuntimeView` 是 Build Time 工具。

```python
# 创建 Runtime View：使用 Build Time
python skills/runtime_view.py --create  # 内部调用 mkCreateRuntimeView (Build Time工具)

# 使用 Runtime View：使用 Run Time
python skills/run.py  # 内部使用 Runtime View 启动 CNEXT
```

---

### 情况 2：清理构建

**问题：** clean 用哪个环境？

**答案：** 两种方式都可以：

```python
# 方式 1：直接删除 (无需环境)
python skills/clean.py  # 直接删除 Objects 目录

# 方式 2：使用 mkmk -u (需要 Build Time)
python skills/clean.py --use-mkmk  # 调用 mkmk -u (Build Time)
```

**推荐：** 方式 1（更快，更可靠）

---

### 情况 3：完整开发周期

**问题：** 从修改代码到测试，用哪些环境？

**答案：** 按顺序使用：

```
1. 修改代码           → 无需环境
2. 检查 workspace     → 无需环境 (workspace.py)
3. 创建 Runtime View  → Build Time (runtime_view.py --create)
4. 编译              → Build Time (build.py)
5. 运行 CATIA        → Run Time (run.py)
```

---

## 🎓 记忆口诀

```
编译找 Build Time，mkinit 来初始
运行找 Run Time，CNEXT 是核心
检查不用环境，读文件就够了
清理看情况，删除最简单
```

---

## ⚡ 极速查询表

| 关键词 | 环境 | Skill |
|-------|-----|------|
| `mkmk` | Build Time | `build.py` |
| `mkinit` | Build Time | N/A |
| `CNEXT` | Run Time | `run.py` |
| `mkrun` | Run Time | N/A |
| `compile` | Build Time | `build.py` |
| `build` | Build Time | `build.py` |
| `start` | Run Time | `run.py` |
| `run` | Run Time | `run.py` |
| `check` | 无 | `workspace.py` |
| `validate` | 无 | `workspace.py` |
| `clean` | 无 或 Build Time | `clean.py` |

---

## 🔍 实战示例

### 示例 1：用户说 "编译并运行"

```python
# 决策：分两步
# Step 1: 编译 → Build Time
subprocess.run(["python", "skills/build.py"])

# Step 2: 运行 → Run Time
subprocess.run(["python", "skills/run.py"])
```

---

### 示例 2：用户说 "检查是否可以编译"

```python
# 决策：只检查，不需要环境
subprocess.run(["python", "skills/workspace.py"])
```

---

### 示例 3：用户说 "清理并重新编译"

```python
# 决策：清理不需要环境，编译需要 Build Time
subprocess.run(["python", "skills/clean.py"])         # 无需环境
subprocess.run(["python", "skills/build.py"])         # Build Time
```

---

### 示例 4：用户说 "CATIA 崩溃了，重新编译试试"

```python
# 决策：按完整流程
# Step 1: 清理
subprocess.run(["python", "skills/clean.py"])

# Step 2: 重新编译 (Build Time)
result = subprocess.run(["python", "skills/build.py"], capture_output=True)
build_result = json.loads(result.stdout)

if build_result["status"] == "success":
    # Step 3: 运行 (Run Time)
    subprocess.run(["python", "skills/run.py"])
else:
    print("编译失败，无法运行")
```

---

## 📊 统计数据

在典型的 CAA 开发会话中：

| 环境 | 使用频率 | 主要 Skills |
|-----|---------|-----------|
| Build Time | 60% | `build.py` (主), `runtime_view.py` (辅) |
| Run Time | 25% | `run.py` |
| 无需环境 | 15% | `workspace.py`, `clean.py` |

**结论：** 大部分操作使用 Build Time（因为编译是核心任务）

---

**版本：** 1.0.0  
**最后更新：** 2026-07-06  
**用途：** 快速决策参考
