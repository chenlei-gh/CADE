# CAA Code Style & Organization

## 文件组织

### 标准 Module 布局

```
MyModule.m/
├── Imakefile.mk                ← 编译配置
├── PublicInterfaces/           ← 对外接口（其他模块可见）
│   └── IMyService.h
├── LocalInterfaces/            ← 内部实现（模块内可见）
│   ├── MyCommand.h
│   └── MyDialog.h
├── src/                        ← 实现代码
│   ├── MyCommand.cpp
│   ├── MyCommandHeader.cpp     ← 命令注册（必须单独文件）
│   ├── MyDialog.cpp
│   └── IMyService.cpp          ← 接口实现
└── (ProtectedInterfaces/)      ← mkmk 自动生成，不手动编辑
```

### 文件关系

```
PublicInterfaces/I*.h  ← 声明 + 导出宏
    ↓ implements
LocalInterfaces/*.h    ← 组件类声明
    ↓
src/*.cpp              ← 实现
    ↓
src/*Header.cpp        ← 命令注册（仅 Command）
```

## 代码风格

### 头文件保护

```cpp
// ✅ 模块名_文件名_H 格式
#ifndef AT_UI_ATAutoRenameCmd_H
#define AT_UI_ATAutoRenameCmd_H

// ... code ...

#endif
```

### Include 顺序

```cpp
// 1. 自身头文件
#include "ATAutoRenameCmd.h"

// 2. 系统框架
#include "CATBaseUnknown.h"
#include "CATStateCommand.h"

// 3. 局部接口
#include "IATNamingService.h"
#include "ATAutoRenameDlg.h"

// 4. 标准库
#include <iostream>
```

### 成员变量命名

```cpp
class ATAutoRenameCmd : public CATStateCommand {
private:
    CATFeatureImportAgent *_pAgent;     // _p 前缀 = 指针
    ATAutoRenameDlg      *_pDlg;       // _p 前缀
    CATUnicodeString      _newName;    // _ 前缀 = 成员变量
    int                   _count;      // _ 前缀
    static int            s_instanceCount; // s_ 前缀 = 静态
};
```

### 常量定义

```cpp
// ✅ 使用 constexpr 或 static const
static const int MAX_NAME_LENGTH = 256;
constexpr double DEFAULT_TOLERANCE = 0.001;

// ✅ 枚举类
enum class RenameMode { Prefix, Suffix, Replace };
```

## 注释规范

### 类注释

```cpp
/**
 * @brief 批量重命名命令
 *
 * 支持三种重命名模式：
 *   - Prefix:  在原名前加前缀
 *   - Suffix:  在原名后加后缀
 *   - Replace: 完全替换原名
 *
 * 示例:
 *   ATAutoRenameCmd cmd;
 *   cmd.SetMode(RenameMode::Prefix);
 *   cmd.SetValue("AT_");
 *   cmd.Execute();
 *
 * @see IATNamingService
 * @see ATAutoRenameDlg
 */
class ATAutoRenameCmd : public CATStateCommand { ... };
```

### 方法注释

```cpp
/**
 * 重命名单个特征对象
 *
 * @param iSpecObj  要重命名的特征对象
 * @param iNewName  新名字
 * @return S_OK 成功, E_INVALIDARG 参数无效, E_FAIL 重命名失败
 */
HRESULT Rename(CATISpecObject *iSpecObj, CATUnicodeString &iNewName);
```

### 行内注释规则

```cpp
// ❌ 废话注释
int count = 0;  // 初始化 count 为 0

// ✅ 解释 why，不是 what
int count = 0;  // 重置计数器，避免上次批量操作残留
```

## 宏使用规范

```cpp
// CATDeclareClass — 类声明宏（放在类定义内）
class MyCmd : public CATStateCommand {
    CATDeclareClass;
};

// CATImplementClass — 类实现宏（放在 .cpp 文件）
CATImplementClass(MyCmd, Implementation, CATStateCommand, CATNull);

// CATDeclareInterface — 接口声明宏
class IMyService : public CATBaseUnknown {
    CATDeclareInterface;
};

// CATImplementInterface — 接口实现宏
CATImplementInterface(IMyService, CATBaseUnknown);

// CATImplementBOA — BOA 绑定宏
CATImplementBOA(IMyService, CATBaseUnknown);

// MacDeclareHeader — 命令注册宏
MacDeclareHeader(MyCmdHeader);
```

## 公共方法排序

按可见性从高到低：

```cpp
class MyCmd : public CATStateCommand {
    CATDeclareClass;

public:
    // 1. 构造/析构
    MyCmd();
    virtual ~MyCmd();

    // 2. 生命周期（从父类继承）
    virtual CATStatusChangeRC GetState(...);
    virtual CATBoolean           Condition();
    virtual CATStatusChangeRC Activate(...);
    virtual CATStatusChangeRC Desactivate(...);
    virtual CATStatusChangeRC Cancel(...);

    // 3. 业务方法
    HRESULT SetMode(RenameMode iMode);
    HRESULT Execute();

    // 4. 回调
    CATStatusChangeRC OnSelect(...);

private:
    // 5. 私有成员
    RenameMode _mode;
};
```

## AI 生成清单

- [ ] 头文件保护用 `MODULE_CLASS_H` 格式
- [ ] Include 顺序：自身 → 系统 → 局部 → 标准库
- [ ] 成员变量用 `_` 前缀，指针加 `_p`
- [ ] 类和方法有 `@brief` 注释
- [ ] Public 在前，Private 在后
- [ ] 不写废话注释（不解释 what，解释 why）
