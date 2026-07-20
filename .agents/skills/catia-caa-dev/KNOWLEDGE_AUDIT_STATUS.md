# CADE 知识库虚构 API 审计状态

> 本文件跟踪 `capabilities/`、`knowledge/`、`patterns/`、`playbooks/` 下每个手写文档的
> "虚构 API 排查"状态。目的：让下一次会话能立刻知道**哪些内容可以直接信任使用**，
> **哪些内容用之前必须先用检索工具复核**，不用重新翻 git log。

**最后更新**：2026-07-20
**更新方式**：`git log --oneline --all -- <path>` + `grep "重要修正|已核实"` 交叉核对所有 commit 历史得出。

---

## 核实方法论（下次继续排查时复用）

四类数据源权威性排序（冲突时优先信前者）：

1. **发布产品字典** `<CATIA_INSTALL>/<arch>/code/dictionary/*.dic`（ground truth，约885文件/7.3万条，记录组件真实实现了哪些接口）
2. **SDK 头文件** `<CATIA_INSTALL>/.../PublicInterfaces/*.h`（refman 的生成源，比 htm 页面更权威）
3. **CAADoc refman htm** `<CATIA_INSTALL>/CAADoc/Doc/generated/refman/`
4. **CAADoc `.dico` 教学样例**（44个，仅供参考，可能过时或简化）
5. **官方示例工程源码全文**（`<CATIA_INSTALL>/CAADoc/CAA*.edu/**/*.cpp`，用 `grep -rl` 搜索验证 API 真实调用惯用法——工具查不到"怎么组合调用"时用这个）

排查工具（在 `.agents/skills/catia-caa-dev/` 目录下运行）：

```sh
python tools/build_caadoc_index.py --check-file <path/to/file.md>   # 批量扫描文件```cpp代码块里的CAT*类型名和方法调用，只打印疑点，优先用这个
python tools/build_caadoc_index.py --query <TypeName> --quiet         # 一行式verdict：FOUND/NOT-FOUND/MISMATCH
python tools/build_caadoc_index.py --query <TypeName>                 # 完整查询：方法列表+SDK头文件交叉比对+枚举值+ground truth实现组件
python tools/build_caadoc_index.py --search <pattern>                 # 全字段子串搜索（类型名/方法签名/.dico条目/枚举值）
python tools/build_caadoc_index.py --repl                             # 交互模式，连续核对多个名字不用反复启动进程
```

**工具已知局限**（非bug，使用时注意）：
- `--check-file` 只扫描 ` ```cpp ` 代码块，不扫描 frontmatter/正文反引号里提及的 API 名（例如某段说明文字里写"`CATIGSMConnectChecker` 这个类不存在"，这种否定性提及会被漏检，需要人工 `grep` 全文）
- 枚举成员值、类型常量会被误报 SUSPECT——这是已知局限，不代表真的有问题，需要人工用 `--query` 复核
- 自定义方法名、说明性文字里提及的虚构类名会被误报

---

## 已核实清单（可直接信任使用）

### capabilities/（13个，**全部已核实**✅）

annotation.md · assembly-tree.md · document-export.md · feature-recognition.md ·
geometry-query.md · parameter-system.md · persistence.md · powercopy.md ·
selection.md · surface-operations.md · undo-redo.md · update-mechanism.md · visualization.md

### playbooks/（14个，**全部已核实**✅，除 README.md）

assembly_constraint_check · assembly_stats · auto_annotate_3d · auto_color ·
batch_drawing · batch_feature_check · batch_update_save · create_context_menu ·
custom_viewer · dialog_wizard · export_bom · geometry_quality_check ·
parameter_editor · surface_analysis

（对应 commit：`321604d` `ff8b596` `c23e661` `3d2d289` `e585c5e` `39d97d6` `49a26e7` `e39e3cc`）

### knowledge/（已核实部分）

| 子目录 | 已核实文件 |
|---|---|
| fta/ | fta_basics.md（`ec082a2` 完整重写） |
| infrastructure/ | lifecycle_patterns.md、state_commands.md（`9ac0762`） |
| part/ | chamfer.md、fillet.md、hole.md（`9ac0762`） |
| philosophy/ | late_types.md、reference_vs_instance.md、updates.md（`679eecf`） |
| product/ | assembly.md（`ce25c0a`） |
| ui/ | dialog_dataflow.md、dialog_patterns.md、event_patterns.md（`9ac0762`+`49a26e7`）、layout_advanced.md、layout_anti_patterns.md（`9ac0762`）、toolbar.md（`af81e50`，官方MacDeclareHeader核实但未标"重要修正"，风险低） |
| failure_patterns/ | fp_dialog_cancel_not_desactivate.md、fp_dialog_null_parent.md（`9ac0762`） |
| drawing/ | drawing_basics.md、drawing_annotations.md（本次会话完整重写，修正虚构 `CATIDrw*` 体系为真实 `CATIDft*`，详情见各文件开头的"⚠️ 重要修正"章节与 `playbooks/pb_batch_drawing.md`） |

