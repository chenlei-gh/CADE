---
id: ui.dialog_dataflow
title: Dialog Dataflow & Architecture
category: knowledge
domain: ui
keywords: [dataflow, command-dialog, persistence, NLS, architecture, communication, preferences]
apis: [CATDlgDialog, CATStateCommand, CATMsgCatalog, CATNotification]
requires: [ui.dialog]
patterns: [ui.master_detail, ui.dynamic_form]
examples: []
release: [R19, R28]
tags: [ui, architecture, dataflow]
---

# CAA UI Architecture & Dataflow

## 整体架构

```
Command (CATStateCommand)
    │
    ├── owns → Dialog (CATDlgDialog)
    │            │
    │            ├── Layout (CATDlgFrame + GridLayout)
    │            ├── Widgets (Editor, Combo, Radio, ...)
    │            └── Validation (ValidateInput)
    │
    ├── owns → Agent (CATFeatureImportAgent)
    │            │
    │            └── Events (OnSelect, OnApply, OnCancel)
    │
    └── registered in → Workbench/Addin (Toolbar)
```

## 数据流向

### 模式 1：Dialog → Command（最常见）

```
用户点击 Apply
    ↓
Dialog.OnApply() 触发的通知
    ↓
Command.OnApply 回调
    ↓ 读取 Dialog 数据
_pNameEditor->GetText()  →  CATUnicodeString name
_pCombo->GetSelect()     →  int mode
_pSpinner->GetValue()    →  int count
    ↓
Command 执行业务逻辑
    ↓
关闭 Dialog / 继续等待
```

### 模式 2：Agent → Command → Dialog

```
用户选择几何对象
    ↓
Agent.OnSelect 通知
    ↓
Command.OnSelect 回调
    ↓ 获取特征数据
CATISpecObject_var spObj = GetSelectedObject()
CATUnicodeString name = GetFeatureName(spObj)
    ↓ 更新 Dialog 显示
_pDlg->SetCurrentName(name)
_pDlg->SetPreview(length, area)
```

## Command-Dialog 通信契约

```cpp
// Dialog 提供 Getter（Command 读取用户输入）
class MyDlg : public CATDlgDialog {
public:
    CATUnicodeString GetNewName();
    CATBoolean IsPrefixMode();
    int GetCounterValue();
};

// Dialog 提供 Setter（Command 更新 Dialog 显示）
class MyDlg : public CATDlgDialog {
public:
    void SetCurrentName(const CATUnicodeString &iName);
    void SetPreview(double iLength, double iArea);
    void SetProgress(int iPercent);
};

// Command 持有 Dialog 引用
class MyCmd : public CATStateCommand {
private:
    MyDlg *_pDlg;           // 一个 Command 通常一个 Dialog
    CATFeatureImportAgent *_pAgent;  // 一个或多个 Agent
};
```

## 持久化偏好

记住用户上次的设置，下次打开自动恢复：

```cpp
// 保存偏好（在 Desactivate 中）
CATStatusChangeRC MyCmd::Desactivate(...) {
    if (_pDlg) {
        _prefs.name = _pDlg->GetNewName();
        _prefs.mode = _pDlg->GetMode();
        _prefs.counter = _pDlg->GetCounterValue();
    }
    return CATStatusChangeRCCompleted;
}

// 恢复偏好（在 Activate 中）
CATStatusChangeRC MyCmd::Activate(...) {
    _pDlg = new MyDlg(this);
    _pDlg->Build();
    _pDlg->SetCurrentName(_prefs.name);      // 恢复上次输入
    _pDlg->SetMode(_prefs.mode);
    _pDlg->SetVisibility(CATDlgShow);
    return CATStatusChangeRCCompleted;
}
```

> ⚠️ **重要修正**：`CATStatusChangeRC` 只有两个合法值：`CATStatusChangeRCCompleted` 与 `CATStatusChangeRCAborted`（定义于 `CATCommand.h`）。不存在 `CATStatusChangeContinue`/`CATStatusChangeCompleted`/`CATStatusChangeCanceled` 这些值。`Activate()` 返回 `CATStatusChangeRCCompleted` 表示激活成功完成（即使对话框仍在显示，命令已进入等待交互的“完成”状态，与对话框是否关闭无关）。

## NLS 国际化

```cpp
// ❌ 硬编码（且构造签名为 (parent, name, style)，第3参不是标题）
//    硬编码字符串会覆盖 CATIA NLS 查找，中文环境下仍显示英文
_pNameLabel = new CATDlgLabel(pFrame, "NameLbl");
_pNameLabel->SetTitle(CATUnicodeString("New Name:"));

// ✅ BuildMessage + fallback（生产项目实证模式）：
//    语义 key + 英文 fallback 保底，catalog 缺失/条目缺失都能显示
static CATUnicodeString NLS(const char* iKey, const char* iFallback)
{
    return CATMsgCatalog::BuildMessage("MyFramework", iKey, NULL, 0, iFallback);
}
_pNameLabel = new CATDlgLabel(pFrame, "NameLbl");
_pNameLabel->SetTitle(NLS("MyDlg.NameLbl", "New Name:"));
```

**对话框 NLS 三条规则（生产项目 + B28 安装目录实证）：**

1. **catalog 用 framework 共享名**（`msgcatalog/<Framework>.CATNls`），所有对话框/命令的消息合并进同一个文件；**key 用语义名**（`类名.控件名`，如 `MyDlg.Title`、`MyDlg.ApplyBtn`），不与控件对象名耦合，重命名控件不破 NLS
2. **代码里用 `BuildMessage(catalog, key, NULL, 0, fallback)`**：fallback 是编译进二进制的英文保底，catalog 没部署时界面仍可读；中文用户则自动取 `Simplified_Chinese/` 下的译文
3. **多语言用目录区分，不是文件名后缀**：英文放 `msgcatalog/<Framework>.CATNls`（UTF-8），中文放 `msgcatalog/Simplified_Chinese/<Framework>.CATNls`（**必须 GBK 编码**，B28 官方中文 catalog 实测为 GBK；UTF-8 写入会被 CATIA 读成乱码）。⚠️ 平铺的 `Xxx_Chinese.CATNls` CATIA **不会加载**；中文 catalog 内容**不能含 emoji**（GBK 无法编码）

`CNext/resources/msgcatalog/MyFramework.CATNls`（英文/默认，UTF-8）：
```
MyDlg.Title = "My Dialog";
MyDlg.NameLbl = "New Name:";
```

`CNext/resources/msgcatalog/Simplified_Chinese/MyFramework.CATNls`（中文，GBK）：
```
MyDlg.Title = "我的对话框";
MyDlg.NameLbl = "新名称:";
```

> 备选：CATDlg 控件也支持**零代码 NLS**（不设标题，CATIA 按 `catalog=类名`、key=`FrameId.控件名.Title` 自动解析，见 CAAAfrBoundingElementCmd 样例）。局限：catalog 文件名必须 = 对话框类名（无法共享）、key 与控件对象名耦合、无 fallback、不支持运行时动态文本。CADE 生成器默认走上面的 BuildMessage 模式。

## 关键原则

1. **Dialog 只管 UI** — 不访问 CATIA 数据模型，不执行业务逻辑
2. **Command 只管逻辑** — 通过 Getter 读取 Dialog，不直接操作 Dialog 控件
3. **Agent 只管道选择** — 不处理业务，把选中对象传给 Command
4. **数据单向流动** — Dialog → Command（读取），Command → Dialog（显示）
