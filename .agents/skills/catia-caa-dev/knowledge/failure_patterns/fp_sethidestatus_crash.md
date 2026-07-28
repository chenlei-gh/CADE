---
id: fp.sethidestatus_crash
title: SetHideStatus Hides Feature Crash / SetHideStatus 隐藏特征崩溃
category: knowledge
domain: failure_patterns
severity: crash
apis: [CATIMechanicalVisu, CATIVisProperties, CATIVisPropertiesAbstract, CATModifyVisProperties]
frameworks: [MecModInterfaces, Visualization]
keywords: [SetHideStatus, hide, show, 隐藏, 基准面, crash, SetPropertiesAtt, CATVPShow, CATShowAttr, CATNoShowAttr, visu]
tags: [failure_pattern, runtime, crash, visualization, mecmod]
release: [R28]
automation: rule
static_rule: [ui_lint:visu_sethidestatus]
---

# SetHideStatus Hides Feature Crash / SetHideStatus 隐藏特征崩溃

## 症状

对 Part 文档中的特征（实测：默认基准面）调用 `CATIMechanicalVisu::SetHideStatus(1)` 隐藏时 **CATIA 直接崩溃**（运行时硬崩溃，非异常、不可 catch）。实测两种上下文均崩：

- 装配文档中遍历各 Part 隐藏基准面 → 崩（代码注释历史记录："hiding here crashes"）
- 改为在独立打开的 Part 文档中隐藏 → **仍然崩**

方法存在、签名正确、编译通过——崩溃只在运行时暴露，静态检查和 mkmk 都无法预知。

## 原因

`SetHideStatus`（`MecModInterfaces/PublicInterfaces/CATIMechanicalVisu.h`，`virtual void SetHideStatus(const int& iStatus) = 0`，0=visible / 1=hidden）只是机械特征可视化状态的**裸 setter**：不更新图形属性表、不发可视化变更通知。在特征级（尤其基准面这类 origin 元素）直接调用，底层 visu 数据结构状态不一致导致崩溃。

CAADoc 官方样例走的是另一条通路（`CAADoc/CAAMechanicalModeler.edu/CAAMmrCommands.m/src/CAAMmrSetShowModeCmd.cpp`，B28 实测存在）：

```cpp
// 1. 从 feature 查询 CATIVisProperties（注意：不是 CATIMechanicalVisu）
CATIVisProperties_var spVisProps = spFeature;

// 2. 读当前 show 状态
CATVisPropertiesValues visValues;
spVisProps->GetPropertiesAtt(visValues, CATVPShow, CATVPGlobalType);

// 3. 写新状态：CATShowAttr=显示 / CATNoShowAttr=隐藏
visValues.SetShowAttribut(CATNoShowAttr);
spVisProps->SetPropertiesAtt(visValues, CATVPShow, CATVPGlobalType);

// 4. 发变更通知（SetHideStatus 通路缺失的关键环节）
CATModifyVisProperties notif(spFeature, NULL, CATVPGlobalType, CATVPShow, visValues);
```

签名核实（B28）：`SetPropertiesAtt` 定义在**父接口** `CATIVisPropertiesAbstract`（`Visualization/PublicInterfaces/CATIVisPropertiesAbstract.h:103`），`CATIVisProperties` 继承它。第三参数 `iGeomType` 默认即 `CATVPGlobalType`，可省。

## 修复

需要隐藏/显示机械特征（含基准面）时：

- ✅ 用 `CATIVisProperties::SetPropertiesAtt(values, CATVPShow, CATVPGlobalType)` + `CATModifyVisProperties` 通知（官方样例通路）
- ❌ 不用 `CATIMechanicalVisu::SetHideStatus`——存在但在此上下文是雷区

Include：`CATIVisProperties.h`、`CATVisPropertiesValues.h`、`CATModifyVisProperties.h`（均 Visualization 框架）；`LOCAL_LIBS` 加 `CATVisualization`。

## 预防规则

- [ ] 隐藏/显示机械特征一律走 `CATIVisProperties` + `CATVPShow` 通路，禁止 `SetHideStatus`
- [ ] 改可视化状态后必须发 `CATModifyVisProperties` 通知，否则视图不刷新
- [ ] "方法存在且编译通过"不等于"运行安全"——运行时行为问题只有实机执行能暴露，此类经验必须沉淀为 FP 防复发
- [ ] 优先选 CAADoc 官方样例验证过的通路，而非仅"存在"的方法

## 边界与局限

- 实测崩溃上下文为**特征级 show/hide**（基准面，R28）。`SetHideStatus` 在其他上下文（如 Body 级）是否同样崩溃未验证——lint 规则因此用 **warning** 而非 error，提示而非阻断
- `CATIMechanicalVisu` 上仍有 `Is3DVisible()` 等只读方法可安全使用；雷区仅限 `SetHideStatus` 这个写方法
