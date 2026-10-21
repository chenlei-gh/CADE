---
id: infra.batch_infrastructure
title: CAA Batch Infrastructure (CATBatch)
category: knowledge
domain: infrastructure
keywords: [batch, CATBatch, batchmain, descriptor, batchdesc, parameter file, ParamOfficial.xml, AFWIN, BATCH_PATH]
apis: []
requires: []
patterns: []
examples: []
release: [R19, R28]
tags: [infrastructure, batch, runtime]
---

# CAA Batch Infrastructure

## 两套机制，不要混

CAA 里「批量跑东西」有两条完全不同的路，入口符号、输入、启动器都不同。
把两者混用是本域最常见的静默失败来源。

| | 脚本批处理 | 编译型 CAA Batch |
|---|---|---|
| 启动器 | `CNEXT -batch -macro <脚本>` | `CATBatch.exe <参数XML>` |
| 执行物 | CATScript / VBA 脚本 | 已编译 DLL 的导出函数 |
| 入口符号 | `CATMain` | `batchmain` |
| 需要描述符 | 否 | 是（`CNext/resources/batchdesc/*.xml`） |
| CADE 能力 | `run_catia --batch` | `run_caa_batch` |

官方原文（`CAADoc/Doc/online/CAAScdInfTechArticles/CAAInfInvoking.htm`）：

> You can start CATIA in batch to execute **a macro** using the `-batch`
> option followed by the full path of **the macro** you want to run.

官方原文（`CAABatUseCases/CAABatBatchSample.htm`）：

> A V5 batch … The code is implemented in **a library**, by the
> **`batchmain`** function. The batch is described in **a XML file** known
> as "file descriptor".

**判据**：`dumpbin /exports` 看导出表。只有 `batchmain` 没有 `CATMain`
= 编译型 Batch，必须走 `CATBatch.exe`。`CNEXT -batch -macro` 喂它不会报错，
只是什么也不发生。

## 三个文件

### 1. Batch 描述符（descriptor）

必须放在 `<Framework>/CNext/resources/batchdesc/`，由 batch 作者编写一次。

```xml
<?xml version='1.0' encoding='UTF-8' standalone='no' ?>
<!DOCTYPE batch SYSTEM "BatchDescriptor.dtd">

<batch name="S0Probe"
       description="Skin flatten probe"
       language="C++"
       commandline="CATBatch CAASkinFlattenS0Probe" />
```

- `name` 是查找键，必须与参数 XML 的 `batch_name` **完全一致**
- `commandline` 形如 `CATBatch <库名>`，`<库名>` 是含 `batchmain` 的 DLL
- 文件名必须叫 `<name>.xml`

### 2. 参数文件（parameter file）

由调用者提供，格式由 batch 作者按 `Parameters.dtd` 决定：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE root SYSTEM "Parameters.dtd" >
<root batch_name="S0Probe" >
  <inputParameters>
    <file id="part" filePath="C:/path/to/Input.CATPart" type="bin"/>
    <folder id="out" folderPath="C:/path/out" type="bin" extension="CATPart"/>
    <simple_arg id="stage" value="2"/>
  </inputParameters>
  <outputParameters>
    <folder id="out_dir" folderPath="C:/path/out" type="bin" extension="CATPart"/>
  </outputParameters>
