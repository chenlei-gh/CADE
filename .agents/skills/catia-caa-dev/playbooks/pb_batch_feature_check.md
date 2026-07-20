---
id: pb.batch_feature_check
title: Batch Feature Check / 批量特征检查
category: playbook
domain: part
keywords: [batch, feature, check, fillet, hole, chamfer, validate, rule, filter]
capabilities: [cap.feature_recognition, cap.parameter_system]
apis: [CATISpecObject, CATIEdgeFillet, CATINewHole, CATIChamfer, CATIPrtPart, IsSubTypeOf]
frameworks: [ObjectSpecsLegacy, MecModInterfaces, PartInterfaces]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, batch, check, feature]
---
# Batch Feature Check (批量特征检查)

遍历 Part 中所有特征，按规则检查并输出结果。

## ⚠️ 重要修正

早期版本存在多处虚构/错误 API，已按 [cap.feature_recognition](../capabilities/feature-recognition.md)、
[part.hole](../knowledge/part/hole.md)、[part.fillet](../knowledge/part/fillet.md) 核实修正：

| 旧写法（虚构/错误） | 真实情况 |
|---------------|---------|
| `CATIPrtPart::GetMechanicalFeatures(features)` | 不存在。`CATIPrtPart` 没有这个方法；遍历特征树用 `CATISpecObject::ListComponents()` |
| `spFeat->IsATypeOf("CATFillet")` | `CATISpecObject` 无 `IsATypeOf(char*)`。真实方法是 `IsSubTypeOf(CATUnicodeString&)`，类型名也不是 `"CATFillet"`/`"CATHole"`，是不带前缀的 StartUp 名 `"EdgeFillet"`/`"Hole"` |
| `CATListValCheckResult` | 项目自定义容器类型可以自行声明，但不要虚构成 CAA 内建容器类型；用普通 `std::vector` 或 CAA 的 `CATListOfCATBaseUnknown_var`（本例用 `std::vector` 更直观） |
| `CATIFillet::GetRadius()` | `CATIFillet` 是空标记接口，没有 `GetRadius()`。真实带方法的接口是继承自它的 `CATIEdgeFillet`（`GetFilletType()`/`GetRadius()`，仅 `CONSTANT` 类型有效） |
| `CATIHole` | 不存在。真实接口名是 `CATINewHole`（`CATISimpleHole` 是它的空标记子接口） |
| 倒角类型判断用 `IsSubTypeOf("EdgeChamfer")` | 组件名是 `Chamfer`（不带 `Edge` 前缀），应为 `IsSubTypeOf("Chamfer")`；接口是 `CATIChamfer`，`GetLength1()`/`GetLength2()` 直接返回 `double`，仅 `GetMode() == LENGTH` 时才是纯长度值 |

## 目标

- 检查所有圆角半径是否在范围内
- 检查所有孔径是否符合标准
- 检查倒角长度是否符合标准
- 输出检查报告

## 实现步骤

1. **获取 Part 容器** → `CATIPrtPart_var spPart`，取根 Feature：`CATISpecObject_var spRoot = spPart;`
2. **遍历所有特征** → `CATISpecObject::ListComponents()` 递归遍历（Visitor 模式）
3. **识别特征类型** → `IsSubTypeOf("EdgeFillet")`, `IsSubTypeOf("Hole")`, `IsSubTypeOf("Chamfer")`
4. **QueryInterface 到具体接口** → `CATIEdgeFillet_var`/`CATINewHole_var`/`CATIChamfer_var`
5. **对比规则** → 硬编码规则或配置文件
6. **输出结果** → 对话框列表 + 双击定位

## 关键代码骨架

