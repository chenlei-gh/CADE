---
id: fp.statecommand_check_header
title: Check Header Command Must Not Be a StateCommand / 常驻面板回调不得靠 StateCommand 续命
category: knowledge
domain: failure_patterns
severity: runtime_error
apis: [CATStateCommand, CATCommand, CATAfrCheckHeaderAccessor, CATDlgDialog, AddAnalyseNotificationCB, RequestDelayedDestruction]
frameworks: [DialogEngine, ApplicationFrame]
keywords: [check header, toggle, panel not opening, Activate not called, agent competition, StateCommand, modeless panel, callback lifetime, 有文档不弹窗]
tags: [failure_pattern, runtime, ui, command, lifecycle, check_header]
release: [R28]
automation: manual
not_automatable_because: "形态是逻辑分支而非可静态判定的语法错误：用 CATStateCommand 保回调寿命与用 CATDlgDialog 自订阅，代码层面都是合法的 AddAnalyseNotificationCB 调用，差异在 this 指向的对象寿命语义。静态规则无法区分'有理由的 StateCommand（向导）'与'为续命而滥用的 StateCommand（面板）'，需依赖设计评审与本文档的架构红线。若后续为 ui_lint 增加'check header 目标类为 CATStateCommand 时告警'的启发式，可升级为 rule。"
capabilities: []
---
# Check Header Command Must Not Be a StateCommand / 常驻面板回调不得靠 StateCommand 续命

## 症状

Check header（`CATAfrCheckHeaderAccessor` 切换按钮）触发的命令，在 **CATIA 未打开任何文档时工作正常**（面板弹出）；**一旦打开任何文档（CATPart / CATProduct 都一样），再点击按钮，面板完全不弹出**——`Activate()` 根本未被调用。反复修 3 次都复发。

## 原因

为了让"点击面板列表行"的 `GetListSelectNotification` 回调的 `this` 存活，把命令从普通 `CATCommand`（构造函数干活 + `RequestDelayedDestruction`，已验证可用）改成了 `CATStateCommand`（`Activate()` 干活），试图用 StateCommand 的长寿命保住回调。

**这个转换本身就是回归源**：

`CATStateCommand` 是为**多步状态机向导**设计的——它作为 editor 的**当前 agent** 运行 statechart。当有文档打开时，editor 命令栈里已存在活动命令（如 Select），check header 触发的 StateCommand 要抢占 agent 位置，与活动命令发生竞争，导致 `Activate()` 不被调用、命令被立即替换。**无文档时没有 editor 命令栈，没有竞争，反而表现正常**——这正是"有文档不弹窗、无文档正常"这一矛盾现象的根因。

纯静态代码分析无法发现：代码逻辑上 `if (_action==1) ShowPanel()` 看起来完全正确，问题出在命令分发的运行时 agent 语义上。

## 修复（架构级，非补丁）

**不要延长命令寿命来保回调，要让回调挂在天然长寿的对象上。**

`CATDlgDialog` 继承自 `CATCommand`，因此面板对话框自己就能调 `AddAnalyseNotificationCB`——把面板做成 `CATDlgDialog` 子类，**让它订阅自己的控件通知**。回调 `this` = 面板单例，寿命与面板一致，命令就可以回到一次性的普通 `CATCommand`：

```cpp
// ✅ 面板对话框（长寿命单例）自订阅——回调 this 永远有效
class CAABOMPanelDlg : public CATDlgDialog {
    CAABOMPanelDlg(CATDialog *p) : CATDlgDialog(p, "Panel", CATDlgGridLayout|CATDlgWndNoButton|CATDlgWndNoDecoration) {
        _pList = new CATDlgMultiList(this, "List");
        AddAnalyseNotificationCB(_pList, _pList->GetListSelectNotification(),
            (CATCommandMethod)&CAABOMPanelDlg::OnListSelect, NULL);
    }
    ~CAABOMPanelDlg() {
        RemoveAnalyseNotificationCB(_pList, _pList->GetListSelectNotification(), NULL);
    }
};

// ✅ 开关命令：一次性、短寿命，构造即干活即自毁
CAABOMToolCmd::CAABOMToolCmd(void *arg) : CATCommand() {
    if (CATPtrToINT32(arg) == 1) { /* show/refresh 面板单例 */ }
    else                         { /* hide 面板单例 */ }
    RequestDelayedDestruction();
}
CATCreateClassArg(CAABOMToolCmd, void *);
```

## 预防规则

- [ ] `CATStateCommand` **只**用于需要状态机的向导式命令；**禁止**用 StateCommand 仅为"保住某个回调的 this"
- [ ] 常驻非模态面板的控件回调，一律由面板 `CATDlgDialog` 子类自订阅（`this` = 面板单例），开关命令保持普通短寿命 `CATCommand`
- [ ] 排查"check header 有文档不弹窗、无文档正常"时，第一怀疑对象：目标命令是否被写成了 `CATStateCommand`
- [ ] 行为层修复（加日志确认 `Activate` 是否被调用、`_action` 值）优先于凭静态代码逻辑猜测——该 bug 静态分析看起来"逻辑完全正确"

## 相关

- [fp_dialog_cancel_not_desactivate.md](fp_dialog_cancel_not_desactivate.md) — 对话框关闭走 Cancel 而非 Desactivate（同属命令生命周期误判）
- [event_patterns.md](../ui/event_patterns.md) — 事件绑定与回调签名规范
- 实现证据：`CAABOMTool.edu/CAABOMToolCmd.m/src/CAABOMPanelDlg.cpp`（自订阅面板）、`CAABOMToolCmd.cpp`（回退为普通 CATCommand）
