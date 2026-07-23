---
id: fp.paste_cross_doc_catpathelement
title: Cross-Document Paste Must Not Pass CATPathElement Targets / 跨文档 Paste 不能传 CATPathElement targets
category: knowledge
domain: failure_patterns
severity: crash_uncatchable
apis: [CATICutAndPastable, CATPathElement, Paste, BoundaryExtract, Extract]
frameworks: [MechanicalModeler, ObjectModelerBase]
keywords: [paste, cross-document, 跨文档, CATPathElement, CATICutAndPastable, clipboard, 剪贴板, copy paste, runtime exception, crash, CAAPriCCP, Paste NULL, CCP]
tags: [failure_pattern, crash, copy_paste, clipboard, cross_document]
release: [R19, R28]
---
# Cross-Document Paste Must Not Pass CATPathElement Targets / 跨文档 Paste 不能传 CATPathElement targets

## 症状

跨文档（源 Part → 新建 Part）使用 `CATICutAndPastable::Paste()` 粘贴 Body 时，传入显式 `CATPathElement` targets（照抄 `CAAPriCCP.cpp` 样例模式），CATIA 弹出"运行时异常/单击确定终止"对话框后整个进程崩溃。

**`try/catch(...)` 无法捕获**（异常来自 CAA 框架内部，`std::set_terminate` 处理器也未触发）——这是这类崩溃最危险的特征：没有任何拦截和恢复的机会。

## 原因

`CAAPriCCP.cpp` 样例演示的是**同文档内** Paste（源和目标是同一个 PrtContainer），`CATPathElement` 引用的对象上下文与目标容器一致，安全可用。

但**跨文档** Paste 时，`CATPathElement` 引用的是**源文档**上下文中的对象，Paste 内部尝试在目标上下文中解析这些路径元素时访问非法，直接进程级崩溃。

## 修复

`Paste()` 的第二参数 `iToCurObjects` 传 `NULL`，让目标容器自行决定粘贴位置（默认粘贴到 MainBody）：

```cpp
// ❌ 崩溃：跨文档传入源上下文的 CATPathElement
CATPathElement targetPath(...);  // 引用源文档对象
pPasteable->Paste(iObjectToCopy, &targetPath, NULL);

// ✅ 安全：目标容器自行决定落点（默认 MainBody）
pPasteable->Paste(iObjectToCopy, NULL, NULL);
```

接口签名 `Paste(iObjectToCopy, iToCurObjects=NULL, iAnImposedFormat=NULL)` 设计上就支持 NULL。

跨文档 CCP 安全通路：

```
源文档   BoundaryExtract → Extract 到剪贴板
剪贴板   BoundaryExtract（取出）
目标文档 Paste(iObj, NULL, NULL)
```

## 核心教训

- **CAA 样例代码的用法不能盲目跨场景照抄**——同文档安全的操作在跨文档时可能进程崩溃。照抄样例前先确认样例的上下文假设（同文档？同会话？同容器？）与你的场景是否一致。
- 如果确实需要精确控制跨文档粘贴位置，改走 **Automation 层**的 `Selection.Copy / PasteSpecial`（C# 版用此通路，已验证可行），不要在 C++ 层硬传 `CATPathElement`。
- 凡是 `try/catch` 拦不住的 CAA 崩溃，优先怀疑：传入了其他文档/其他容器上下文的对象引用。

（来源：2026-07-23，CADE `CAAPartToAsm.edu` S2 跨文档 Paste 崩溃排查，`CAAPtsCopyPaste.cpp`）
