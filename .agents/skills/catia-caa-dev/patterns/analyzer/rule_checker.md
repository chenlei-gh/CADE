---
id: analyzer.rule
title: Rule Checker
category: pattern
domain: analyzer
keywords: [rule, check, validate, specification, compliance, standard, severity]
apis: [CATISpecObject, CATICkeParm]
requires: [mecmod.feature, part.fillet]
patterns: [analyzer.geometry]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [pattern, rule, check, validation]
---

# Rule Checker Pattern (规则检查模式)

将企业规范转化为可执行的检查规则，对每个 Feature 进行逐条验证。

## 适用场景

- DFM 检查（制造可行性分析）
- 企业标准符合性检查
- 质量门禁检查
- 设计规范自动审查

## 架构模式

```
Rule Engine
  │
  ├── Rule Set (规则集)
  │     ├── Rule 1: Min Radius
  │     ├── Rule 2: Max Radius
  │     ├── Rule 3: Min Hole Diameter
  │     └── ...
  │
  ├── Check Context (上下文)
  │     ├── Current Feature
  │     ├── Feature Name
  │     └── Feature Path
  │
  └── Check Result
        ├── Pass/Fail
        ├── Message
        ├── Severity (Error/Warning/Info)
        └── Suggestion (修复建议)
```

## 实现步骤

### Step 1: 定义规则

```cpp
struct Rule {
    CATUnicodeString id;        // 规则编号 (如 "R-FILLET-001")
    CATUnicodeString name;      // 规则名称
    CATUnicodeString targetType;// 目标 Feature 类型
    CATUnicodeString description;
    int severity;               // 0=Info, 1=Warning, 2=Error
};
```

### Step 2: 实现规则检查

```cpp
class RuleChecker {
public:
    struct CheckResult {
        CATUnicodeString ruleId;
        bool passed;
        CATUnicodeString message;
        CATISpecObject_var offender;
    };

    virtual CheckResult Check(CATISpecObject_var pFeature) = 0;
};

// 示例：圆角半径最小检查
class MinRadiusRule : public RuleChecker {
public:
    MinRadiusRule(double minR) : m_minRadius(minR) {}

    CheckResult Check(CATISpecObject_var pFeature) override {
        if (!pFeature->IsATypeOf("EdgeFillet")) {
            return {m_ruleId, true, "N/A", pFeature};
        }
        CATIFillet_var pFillet = pFeature;
        double r = pFillet->GetRadius()->Value();
        bool pass = r >= m_minRadius;
        return {
            m_ruleId,
            pass,
            pass ? "OK" : "Radius too small",
            pFeature
        };
    }

private:
    double m_minRadius;
    CATUnicodeString m_ruleId = "R-FILLET-001";
};
```

### Step 3: 组合规则集

```cpp
class RuleSet {
public:
    void AddRule(RuleChecker* pRule) {
        m_rules.Append(pRule);
    }

    void Run(CATISpecObject_var pFeature) {
        for (int i = 1; i <= m_rules.Size(); i++) {
            CheckResult result = m_rules[i]->Check(pFeature);
            if (!result.passed) {
                m_failures.Append(result);
            }
        }
    }

    CATListValCheckResult GetFailures() { return m_failures; }

private:
    CATListValRuleChecker m_rules;
    CATListValCheckResult m_failures;
};
```

## 关键点

1. **规则独立** —— 每条规则是独立的 Checker，方便增加/删除
2. **Severity 分级** —— Error 阻断、Warning 提醒、Info 参考
3. **建议修复方案** —— 结果中应包含 Suggestion
4. **可配置** —— 规则参数（如最小半径值）应从外部配置读入
