# 架构与扩展

## 1. 分层

```
CLI (talentpro.cli)
  └── 编排层
        ├── 题目：talentpro.spec  →  talentpro.validators.{structure,metadata,
        │                          instruction,consistency,report_contract,security}
        ├── 仓库：talentpro.validators.repo
        ├── 数据：talentpro.report（生成 / 解析 / 比对）
        ├── 过程：talentpro.gitlog → talentpro.milestone
        ├── 待办：talentpro.backlog
        └── 造题：talentpro.scaffold
              └── 公共模型 talentpro.models（RuleResult / CheckReport / Analysis / Mismatch）
```

设计取舍：

- **解析与校验分离**：`load_task` 采取「尽力解析」，文件缺失返回 `None`/空串，由规则给出
  可读结论；只有 `task.toml` 缺失或 TOML 非法才抛 `TaskFormatError`。
- **规则是可注册函数**：新增规则不改框架代码，也无需改动 CLI。
- **判卷语义只实现一次**：`report.py` 同时服务「生成标准报告」与「比对考生产出」，
  避免参考解与断言各写一遍统计逻辑而逐渐漂移。

## 2. 数据流

```
access.log ──parse_log──▶ [LogEntry] ──analyze──▶ Analysis ──render_report──▶ report.txt
                                                        │
                                                 compare_reports ◀── 考生产出

题目目录 ──load_task──▶ TaskSpec ──run_checks──▶ CheckReport ──▶ 终端 / JSON
                                        │
                                        └──▶ suggest_todos ──▶ 后续工作清单

git log ──read_commits──▶ [Commit] ──plan_milestones──▶ [MilestoneDraft]
                                        └── validate_milestones ──▶ 覆盖 / 粒度 / 顺序自检
```

## 3. 规则框架

规则函数签名是 `Callable[[TaskSpec], list[RuleResult]]`，经 `@rule` 装饰器注册：

```python
@rule("consistency.example", "示例规则", "consistency")
def check_example(task: TaskSpec) -> list[RuleResult]:
    if 条件成立:
        return []
    return [finding("consistency.example", Severity.ERROR, "问题描述", "修复建议")]
```

- 规则只返回**有问题的项**；全部通过时 `run_checks` 会补一条 `INFO`，便于在明细里确认
  规则确实执行过。
- 规则内部抛异常不会中断检查：会被降级为一条 `ERROR`（`规则执行异常`），保证一次运行
  能拿到尽可能多的信息。
- 严重级别：`ERROR` 阻断（退出码 1），`WARNING` 提示（`--strict` 时阻断），`INFO` 仅展示。

## 4. 规则分类

| 分类 | 关注点 | 覆盖问题 |
| --- | --- | --- |
| `structure` | 必填文件、文件非空、目录命名、canary、输入数据 | 少文件、空文件导致判卷直接失败 |
| `metadata` | schema 版本、名称描述、难度标签、时限、资源、网络开关 | 版本不兼容、判卷装不上依赖 |
| `instruction` | 语义区块、输出路径、格式样例、信息泄露、长度 | 考生看不懂、无法复现 |
| `consistency` | 题面↔判卷↔参考解↔镜像 路径与产物 | 「题面说 A、判卷读 B」这类致命不一致 |
| `report` | 输出格式样例可解析、区块标题与判卷一致 | 样例格式错误、无人在意的产出 |
| `security` | 密钥令牌、硬编码口令、内网地址、本机路径 | 提交前的合规清理 |
| `repo` | 功能子系统、README 一致性、入口点、测试、元文件、CI、整洁度 | 仓库级质量评估 |

## 5. 扩展指南

- **加题目规则**：在对应分类模块里加 `@rule` 函数，并在 `talentpro/validators/__init__.py`
  中确保模块被导入（现有模块已导入）。
- **加仓库规则**：写 `Callable[[Path], list[RuleResult]]`，追加到 `repo.REPO_RULES` 元组。
- **加 CLI 子命令**：在 `cli.build_parser()` 中注册子解析器，实现 `cmd_xxx(args) -> int`，
  并在 `cli.COMMANDS` 中登记。
- **加输出格式**：改动 `report.py` 的区块常量与 `render_report`/`parse_report` 时，需同步
  `scaffold.py` 的判卷模板，否则 `report.sections_aligned` 会报错。

## 6. 测试策略

| 层次 | 覆盖方式 |
| --- | --- |
| 单元 | 解析、统计、路径抽取、里程碑切分等纯函数 |
| 规则 | 对干净任务断言 0 error；再逐条破坏（删文件、改版本、改路径）断言命中对应规则 |
| 端到端 | `scaffold` 产物直接跑 `run_checks` 必须 0 error / 0 warning |
| 自检 | `check_repository(REPO_ROOT)` 必须 0 error，防止文档与代码脱节 |
| CLI | 子命令返回码与 JSON 输出结构 |

安全测试里构造假密钥一律使用字符串拼接，避免仓库自身命中敏感信息扫描。
