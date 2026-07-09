# 使用规范

## docs/

| 子目录 | 用途 | 存放内容 |
|--------|------|---------|
| `API/` | API 参考 | 接口文档、类图、调用示例 |
| `Design/` | 设计说明 | 架构图、流程图、技术决策 |
| `Images/` | 图片资源 | 截图、架构图、UI 预览 |

**规则**：
- 不放 Obsidian 知识库内容
- 所有文档面向开发者（clone 项目的人）
- 图片用 PNG，不用 PSD/AI 源文件

## examples/

| 用途 | 存放内容 |
|------|---------|
| 测试数据 | 示例 CATPart、CATProduct、CATDrawing |
| 输入文件 | BOM 表模板、命名规则配置 |

**规则**：
- 二进制文件用 Git LFS 或 `.gitignore` + 网盘链接
- 必须包含 README.md 说明每个示例的用途

## scripts/

| 脚本 | 用途 |
|------|------|
| `build.py` | 增量编译 (`mkmk -u`) |
| `clean.py` | 清理编译 (`mkmk -c`) |
| `full_build.py` | 全量编译 (`mkmk -a`) |
| `package.py` | 打包为可部署文件 |
| `install.py` | 安装到目标 CATIA |
| `run_test.py` | 启动 CATIA 运行 FunctionTests |

**规则**：
- 脚本可独立运行，不依赖 CADE
- 每个脚本有 `--help` 或 `--dry-run`
