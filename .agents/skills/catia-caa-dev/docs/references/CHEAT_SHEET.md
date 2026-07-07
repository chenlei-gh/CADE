# Build Time vs Run Time 速查卡

> **1 秒决策指南 - AI 专用**

---

## 🎯 核心判断法

```
问：这是编译操作还是运行操作？

编译 → Build Time
运行 → Run Time
其他 → 无需环境
```

---

## ⚡ 按关键词查询

| 用户说的关键词 | 环境 | 命令 |
|-------------|-----|------|
| `编译`, `compile`, `build` | **Build Time** | `python skills/build.py` |
| `运行`, `启动`, `run`, `start` | **Run Time** | `python skills/run.py` |
| `检查`, `验证`, `check`, `validate` | 无 | `python skills/workspace.py` |
| `清理`, `clean` | 无 或 Build Time | `python skills/clean.py` |
| `mkmk` | **Build Time** | `python skills/build.py` |
| `CNEXT`, `CATIA` | **Run Time** | `python skills/run.py` |

---

## 📊 按 Skill 分类

| Skill | 环境需求 | 用途 |
|-------|---------|------|
| `build.py` | **Build Time** ⚒️ | 编译代码 |
| `run.py` | **Run Time** 🚀 | 启动 CATIA |
| `runtime_view.py --create` | **Build Time** ⚒️ | 创建 Runtime View |
| `workspace.py` | 无 📋 | 验证结构 |
| `clean.py` | 无 或 Build Time 🧹 | 清理构建 |
| `env.py` | 无 ⚙️ | 查看环境 |

---

## 🔄 标准流程

```
workspace.py      [无需环境]    检查结构
     ↓
runtime_view.py   [Build Time]   创建 Runtime View
     ↓
build.py          [Build Time]   编译
     ↓
run.py            [Run Time]     运行测试
```

---

## ⚠️ 常见错误

| 错误现象 | 原因 | 环境 | 解决 |
|---------|-----|------|-----|
| `'mkmkM' is not recognized` | 未初始化 Build Time | Build Time | 必须通过 `mkinit.bat` |
| `0xC0000142` | 直接运行 mkmkM.exe | Build Time | 必须在 cmd.exe 中初始化 |
| `CNEXT.exe not found` | 路径错误 | Run Time | 检查 config.txt |
| `Runtime View not found` | 未创建 | Run Time | 运行 `runtime_view.py --create` |

---

## 🧠 记忆口诀

```
Build Time 编译用，mkinit 打头阵
Run Time 运行时，CNEXT 是核心
工作区检查不用环境，直接读文件
两个环境分得清，CAA 开发才顺心
```

---

## 💡 特殊情况

### Q: 创建 Runtime View 用哪个环境？
**A:** Build Time（因为 `mkCreateRuntimeView` 是 Build Time 工具）

### Q: 清理用哪个环境？
**A:** 两种方式：
- 直接删除 Objects：**无需环境**（推荐，更快）
- 使用 `mkmk -u`：**Build Time**

### Q: 检查 CATIA 是否运行用哪个环境？
**A:** Run Time（需要 `psutil` 检查进程）

---

## 📝 实战示例

### 示例 1：编译并运行
```python
# Build Time
subprocess.run(["python", "skills/build.py", workspace])

# Run Time
subprocess.run(["python", "skills/run.py"])
```

### 示例 2：修复错误
```python
# 全程 Build Time
for attempt in range(5):
    result = subprocess.run(["python", "skills/build.py"])
    if success:
        break
    fix_error()
```

### 示例 3：首次设置
```python
# 无需环境
subprocess.run(["python", "skills/workspace.py"])

# Build Time
subprocess.run(["python", "skills/runtime_view.py", "--create"])
subprocess.run(["python", "skills/build.py"])

# Run Time
subprocess.run(["python", "skills/run.py"])
```

---

## 🎓 AI 使用建议

### ✅ 正确做法
1. **编译前不需要问**，直接用 Build Time
2. **运行前检查是否已运行**（`run.py --check`）
3. **每个环境独立使用**，不要混合
4. **编译失败后修复代码**，然后重新编译

### ❌ 错误做法
1. ~~直接运行 `mkmkM.exe`~~（会失败）
2. ~~编译和运行用同一个环境~~（会冲突）
3. ~~假设编译成功就能运行~~（可能没有 Runtime View）
4. ~~尝试在 Python 中设置环境变量~~（必须在 cmd.exe 中）

---

## 📚 完整文档

需要更多细节？查看：

- **完整指南**: `docs/BUILD_RUN_TIME_USAGE_GUIDE.md`
- **快速决策**: `docs/QUICK_DECISION_TREE.md`
- **实战示例**: `docs/AI_WORKFLOW_EXAMPLES.md`

---

**版本:** 1.0.0 | **用途:** AI 快速参考 | **大小:** 极简速查
