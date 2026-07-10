# CAA Imakefile Advanced Usage

## 基本结构

```makefile
# Module Imakefile.mk
MODULE = MyModule

# 源文件
SOURCES += \
    src/MyCommand.cpp \
    src/MyCommandHeader.cpp \
    src/MyDialog.cpp \
    src/IMyService.cpp

# 链接库
LOCAL_LIBS += \
    CATMathematics \
    CATVisualization \
    CATDialogEngine
```

## 常用变量

| 变量 | 用途 | 示例 |
|------|------|------|
| `MODULE` | 模块名 | `MODULE = MyModule` |
| `SOURCES` | 源文件列表 | `SOURCES += src/*.cpp` |
| `LOCAL_LIBS` | 链接库 | `LOCAL_LIBS += CATMathematics` |
| `PREREQ_COMPONENTS` | 前置组件 | `PREREQ_COMPONENTS += System` |
| `LOCAL_CCFLAGS` | 编译选项 | `LOCAL_CCFLAGS += -DDEBUG_MODE` |
| `LOCAL_INCLUDES` | include 路径 | `LOCAL_INCLUDES += ../SharedHeaders` |
| `BUILT_SOURCES` | IDL 生成源 | `BUILT_SOURCES += IMyService.idl` |

## 链接库选择指南

### CATIA 核心库

```makefile
# 数学
LOCAL_LIBS += CATMathematics

# 可视化
LOCAL_LIBS += CATVisualization

# 对话框
LOCAL_LIBS += CATDialogEngine

# 特征
LOCAL_LIBS += CATMecMod Interfaces

# 几何
LOCAL_LIBS += CATTessellation CATTopology

# 选择
LOCAL_LIBS += CATInteractiveInterfaces
```

### 按功能选库

| 你的功能 | 需要的库 |
|---------|---------|
| 创建 Feature | `CATMecMod Interfaces` |
| 创建 Dialog | `CATDialogEngine` |
| 几何计算 | `CATMathematics CATTopology` |
| 选择对象 | `CATInteractiveInterfaces` |
| 文件 I/O | `CATSysMultiCAA` |
| 批处理 | `CATBatchInfra` |

## 预编译宏

```makefile
# 调试模式
LOCAL_CCFLAGS += -DDEBUG_MODE
LOCAL_CCFLAGS += -DTRACE_ACTIVE

# 条件编译
ifeq ($(OS),Windows)
    LOCAL_CCFLAGS += -DWIN32
endif

# 版本标记
LOCAL_CCFLAGS += -DVERSION=2.1.0
```

## IDL 接口

```makefile
# 使用 IDL 的接口
BUILT_SOURCES += IMyService.idl

# IDL 自动生成：
#   IMyService.h
#   IMyService.cpp  
#   放到 ProtectedInterfaces/
```

## Framework Imakefile

```makefile
# Framework/Imakefile.mk
MODULES += \
    MyModule1 \
    MyModule2 \
    MyModule3
```

## 编译依赖

```makefile
# 声明需要先编译的模块
PREREQ_COMPONENTS += \
    System \
    ObjectModelerBase \
    Mathematics

# 模块间依赖
PREREQ_COMPONENTS += \
    AT_Core          # UI 依赖 Core
```

## AI 生成规则

- [ ] 每个 `src/*.cpp` 都要加到 `SOURCES`
- [ ] 每个 `src/*Header.cpp`（命令注册）也要加到 `SOURCES`
- [ ] IDL 接口用 `BUILT_SOURCES` 不是 `SOURCES`
- [ ] 用到了 Dialog → 加 `CATDialogEngine`
- [ ] 用到了 Feature → 加 `CATMecMod Interfaces`
- [ ] Framework 的 `MODULES` 列表和实际模块目录一致
- [ ] 模块间有依赖 → 加 `PREREQ_COMPONENTS`
