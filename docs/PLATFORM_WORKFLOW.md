# 平台作业流程对齐

本文件把平台的六步作业（上传仓库 → 准入检查 → Repo 质量 → Milestone → Milestone 质量 →
下一步 TODO）映射到本仓库可执行的命令，并给出可直接粘贴的表单内容。

## 0. 提交前确认

| 平台要求 | 自查方式 |
| --- | --- |
| 仓库包含连续、真实的开发过程 | `talentpro history .`：查看提交数、时间跨度、提交说明质量分 |
| 提交说明可读、可追溯 | `talentpro history .` 的「含糊主题」应为 0 |
| 已清理密钥、令牌、客户数据、内部地址 | `talentpro check <task> --category security`；仓库级用 `talentpro repo-check .` |
| README 与代码一致 | `talentpro repo-check .` 中的 `repo.readme_code_consistency` |

## 1. 上传仓库

- 平台会拉取指定分支的代码与提交历史；本次作业只检查上传成功时的版本。
- 上传前先确认分支上的内容就是交付版本：`git status`、`git log --oneline`。
- 重新上传会清空已有质检结果与 Milestone，因此先把内容定稿再上传。

## 2. 准入检查（提交数量 / 代码规模 / 可解析率 / README 完整性）

```bash
talentpro repo-check .                 # 0 error 才继续
python -c "import talentpro"           # 可导入
python -m compileall -q talentpro      # 可解析率
```

对照项：

| 平台指标 | 本仓库对应实现 |
| --- | --- |
| 提交数量 | `talentpro history .` → `提交总数` |
| 代码规模 | `talentpro repo-check .` → `repo.subsystems`（主包模块数） |
| 可解析率 | 全部 `.py` 通过 `python -m compileall talentpro` |
| README 完整性 | `talentpro repo-check .` → `repo.readme` 与 `repo.readme_sections` |

## 3. Repo 质量检查（功能子系统 / README 与代码一致性 / 提交说明质量）

| 平台指标 | 本仓库对应实现 |
| --- | --- |
| 功能子系统 | `talentpro.validators`（规则集）、`talentpro.report`（数据契约）、`talentpro.gitlog` + `talentpro.milestone`（过程分析）、`talentpro.scaffold`（造题）、`talentpro.cli`（编排） |
| README 与代码一致性 | README「主要能力」表逐行对应真实模块；`repo.readme_code_consistency` 会校验引用是否存在 |
| 提交说明质量 | 全部使用约定式提交（`feat(scope): …`），`talentpro history .` 给出口径一致的质量分 |

## 4. Milestone 划分

平台要求：按业务开发顺序划分 Milestone，选择 Commit 区间，并说明每个 Milestone 完成的
独立目标。本仓库的提交已经按子系统切分，直接生成即可：

```bash
talentpro milestones . --out docs/MILESTONES.md      # 生成 Markdown，含提交区间
talentpro milestones . --json | jq '.milestones[] | {title, commit_range}'   # 只取区间
```

推荐的里程碑划分（标题 → 独立目标 → 验证方式）：

| # | 标题 | 独立目标 | 验证方式 |
| --- | --- | --- | --- |
| 1 | 工程骨架与包结构 | 仓库可安装、可导入，具备打包配置与忽略规则 | `uv pip install -e ".[dev]"` 成功，`python -c "import talentpro"` 无报错 |
| 2 | 题目解析与数据模型 | 能稳定解析题目目录，输出统一的 `TaskSpec` | `pytest tests/test_spec.py -q` 通过；缺 `task.toml` 抛 `TaskFormatError` |
| 3 | 报告生成与解析 | 参考解与判卷断言基于同一套真值 | `pytest tests/test_report.py -q` 通过；`talentpro compare` 可定位差异 |
| 4 | 规范校验规则集 | 题库规范变成可执行规则 | `pytest tests/test_validators.py -q` 通过；`examples/exam_001` 校验 0 error |
| 5 | 敏感信息与一致性扫描 | 提交前自动阻断密钥、内网地址、路径不一致 | `pytest tests/test_security.py tests/test_consistency.py -q` 通过 |
| 6 | 提交历史与里程碑分析 | 过程质量可量化、里程碑可自动划分并自检 | `talentpro milestones .` 覆盖全部提交且无 issue |
| 7 | 题目脚手架与 CLI | 一条命令造题并通过校验，能力可编排 | `pytest tests/test_scaffold.py tests/test_cli.py -q` 通过 |
| 8 | 文档、示例与持续集成 | 规范与流程沉淀，CI 保证质量稳定 | `talentpro repo-check .` 0 error，CI 绿灯 |

填写要点：

- 「标题」用上表第 2 列，「说明」至少写清**目标 + 验证方式**（`talentpro milestones`
  生成的 `目标：` / `验证：` 两行可直接粘贴）。
- 区间按上表顺序选取，保证**连续且不重叠**；自检脚本会检查覆盖与顺序。

## 5. Milestone 质量检查（聚合性 / 需求可验证性 / 代码覆盖 / 拆分粒度）

| 平台指标 | 自查方式 |
| --- | --- |
| 聚合性 | 每个里程碑对应一个功能子系统，而不是零散提交 |
| 需求可验证性 | 每个里程碑都写了「验证方式」，对应到具体测试文件 |
| 代码覆盖 | 里程碑区间内的提交都能对应到 `talentpro/` 下的模块与 `tests/` 下的用例 |
| 拆分粒度 | 里程碑数量 2~12；单段提交数不超过 8（`--max-per-milestone` 控制） |

```bash
talentpro milestones .            # 末尾会输出自检结论：覆盖 / 顺序 / 重复 / 粒度
```

## 6. 下一步 TODO

平台要求至少 5 条后续工作（不要求已有对应 Commit）。直接由检查结论生成，缺口优先：

```bash
talentpro todos .                 # 先跑 repo-check 摘取未通过项，再用通用待办补足到 ≥5 条
talentpro todos . --json          # 需要逐条粘贴时用 JSON
```

当前推荐的 5~7 条（与 `talentpro.backlog.DEFAULT_TODOS` 一致）：

1. **为题目配置独立判卷环境**：`[verifier] environment_mode = "separate"`，隔离判卷依赖。
2. **引入 Reward Kit 评分卡**：从二值 `reward` 升级为支持部分给分的分项得分。
3. **新增 `talentpro oracle` 子命令**：自动调用 `harbor trials start -a oracle` 并汇总 reward。
4. **建立题库索引 `tasks.json`**：记录难度、标签、最近判卷结果与通过率。
5. **补充大数据量性能用例**：≥100 万行日志，明确时间预算与超时基线。
6. **里程碑评审记录模板**：自动划分只保证覆盖与顺序，独立目标仍需人工复核。
7. **敏感信息扫描接入提交钩子**：pre-commit 调用 `talentpro check --category security`。
