# CADE 知识库虚构 API 审计状态

> 本文件跟踪 `capabilities/`、`knowledge/`、`patterns/`、`playbooks/` 下每个手写文档的
> "虚构 API 排查"状态。目的：让下一次会话能立刻知道**哪些内容可以直接信任使用**，
> **哪些内容用之前必须先用检索工具复核**，不用重新翻 git log。

**最后更新**：2026-07-23
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

- `CATMsgCatalog::GetMessage` **不存在**（真实：`static BuildMessage(catalog, key, params, nb, default)`），曾于 dialog_dataflow.md/dialog_layout.md 出现，已修正

**工具已知局限**（非bug，使用时注意）：
- `--check-file` 只扫描 ` ```cpp ` 代码块，不扫描 frontmatter/正文反引号里提及的 API 名（例如某段说明文字里写"`CATIGSMConnectChecker` 这个类不存在"，这种否定性提及会被漏检，需要人工 `grep` 全文）
- 枚举成员值、类型常量会被误报 SUSPECT——这是已知局限，不代表真的有问题，需要人工用 `--query` 复核
- 自定义方法名、说明性文字里提及的虚构类名会被误报
- **判断头文件是否真实存在时，`find` 路径必须是 `<CATIA_INSTALL>/<Module>/PublicInterfaces/`，不要在 `<arch>/win_b64` 下找**（本次教训：`CATCreateWorkshop.h` 真实存在于 `ApplicationFrame/PublicInterfaces/`，曾因 find 路径误加 `win_b64` 被误判为不存在，导致两个 context_menu 文件被错删 include，已回滚）

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
| fta/ | fta_basics.md（`ec082a2` 完整重写）、**auto_annotate.md**（本批：虚构 `CATIHole`/`GetDiameter()`返回值/`GetDepth()` → 真实 `CATINewHole`/`GetDiameter(double&)`） |
| infrastructure/ | lifecycle_patterns.md、state_commands.md（`9ac0762`）、**selection.md**（本次会话完整重写：虚构 `CATISelection`/`SelectElement`/`CATVisProperties::SetHighlight`/`CATISO::ReframeOnObject` → 真实 `CATCSO`/`CATIVisProperties::SetPropertiesAtt`/`CAT3DViewer::ReframeOn`，geom type 用 `CATVPAsm`）、**code_style.md**（本批干净）、**error_handling.md**（本批：`CATUnicodeString::FromInt`→`BuildFromNum`）、**imakefile_advanced.md**（本批：库名 `CATMecMod`→`CATMecModInterfaces`、`CATTopology`→`CATTopologicalOperators`、`CATSysMultiCAA`→`CATSysFile`、`CATBatchInfra`→`CATBatchUtils`，均经 win_b64 .dll 核实）、**memory_management.md**（本批：虚构 `RemoveAllElementaryFilters`→真实 `SetFilter(NULL)`）、**naming_conventions.md**（本批干净） |
| part/ | chamfer.md、fillet.md、hole.md（`9ac0762`） |
| mecmod/ | **feature_patterns.md**（本次会话完整重写：虚构 `CATImplementStartUp`/`CATFeatureStartUp`/`CATAttribute`/`CATNull` 宏与 `CreateFeature` → 真实 `CATOsmSUHandler::Instanciate` 目录机制 + `CATImplementClass(X, DataExtension, CATBaseUnknown, LateType)`）、**feature.md**（本批：`GetChildren` 属 `CATINavigateObject` 非 `CATISpecObject`、`GetParent`→`GetFather`、`IsATypeOf`→`IsSubTypeOf`、Body 获取走 `CATIMfBRep`）、**topology.md**（本批大改：虚构 `CATBody::GetAllCells`/`CATFace::GetArea`/`GetNormal`/`CATEdge::GetLength` → 真实 `GetCellsHighestDimension`/`CalcArea`/`EvalNormal`/`CalcLength`/`GetVertices(CATVertex**)`/`GetPoint`） |
| philosophy/ | late_types.md、reference_vs_instance.md、updates.md（`679eecf`）、**caterror.md**（本批：`CATIMechanicalUpdate_var`→`CATISpecObject_var`）、**com_lifecycle.md**（本批干净）、**undo_redo.md**（本批：虚构 `CATIUndoRedoCommand`/`Undo()`/`Redo()` → 真实 `CATCommandGlobalUndo`/`BeforeUndo`/`BeforeRedo`/`AfterUndo`/`AfterRedo`；属性写走 `CATISpecAttrAccess::SetDouble`） |
| surface/ | **surface_basics.md**（本次会话完整重写：虚构 `CreateJoin`/`CATIGSMJoin`/`CATIGSMConnectChecker`/`CATBody::GetSurfaceArea`/`CATBooleanTrue` → 真实 `CreateAssemble`/`CATIMeasurableSurface::GetArea`/TRUE/FALSE；长度参数必须 `CATICkeParmFactory::CreateLength`） |
| product/ | assembly.md（`ce25c0a`） |
| ui/ | **dialog.md**（本次会话完整重写：虚构 `CATDlgList` → 真实 `CATDlgSelectorList`/`CATDlgTableView`；统一构造签名 `(parent,name,style)`，文本走 NLS/`SetTitle`）、**dialog_layout.md**（本次会话重写：修正 2参`SetGridConstraints`/链式`SetRow`/等虚构链式调用、`CATGRID_HORIZONTAL`/`CATDlgFraGroupFrame`/`AttachTab`/`CATDlgProgressBar`/`CATDlgMultiEditor`/`AddItem`/`SetStep`/`CATDlgNotification`/`CATDlgLstMultipleSelection`/`CATDlgFileOpen`/`CenterOnScreen`/`DoEvents` 等 16 项虚构 → 全部替换为 B28 头文件实证 API）、**workbench_patterns.md**（本次会话完整重写：虚构 CATIGenericWksAddin/CATCmdMenu/AddCommand → 真实 CATIAfrGeneralWksAddin + MacDeclareHeader + NewAccess 宏链）、**layout_advanced.md**（本次会话修正存量虚构：`CATDlgTree`/`CATDlgTreeItem` 不存在、2 参 `SetGridConstraints`、`CATDlgSplitterVertical`/`AttachLeft`/`SetMinimumSize`/`SetCurrentTab` → 真实 SelectorList 缩进模拟 + TabContainer + `SetSelectedPage`/`SetSashPosition`）、**context_menu.md**（本批干净：`CATExtIContextualMenu`/`NewAccess`/`SetAccessCommand` 链与 `CATCreateWorkshop.h`（真实存在于 `ApplicationFrame/PublicInterfaces`）均核实无误）、**toolbar.md**（`CATCreateWorkshop.h` 真实存在，核实无误） |
| failure_patterns/ | fp_dialog_cancel_not_desactivate.md、fp_dialog_null_parent.md（`9ac0762`）、**fp_imakefile_link.md**（本批干净）、**fp_missing_include.md**（本批：虚构 `CATIMechanicalUpdate`→真实 `CATIUpdateError`）、**fp_toolbar_setaccesschild_overwrite.md**（本批干净，官方样例 CAAAfrGeometryWks.cpp 佐证）、**fp_undeclared_class.md**（本批干净，宏族均真实） |
| drawing/ | drawing_basics.md、drawing_annotations.md（本次会话完整重写，修正虚构 `CATIDrw*` 体系为真实 `CATIDft*`，详情见各文件开头的"⚠️ 重要修正"章节与 `playbooks/pb_batch_drawing.md`） |

### patterns/（已核实部分）

- `surface/surface_analysis.md`（联动 `pb_surface_analysis.md` 核实）
- `ui/wizard.md`（`49a26e7` 完整重写，修正 `IsOutputSetCondition` 类型不匹配的深层机制错误）
- `ui/dynamic_form.md`（`9ac0762` 小幅修正 `CATFeatureImportAgent` 误用）
- `drawing/batch_drawing.md`（本次会话完整重写，修正 `CATIDrwSheet`→`CATIDftSheet`、`CATIProgressCallback`（不存在）→真实的 `CATIProgressTask`/`CATIProgressTaskUI`（`ApplicationFrame` 框架））
- `workflow/batch_process.md`（本次会话完整重写：虚构 `CATSessionServices`/`CATIProgressBar`/`GetActiveDocument`/`GetPartContainer` → 真实 `CATFrmEditor::GetDocument` + `CATIContainerOfDocument::GetSpecContainer` + `CATIProgressTask`/`CATIProgressTaskUI`）
- `blocks/locator.md`（本次会话完整重写：虚构 `GetSelection`/`SelectElement`/`ReframeOnObject`/`CATVisProperties::SetHighlight` → 真实 `CATCSO`/`CATIVisProperties::SetPropertiesAtt`/`ResetPropertiesAtt`/`CAT3DViewer::ReframeOn`）
- `ui/result_dialog.md`（本次会话完整重写：虚构 `CATDlgList` 多列签名/`SelectElement` → 真实 `CATDlgSelectorList`/`CATDlgTableView` + `CATCSO`）
- `ui/master_detail.md`（本次会话完整重写：虚构 `CATDlgSunkenFrame`/`CATDlgGroupFrame`/`CATDlgLstSingleSelection` → 真实 `CATDlgFraNoTitle`/`SetTitle`/`CATDlgLstMultisel`）
- `analyzer/geometry_analyzer.md`（本批：`GetChildren`→`ListComponents`、`IsATypeOf`→`IsSubTypeOf`、`SelectElement`→`CATISO::AddElement`、定位改用 `CAT3DViewer::ReframeOn`、`CATIHole`→`CATINewHole`）
- `analyzer/rule_checker.md`（本批：`IsATypeOf`→`IsSubTypeOf`；虚构 `CATIFillet::GetRadius` → 真实 `CATIEdgeFillet::GetRadius`）
- `blocks/feature_visitor.md`（本批：`GetChildren`→`ListComponents`、`IsATypeOf`→`IsSubTypeOf`）
- `fta/auto_annotate.md`（本批：`CATIHole`→`CATINewHole`、`GetDiameter(double&)` 引用传参、删除不存在的 `GetDepth()`）
- `ui/context_menu.md`（本批干净：`CATCreateWorkshop.h` 真实存在于 `ApplicationFrame/PublicInterfaces`，`NewAccess`/`SetAccessCommand` 宏链核实无误）

### frameworks/（148个自动生成索引文件，不适用本审计）

这些是脚本从 CAADoc 自动抽取的 API 签名索引（`knowledge/frameworks/*.md`），不是手写教学文档，本身即是索引数据，不存在"虚构 API"问题，无需人工核实。

---

## 未核实清单

> ✅ **手写文档校核已全部完成。** `capabilities/`（13）、`playbooks/`（14）、`knowledge/`、`patterns/` 下所有手写教学文档均已核实完毕，无剩余未核实项。
>
> 仅剩 `knowledge/frameworks/` 148 个文件为脚本自动生成的 API 索引（非手写教学代码），不适用本审计。

---

## 下次会话继续入口

知识库手写文档虚构 API 校核已**全部完成**（capabilities 13 + playbooks 14 + knowledge 全部 + patterns 全部）。无待办文件。

后续如需复查个别 API：
1. 跑 `python tools/build_caadoc_index.py --query <TypeName>` 或 `--check-file <path>` 快速核对
2. 对 SUSPECT 结果，先排除已知误报源（宏/枚举值/库名/头文件名/教学占位符），再用 SDK 头文件或 win_b64 `.dll` 复核
3. 判断头文件存在性用 `find <CATIA_INSTALL>/<Module>/PublicInterfaces/ -name X.h`，勿在 `win_b64` 下找
4. 改知识库长 markdown 用 `write_file` 整体重写，勿用 `edit_file` 局部编辑（历史上多次截断/错位）
5. 改完跑 `python tests/test_master.py --quick`（应 38/38 全过）

---

## 生产使用建议（给 AI/开发者的即时参考）

- **可直接信任**：`capabilities/` 全部13个、`playbooks/` 全部14个、`knowledge/` 与 `patterns/` 全部手写教学文档（均已核实，含 drawing/surface/mecmod/infrastructure/philosophy/failure_patterns/ui 各子目录）。
- **frameworks/ 148个文件**：这是自动生成的 API 索引数据（非教学代码），可作为**查找线索**（定位属于哪个框架）放心使用，但具体方法签名仍以 `--query` 实时核对头文件为准（索引文件本身也会标注 SDK/refman mismatch）。