</root>
```

`id` 必须与 `batchmain` 里 `ReadParam(inputs, "<id>")` 的字符串一一对应。
写错 id 不报错，只是取到空值。

### 3. 入口函数

```cpp
extern "C" int batchmain(int argc, char** argv)
{
    CATBatchUtils::CATBatchInput  inputs;
    CATBatchUtils::CATBatchOutput outputs;
    // ...
    return 0;
}
```

通过 `TIE_CAA_BATCHMAIN` 或模块导出表暴露，**不是** `CATMain`。

## 描述符查找顺序（实测修正）

`CATBatch` 在 `CATInstallPath` 的**每个**条目下找
`<root>/resources/batchdesc/<batch_name>.xml`。`CATInstallPath` 接受 `;` 分隔的
路径列表，和 `CATDLLPath` 一样。

**`BATCH_PATH` 不是描述符查找根。** 早先根据 `CATBatchUtils.dll` 里的
`BATCH_PATH=%s%c%resources%c%batchdesc%c` 字面串推断它是查找根，实测否定：
无论 `BATCH_PATH` 设成 `win_b64`、`win_b64/resources`、
`win_b64/resources/batchdesc` 还是不设，运行时行为完全一致。

实测矩阵（B28，`batch_name=S0Probe`，描述符只存在于 Runtime View）：

| `CATInstallPath` | 结果 |
|---|---|
| `B28\win_b64`（只有安装） | `CATBatchInit failed`，RC=2，**`batchmain` 从未被调用** |
| `D:\...\win_b64;B28\win_b64` | 描述符命中，`batchmain` 被调用 |
| Runtime View 目录里删掉描述符 | 立刻退回 RC=2 |

所以 **Runtime View 必须进 `CATInstallPath`**，否则工作区描述符永远不可见，
失败发生在 `CATBatchInit` 阶段、日志里只有一行 `CATBatchInit failed`，
极易被误读成「DLL 或描述符写错了」。CADE 的 `env.py` 已把 Runtime View
放在 `CATInstallPath` 首位（同名时工作区描述符遮蔽官方描述符）。

## 失败模式

### RC=2 + 日志只有一行 `CATBatchInit failed`

**根因**：描述符没找到，失败发生在 `batchmain` 之前。最常见原因是
`CATInstallPath` 只有安装目录、没有 Runtime View（见上节）。
`CATBatchUtils.dll` 把这一阶段细分成
`CATCreateInstance failed` / `QI on CATIBatch failed` /
`put_ParametersPath failed` / `put_BatchDescriptorPathFromParam failed`，
但 `LOG.txt` 只落一行概括，不写细分原因。

**判据**：`LOG.xml` 里没有 `Entry point <batchmain> found`。
有它就是过了初始化、问题在别处。

### `CATBatchInit failed` 消失、改成 `batchmain` 内的错误

初始化过了，失败在用户代码，别再改环境变量。

### AFWIN 弹窗 + `Entry point <batchmain> not found`

**根因**：参数文件的 `batch_name` 与工作区描述符不匹配，查找回落到官方
`batchdesc/` 中同名文件，于是 CATBatch 去加载一个你根本没写过的 DLL。

实测案例：参数 XML 写 `batch_name="BatchSample"`，命中官方
`BatchSample.xml`（`commandline="CATBatch CAABatBatchSample"`），而
`CAABatBatchSample.dll` 在全盘不存在 → 报 `batchmain not found`。
真正的错误在参数文件，不在 DLL。

**预防**：CADE 的 `run_caa_batch` 在启动前检查描述符、库、`batchmain` 导出、
输入文件四件事，不需要靠弹窗和翻日志定位。

### 参数全对但 `OpenDocument returned NULL`

日志形如：

```
CATDocumentServices::New(CATPart)      : 0x80004005
CATDocumentServices::OpenDocument      : 0x80004005
FATAL : OpenDocument returned NULL document
```

`batchmain` 已进入、参数已读到，但 CATIA 文档模型整体未起。

日志开头通常还伴随：

```
GetPtrSession (existing session)  : 0x80004005
existing session available        : 0
Create_Session                    : 0x80004005
CATInstantiateComponent(CATFeatCont, IID_CATIGSOFactory) : 0x80004002
GSO factory available             : 0
```

即 **CATIA 会话根本没创建成功**，后续所有文档 API 必然连带失败。
这已经越过 CADE 的控制边界：CATBatch 托管进程的生命周期由它自己管，
`batchmain` 里显式调 `Create_Session` 也补不回来。

已排除的假设（实测）：

- `CATInstallPath` 用符号链接拼的精简安装 → 不影响，`batchmain` 照常进入
- 描述符缺 `NeedsVisu` / `catutil` 属性 → 不影响
- `NOLICENSECHECK` 环境变量 → 不影响

因此 `0x80004005` 会话层的根因**尚未定位**，不要凭症状去改 `env.py`。
若需要文档级操作，先确认同机器上 `run_catia`（CNEXT 图形会话）能正常开会话，
再用它做对照隔离。

### 环境变量漂移

手工写 `run_*.bat` 时，`CATInstallPath` / `CATDLLPath` / `CATDictionaryPath`
容易各自写成不同取值，出现「同一概念三种值」。应由 CADE 统一注入，
不要人肉维护多份 bat。

## 日志位置

CATBatch 把运行日志写到 `%TEMP%/<32位十六进制>/`：

- `<uuid>LOG.txt` — 文本日志，失败原因的原始出处
- `<uuid>LOG.xml` — 结构化日志
- `<uuid>OUTPUT.xml` — 输出参数

失败时**先看这里**，不要依赖退出码或控制台输出 —— CATBatch 常常
只弹窗、不打印。
