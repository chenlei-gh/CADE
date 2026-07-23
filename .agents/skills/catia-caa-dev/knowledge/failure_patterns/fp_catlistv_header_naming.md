---
id: fp.catlistv_header_naming
title: "CATListVal Type Name ≠ Header Name"
severity: error
category: knowledge
domain: infrastructure
release: [R19, R28]
tags: [header, include, naming]
apis: [CATListValCATBaseUnknown_var, CATLISTV_CATBaseUnknown, CATLISTV_CATISpecObject, CATLISTV_CATICst]
frameworks: [System]
keywords: [CATListVal, CATLISTV, header, include, naming, fabricated]
---

# CATListVal Type Name ≠ Header Name

## 陷阱

CAA 容器类型的**类型名**和**头文件名**遵循不同的命名规则：

| 类型名（代码中使用） | 头文件名（#include） | 框架 |
|---|---|---|
| `CATListValCATBaseUnknown_var` | `CATLISTV_CATBaseUnknown.h` | System |
| `CATListValCATISpecObject_var` | `CATLISTV_CATISpecObject.h` | ObjectSpecsLegacy |
| `CATListValCATICst_var` | `CATLISTV_CATICst.h` | ConstraintModelerInterfaces |
| `CATListOfCATUnicodeString` | `CATListOfCATUnicodeString.h` | System |

**类型名是骆驼拼写**（`CATListValXxx_var`），**头文件名是全大写+下划线+V后缀**（`CATLISTV_Xxx.h`）。

AI 按类型名脑补出 `CATListValCATBaseUnknown.h` 这样的头文件——**该文件不存在**，编译报错 `fatal error C1083: 无法打开包括文件`。

## 根因

CAA 的历史命名不一致：
- `CATLISTV(T)` 是一个**宏**，展开为 `CATListValT_var`
- 宏定义在 `CATLISTV_T.h` 头文件中（全大写命名）
- 但展开后的类型名是骆驼拼写（`CATListValT_var`）

## 规则

1. **类型名 → 头文件**：去掉 `_var` 后缀 → 全转大写 → `CATListVal` → `CATLISTV_`
   - `CATListValCATBaseUnknown_var` → `CATLISTV_CATBaseUnknown.h`
   - `CATListValCATISpecObject_var` → `CATLISTV_CATISpecObject.h`
2. **宏写法**：`CATLISTV(CATBaseUnknown_var)` 等价于 `CATListValCATBaseUnknown_var`，头文件相同
3. **verifier 已自动检测**：虚构头文件（不存在于 CATIA 安装的）会被标记为 error

## 正确示例

```cpp
#include "CATLISTV_CATBaseUnknown.h"  // 正确
// #include "CATListValCATBaseUnknown.h"  // 错误！该文件不存在

CATListValCATBaseUnknown_var* pChildren = pProduct->GetChildren();
// 或等价宏写法：
CATLISTV(CATBaseUnknown_var)* pChildren = pProduct->GetChildren();
```

## 常见虚构头文件（均不存在）

- `CATListValCATBaseUnknown.h` → 正确：`CATLISTV_CATBaseUnknown.h`
- `CATListValCATISpecObject.h` → 正确：`CATLISTV_CATISpecObject.h`
- `CATListValCATIProduct.h` → 正确：`CATLISTV_CATBaseUnknown.h`（CATIProduct 无专用列表头文件）
