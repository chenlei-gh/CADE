# CADE 实验性知识候选区 (Experimental Candidates)

> **安全与防污染规范**：
> 本目录用于存放 CADE `ChainExplorer` 自动从 Dassault 官方例程中提取、提炼的候选调用链草稿（`CANDIDATE_*.md`）。
> 
> - **严格隔离**：本目录下的所有文件**严禁**被索引进官方知识目录 `catalog/index.yaml`。
> - **未经验证不可作为绝对事实**：虽然每个接口、方法所有者、头文件和库依赖均通过本地索引严格核验，但业务逻辑依然需要经过真实 CATIA 编译与运行时功能测试。
> - **晋级门禁 (Promotion Gate)**：只有满足以下条件，经人工审查后方可晋级为正式 Playbook：
>   1. 真实工作区通过 `build.py` 编译零错误；
>   2. 真实 CATIA 运行时功能验收通过；
>   3. 编写回归用例确认无副作用。
>
> **完整调用链提升当前是关闭的**（阶段性设计，不是漏洞）：
> `ChainExplorer` 现在只会写出 `index_consistency=root_matched_metadata_unverified`
> 或 `unknown`。Kernel 只接受 `consistent` 才会把结果标成 `official_usecase_chain`。
> 没有生产代码会写出 `consistent`，所以真实探索一律停在
> `official_usecase_fragment`（`fragment_only=true`）。
> 根路径匹配不等于索引元数据已与源码核对。在补上这一步之前，
> 不要把片段当成可执行调用链，也不要为了重新提升而手工填 `consistent`。
