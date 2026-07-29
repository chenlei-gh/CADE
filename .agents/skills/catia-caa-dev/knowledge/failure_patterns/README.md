# Failure Patterns — 作者约定

Failure Pattern 不是查询资料库，而是**防线的证据链**。每个 fp 的生命周期：

```
发现错误 → 记录 fp（WHY/HOW）→ 提取稳定条件 → 转化为确定性防线（WHAT）
```

- **Rule（静态检测）** 回答 WHAT：什么代码形态报错
- **FP 文档** 回答 WHY：根因、实机排查过程、例外与局限——规则必须经 `knowledge_ref` 指回本文档，fp 不得因已自动化而删除

## 新增 fp 必须回答 4 个问题

1. 能否转化为静态规则（verifier / ui_lint / diagnostics）？
2. 能否进入模板/生成器约束（让错误根本无法生成）？
3. 能否进入 Build Gate（编译前拦截）？
4. 如果都不能，为什么？（写入 `not_automatable_because`）

## 必填 front-matter

```yaml
automation: rule | template | manual
#   rule     — 存在静态检测规则，static_rule 必填
#   template — 防线在模板/生成器约束（错误无法被生成），无检测规则
#   manual   — 无任何自动化防线，not_automatable_because 必填

static_rule: [ui_lint:ui_dialog_null_parent]   # automation=rule 时必填，格式 module:symbol
not_automatable_because: "..."                  # automation=manual 时必填
```

规则 ID 必须引用**真实存在的**符号（`ui_lint` 的 rule id、`verifier`/`diagnostics` 的方法名、`generator` 的熔断函数），禁止凭命名规律推断。

## 当前转化状态（2026-07-27 核实）

| fp | automation | 防线 |
|---|---|---|
| fp_catlistv_header_naming | rule | `verifier:_check_includes`（header_map 权威校验） |
| fp_dialog_cancel_not_desactivate | rule | `ui_lint:ui_dialog_cancel_empty` |
| fp_dialog_null_parent | rule | `ui_lint:ui_dialog_null_parent` |
| fp_imakefile_link | rule | `diagnostics:_check_link_with_coverage` |
| fp_missing_include | template | 模板默认 include |
| fp_paste_cross_doc_catpathelement | rule | `ui_lint:paste_explicit_targets`（跨文档 error / 同文档 warning） |
| fp_sethidestatus_crash | rule | `ui_lint:visu_sethidestatus`（warning，官方通路 `CATIVisProperties::SetPropertiesAtt`） |
| fp_template_feature_apis | rule | `generator:_gen_feature_spec` 熔断 + `verifier:_check_includes` |
| fp_toolbar_setaccesschild_overwrite | rule | `ui_lint:ui_toolbar_access_chain` |
| fp_undeclared_class | template | Component 模板内置 CATDeclareClass/CATImplementClass |
| fp_var_forward_decl | rule | `ui_lint:var_forward_decl` |
| fp_startup_interface_qi | manual | 见 `not_automatable_because`（接口挂在哪一层对象暂无静态数据，待建层级数据后升级 verifier 规则） |
| fp_runtime_resource_not_synced | manual | 同步动作已由 `build.py:sync_runtime_view` 自动执行；漏洞在绕过 build.py 的编译路径（手动 mkmk/VS），属流程行为，见 `not_automatable_because` |

**转化率：11/13（rule 9 + template 2 + manual 2）。**
