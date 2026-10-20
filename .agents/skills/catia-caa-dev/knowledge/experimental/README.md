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
