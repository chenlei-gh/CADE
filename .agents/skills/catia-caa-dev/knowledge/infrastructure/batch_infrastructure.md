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
| 文档级操作（`Documents.Add` / `Open`） | ✅ 可用（B28 实测） | ❌ `0x80004005`（会话建不起来） |
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
- **走 mkrun 完整 TCK 环境启动 CATBatch** → 不影响，结果完全一致

### 对照实验结论：CNEXT 能建会话，CATBatch 不能

同一台机器、同一时间、同一份 Runtime View，用同一条 mkrun 链路分别跑：

| 启动方式 | `Documents.Add("Part")` | `Documents.Open(...CATPart)` |
|---|---|---|
| `mkrun -c "CNEXT -batch -macro x.CATScript"` | 成功 | 成功 |
| `mkrun -c "CATBatch <param.xml>"` | `0x80004005` | `0x80004005` |

两个结论：

1. **安装、授权、Runtime View 都是好的**。CNEXT 能正常新建并打开 CATPart，
   说明 `0x80004005` 不是“安装缺资源”也不是“没有许可证”。
2. **差别在启动器本身**。CATBatch 以托管模式自己管会话生命周期，
   它没把会话建成，`batchmain` 里再调 `Create_Session` 也补不回来。

因此在 CATBatch 里做文档级操作的**前置条件尚未满足**，
这不是调用方式或环境变量能修的，也不在 CADE 能覆盖的范围内。
需要文档级批量处理时，优先用 `run_catia --batch` / `run --macro`
（CNEXT 脚本路径，实测可用）。

### 为什么 `run --macro` / `run --batch` 曾经静默无效

`mkrun` 有它自己的 argv，`-macro` / `-batch` 是 **CNEXT** 的开关。
把它们直接拼在 `mkrun` 后面，mkrun 会报
`mkrunM: illegal option -- 'batch'` 并以 RC=1 退出，CNEXT 根本不会启动；
而调用方拿到的是启动脚本的退出码，于是表现为「返回 0、什么也没发生」。
正确形式是 `mkrun -c "CNEXT <开关>"`。已修。

### 硬限制：`mkrun -c` 的实参不能含空格

`mkrun` 对 `-c` 的值**不做 CRT 命令行解析**，而是按空格简单切分后再拉起 CNEXT。
B28 实测三种写法全部失败，参数都在第一个空格处被截断
（`C:\temp\space dir\...` → `Cannot open library C:\temp\space.dll`）：

| 写法 | 结果 |
|---|---|
| 裸路径 `mkrun -c "CATBatch C:\temp\space dir\x.xml"` | ❌ 截断 |
| 嵌套双引号 `mkrun -c "CATBatch "C:\temp\space dir\x.xml""` | ❌ 截断 |
| 反斜杠转义 `mkrun -c "CATBatch \"C:\temp\space dir\x.xml\""` | ❌ 截断 |

推断（未反汇编验证）：mkrun 先按空格切分载荷，转义在任何阶段都没机会生效。

因此 **workspace 模式（mkrun 链路）要求宏/参数文件路径不含空格**。
CADE 对此 fail-fast：`_mkrun_payload_error()` 前置校验，命中时
`run_catia_macro` / `run_catia_batch` 返回 `status: error` 并提示两条出路
（移到无空格路径；或去掉 workspace 走 CATSTART，代价是不加载自定义 DLL），
不会生成注定失败的启动脚本。

注意 CATIA 自身装在 `C:\Program Files\...` 不影响：安装路径只进
`tck_init.bat` / `mkinit.bat` 的 `call` 行，不进 `-c` 载荷。

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
