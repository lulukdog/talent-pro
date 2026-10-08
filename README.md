# talent-pro · 考核题库开发工具链

面向「高质量代码仓库采集 / 专家准入考核」场景的题目开发工具链。它把题库规范固化成
**可执行的检查规则**，把报告格式、里程碑划分、后续工作清单变成**可复现的命令输出**，
让出题、自测、提交三步都有据可依。

- 题目格式对齐 **Terminal-Bench** 数据格式，判卷框架对齐 **Harbor v0.5.0**
- 零第三方运行时依赖，仅需 Python 3.11+
- 自带示例题目 `examples/exam_001`（日志分析，Easy）

## 项目简介

出题人最容易踩的坑不是不会写题，而是「题面、判卷脚本、参考解三者对不上」：题面说输出到
`/output/report.txt`，判卷脚本却读别的路径；参考解写死了答案；判卷脚本要联网而镜像禁网。
这类问题在人工评审里极难发现，在自动判卷里却直接表现为 `reward = 0`。

`talentpro` 把这些问题变成 28 条题目级规则与 12 条仓库级规则，一条命令跑完：

```bash
uv run talentpro check examples/exam_001     # 题目级：结构 / 元数据 / 题面 / 一致性 / 报告契约 / 安全
uv run talentpro repo-check .                # 仓库级：功能子系统 / README 一致性 / 测试 / 敏感信息
```

## 主要能力

| 能力 | 命令 | 实现模块 |
| --- | --- | --- |
| 题目规范校验（28 条规则，6 个分类） | `talentpro check` | `talentpro.validators` |
| 仓库质量检查（12 条规则） | `talentpro repo-check` | `talentpro.validators.repo` |
| 访问日志统计与报告生成 | `talentpro report` | `talentpro.report` |
| 报告差异比对（判卷复现） | `talentpro compare` | `talentpro.report` |
| 新题目脚手架（含样例数据与判卷断言） | `talentpro scaffold` | `talentpro.scaffold` |
| 里程碑划分与质量自检 | `talentpro milestones` | `talentpro.milestone` |
| 后续工作清单生成 | `talentpro todos` | `talentpro.backlog` |
| 提交历史与提交说明质量 | `talentpro history` | `talentpro.gitlog` |

## 安装

需要 Python 3.11 或更高版本（使用 [uv](https://docs.astral.sh/uv/) 或 pip 均可）：

```bash
# 方式一：作为工具安装
uv tool install git+https://github.com/lulukdog/talent-pro

# 方式二：开发模式安装
git clone https://github.com/lulukdog/talent-pro
cd talent-pro
uv venv --python 3.12
uv pip install -e ".[dev]"
```

## 快速开始

```bash
# 1. 生成一道新题目（含样例日志、参考解与判卷断言）
uv run talentpro scaffold exam_002 --dest tasks/exam_002 --author zhaolu

# 2. 改动后跑规范校验；有 ERROR 会以退出码 1 结束，可直接用于 CI 门禁
uv run talentpro check tasks/exam_002
uv run talentpro check tasks/exam_002 --json | jq '.passed, .errors'

# 3. 只用某类规则（例如提交前的敏感信息扫描）
uv run talentpro check tasks/exam_002 --category security

# 4. 从日志复现标准报告，并与考生产出比对
uv run talentpro report tasks/exam_002/environment/access.log -o /tmp/report.txt
uv run talentpro compare /tmp/report.txt /tmp/actual.txt

# 5. 按提交历史划分里程碑，产出可直接粘贴到平台的标题与说明
uv run talentpro milestones . --out /tmp/MILESTONES.md

# 6. 生成至少 5 条后续工作（会优先吸收第 2 步发现的未通过项）
uv run talentpro todos tasks/exam_002
```

## 目录结构

```
talent-pro/
├── talentpro/                  # 主包
│   ├── models.py               # 检查结果、日志分析结果、差异项
│   ├── spec.py                 # 题目目录解析与数据模型
│   ├── report.py               # report.txt 生成 / 解析 / 比对
│   ├── gitlog.py               # 提交历史读取与提交说明质量
│   ├── milestone.py            # 里程碑划分与质量自检
│   ├── backlog.py              # 后续工作清单
│   ├── scaffold.py             # 题目脚手架与样例日志生成
│   ├── cli.py                  # 命令行入口
│   └── validators/             # 规则集
│       ├── base.py             # 注册 / 执行 / 结果聚合
│       ├── structure.py        # 必填文件、命名、canary
│       ├── metadata.py         # schema 版本、时限、资源、网络开关
│       ├── instruction.py      # 题面区块、长度、不泄露判卷细节
│       ├── consistency.py      # 题面↔判卷↔参考解↔镜像 路径一致性
│       ├── report_contract.py  # 输出格式样例与区块对齐
│       ├── security.py         # 密钥 / 内网地址 / 本机路径
│       └── repo.py             # 仓库级规则
├── examples/exam_001/          # 示例题目（完整 Harbor 任务）
├── tests/                      # 单元测试（覆盖规则、脚手架、CLI）
├── docs/                       # 题目规范、作业流程、架构说明
├── conftest.py                 # 让测试无需安装即可直接运行
└── pyproject.toml              # 打包与工具配置
```

## 命令行参考

| 子命令 | 说明 | 主要参数 |
| --- | --- | --- |
| `check` | 校验题目目录 | `--json` `--strict` `--category` `--rules` |
| `repo-check` | 仓库级质量检查 | `--json` `--strict` |
| `report` | 由访问日志生成标准报告 | `-o/--output` |
| `compare` | 比较两份报告 | `<expected> <actual>` |
| `scaffold` | 生成新题目目录 | `--dest` `--author` `--difficulty` `--log-lines` |
| `milestones` | 按提交历史划分里程碑 | `--json` `--out` `--max-per-milestone` |
| `todos` | 生成后续工作清单 | `--json` `--minimum` |
| `history` | 提交历史与说明质量 | `--json` |

返回码约定：`0` 通过，`1` 存在未通过项（`--strict` 时警告也算），`2` 输入或环境错误。

## 题目规范

完整的题目目录结构、`task.toml` 字段含义、判卷脚本约定与输出格式契约见
[docs/TASK_SPEC.md](docs/TASK_SPEC.md)；模块设计与规则扩展方式见
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)；平台六步作业（上传 → 准入 → Repo 质量 →
Milestone → Milestone 质量 → TODO）对应的自查清单与可粘贴内容见
[docs/PLATFORM_WORKFLOW.md](docs/PLATFORM_WORKFLOW.md)。

## 开发与测试

```bash
uv pip install -e ".[dev]"

ruff check .                   # 静态检查
pytest -q                      # 单元测试
talentpro repo-check .         # 自检：文档与代码是否一致
```

新增规则只需在 `talentpro/validators/` 下用 `@rule` 装饰器声明，规则函数返回
`RuleResult` 列表，注册与结果聚合由框架统一处理：

```python
@rule("structure.example", "示例规则", "structure")
def check_example(task: TaskSpec) -> list[RuleResult]:
    if (task.root / "something").exists():
        return []
    return [finding("structure.example", Severity.ERROR, "缺少 something")]
```

## 变更记录与许可

版本历史见 [CHANGELOG.md](CHANGELOG.md)，协作方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，
本项目基于 [MIT License](LICENSE) 开源。