```cpp
#include <vector>

struct CheckResult {
    CATUnicodeString featureName;
    CATUnicodeString checkType;
    CATUnicodeString expected;
    CATUnicodeString actual;
    CATBoolean passed;
};

void CheckFillet(CATISpecObject_var iFeat, std::vector<CheckResult> &oResults,
                  double iMinRadius, double iMaxRadius) {
    CATIEdgeFillet_var spFillet = iFeat;   // 不是 CATIFillet_var（那是空标记接口）
    if (NULL_var == spFillet) return;

    CATPrtFilletType type = spFillet->GetFilletType();
    if (type != CONSTANT) return;   // 仅常量半径圆角检查半径范围（枚举成员无前缀）

    double radius = spFillet->GetRadius();       // 直接返回 double，无需 boxed 解包

    // CATUnicodeString 没有 double 构造函数/Concat 静态方法，数值转字符串走 char buffer
    char buf[64];
    CheckResult r;
    r.featureName = iFeat->GetName();
    r.checkType = "FilletRadius";
    sprintf(buf, "%.2f~%.2f", iMinRadius, iMaxRadius);
    r.expected = CATUnicodeString(buf);
    sprintf(buf, "%.2f", radius);
    r.actual = CATUnicodeString(buf);
    r.passed = (radius >= iMinRadius && radius <= iMaxRadius) ? TRUE : FALSE;
    oResults.push_back(r);
}

void CheckHole(CATISpecObject_var iFeat, std::vector<CheckResult> &oResults,
               double iMinDiameter, double iMaxDiameter) {
    CATINewHole_var spHole = iFeat;   // 真实接口名，不是 CATIHole
    if (NULL_var == spHole) return;

    double diameter = 0.0;
    spHole->GetDiameter(diameter);    // void 返回，输出参数

    char buf[64];
    CheckResult r;
    r.featureName = iFeat->GetName();
    r.checkType = "HoleDiameter";
    sprintf(buf, "%.2f", diameter);
    r.actual = CATUnicodeString(buf);
    r.passed = (diameter >= iMinDiameter && diameter <= iMaxDiameter) ? TRUE : FALSE;
    oResults.push_back(r);
}

void CheckChamfer(CATISpecObject_var iFeat, std::vector<CheckResult> &oResults,
                   double iMinLength, double iMaxLength) {
    CATIChamfer_var spChamfer = iFeat;
    if (NULL_var == spChamfer) return;

    // GetMode() 返回 CATPrtChamferMode（LENGTH/LENGTH_ANGLE/CHORDAL_LENGTH_ANGLE/
    // HEIGHT_ANGLE/HOLDCURVE_ANGLE/HOLDCURVE_LENGTH，无前缀）；仅 LENGTH 模式下
    // Length1/Length2 都是纯长度值，才适合直接做长度范围检查
    CATPrtChamferMode mode = spChamfer->GetMode();
    if (mode != LENGTH) return;

    double length1 = spChamfer->GetLength1();   // 直接返回 double

    char buf[64];
    CheckResult r;
    r.featureName = iFeat->GetName();
    r.checkType = "ChamferLength";
    sprintf(buf, "%.2f", length1);
    r.actual = CATUnicodeString(buf);
    r.passed = (length1 >= iMinLength && length1 <= iMaxLength) ? TRUE : FALSE;
    oResults.push_back(r);
}

// 递归遍历整个特征树（Visitor 模式，避免深度装配下的栈溢出可改为显式栈）
void TraverseAndCheck(CATISpecObject_var iFeat, std::vector<CheckResult> &oResults) {
    if (iFeat->IsSubTypeOf("EdgeFillet")) {
        CheckFillet(iFeat, oResults, 1.0, 10.0);
    } else if (iFeat->IsSubTypeOf("Hole")) {
        CheckHole(iFeat, oResults, 3.0, 20.0);
    } else if (iFeat->IsSubTypeOf("Chamfer")) {
        CheckChamfer(iFeat, oResults, 0.5, 5.0);
    }

    // ListComponents() 返回堆分配的列表指针，调用方负责 delete
    CATListValCATISpecObject_var *pChildren = iFeat->ListComponents();
    if (pChildren != NULL) {
        for (int i = 1; i <= pChildren->Size(); i++) {
            CATISpecObject_var child = (*pChildren)[i];
            if (NULL_var != child) {
                TraverseAndCheck(child, oResults);
            }
        }
        delete pChildren;
    }
}

HRESULT CheckAllFeatures(CATIPrtPart_var iPart, std::vector<CheckResult> &oResults) {
    if (NULL_var == iPart) return E_FAIL;
    CATISpecObject_var spRoot = iPart;   // CATIPrtPart 本身也是一个 CATISpecObject
    if (NULL_var == spRoot) return E_FAIL;

    TraverseAndCheck(spRoot, oResults);
    return S_OK;
}
```

## 注意事项

- 大 Part（>500 特征）注意遍历性能，`ListComponents()` 每次调用都分配新列表，务必 `delete`
- 递归遍历避免栈溢出：极深的特征树（罕见）可改写为显式栈的迭代遍历
- 检查规则建议从配置文件读取而非硬编码
- 结果对话框支持导出为 HTML/CSV 报告
- 圆角检查仅处理 `CONSTANT`（常量半径）类型；`VARIABLE`（变量半径）圆角需要按顶点逐个用 `GetRadiusOnVertex()` 检查（见 [part.fillet](../knowledge/part/fillet.md)）
- 倒角检查仅处理 `CATPrtChamferMode::LENGTH` 模式（对称双长度）；`LENGTH_ANGLE`/`HEIGHT_ANGLE` 等模式下 `GetLength2()` 返回的是角度而非长度，不能直接用长度范围判断，需要按 `GetMode()` 分支处理