### patterns/（已核实部分）

- `surface/surface_analysis.md`（联动 `pb_surface_analysis.md` 核实）
- `ui/wizard.md`（`49a26e7` 完整重写，修正 `IsOutputSetCondition` 类型不匹配的深层机制错误）
- `ui/dynamic_form.md`（`9ac0762` 小幅修正 `CATFeatureImportAgent` 误用）
- `drawing/batch_drawing.md`（本次会话完整重写，修正 `CATIDrwSheet`→`CATIDftSheet`、`CATIProgressCallback`（不存在）→真实的 `CATIProgressTask`/`CATIProgressTaskUI`（`ApplicationFrame` 框架））

### frameworks/（148个自动生成索引文件，不适用本审计）

这些是脚本从 CAADoc 自动抽取的 API 签名索引（`knowledge/frameworks/*.md`），不是手写教学文档，本身即是索引数据，不存在"虚构 API"问题，无需人工核实。

---

## 未核实清单（使用前建议先用 `--query`/`--check-file` 复核）

> 🔴 高风险组（`knowledge/drawing/drawing_basics.md`、`knowledge/drawing/drawing_annotations.md`、`patterns/drawing/batch_drawing.md`）已在本次会话全部核实并重写完成，已移入上方"已核实清单"，不再列于此。

### 🟡 中风险（patterns/ 目录，大量未核实的手写代码示例）

- `patterns/analyzer/geometry_analyzer.md`
- `patterns/analyzer/rule_checker.md`
- `patterns/blocks/feature_visitor.md`
- `patterns/blocks/locator.md`
- `patterns/fta/auto_annotate.md`
- `patterns/ui/context_menu.md`
- `patterns/ui/master_detail.md`
- `patterns/ui/result_dialog.md`
- `patterns/workflow/batch_process.md`

### 🟡 中风险（knowledge/ 目录剩余未核实文件）

| 子目录 | 未核实文件 |
|---|---|
| failure_patterns/ | fp_imakefile_link.md、fp_missing_include.md、fp_toolbar_setaccesschild_overwrite.md、fp_undeclared_class.md |
| infrastructure/ | code_style.md、error_handling.md、imakefile_advanced.md、memory_management.md、naming_conventions.md、selection.md |
| mecmod/ | feature.md、feature_patterns.md、topology.md |
| philosophy/ | caterror.md、com_lifecycle.md、undo_redo.md |
| surface/ | surface_basics.md |
| ui/ | context_menu.md、dialog.md、dialog_layout.md、workbench_patterns.md |

---

## 下次会话继续入口

1. 🔴 高风险组（drawing 相关3文件）已在本次会话全部处理完毕。下次可从"🟡 中风险"列表挑选下一批。建议优先顺序：`patterns/` 目录下9个手写代码示例文件（启用频率高）→ `knowledge/mecmod/`（核心建模概念，使用频率高）→ 其余
2. 对每个文件跑 `python tools/build_caadoc_index.py --check-file <path>`，把输出的 SUSPECT 逐条用 `--query`/`.edu` 样例源码交叉验证
3. 确认虚构点后，用 `write_file` 整体重写受影响段落（**不要用 `edit_file` 对含大量代码块的长 markdown 做局部编辑**——历史上多次在 `pb_parameter_editor.md`、`patterns/ui/wizard.md` 上造成截断/内容错位，即使工具返回"successfully"也不可信，写完必须 `read_file` 验证结构完整）
4. 修完一批文件后，在本文件对应清单里把文件从"未核实"移到"已核实"，并记录 commit hash
5. 跑一次 `python tests/test_master.py --quick`（应 38/38 全过）确认没有破坏现有测试

---

## 生产使用建议（给 AI/开发者的即时参考）

- **可直接信任**：`capabilities/` 全部13个、`playbooks/` 全部14个、上表列出的 `knowledge/` 已核实文件（包含 `knowledge/drawing/` 全部2个）、`patterns/surface/surface_analysis.md`、`patterns/ui/wizard.md`、`patterns/ui/dynamic_form.md`、`patterns/drawing/batch_drawing.md`。
- **谨慎使用**：`patterns/` 目录其余9个文件、`knowledge/failure_patterns/`（除2个已核实）、`knowledge/infrastructure/`（除2个已核实）、`knowledge/mecmod/`、`knowledge/philosophy/`（除3个已核实）、`knowledge/surface/surface_basics.md`、`knowledge/ui/`（除已核实的6个）。AI 生成代码涉及这些区域的具体 API 调用时，应先用 `--query`/`--check-file` 核实关键类型和方法名，不要直接照抄示例代码。
- **frameworks/ 148个文件**：这是自动生成的 API 索引数据（非教学代码），可作为**查找线索**（定位属于哪个框架）放心使用，但具体方法签名仍以 `--query` 实时核对头文件为准（索引文件本身也会标注 SDK/refman mismatch）。