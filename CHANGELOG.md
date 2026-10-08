# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 结构，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-10-08

首个可用版本：题目规范校验、报告契约、里程碑划分与造题脚手架。

### Added

- **题目解析**（`talentpro.spec`）：`load_task` 把 `task.toml`、题面、镜像、参考解与判卷脚本
  解析为统一的 `TaskSpec`；提供绝对路径抽取与容器路径过滤，区分 `/data/access.log` 与
  HTTP 路由 `/api/users`。
- **报告契约**（`talentpro.report`）：访问日志解析、统计（每 IP 请求数 / 状态码分布 / Top IP）
  与 `report.txt` 的生成、解析、逐区块比对；Top IP 并列时按字典序取最小，保证结果可复现。
- **规范校验**（`talentpro.validators`）：28 条题目级规则，覆盖结构、元数据、题面、
  一致性、报告契约与安全六个分类；仓库级另有 12 条规则。
- **安全扫描**（`talentpro.validators.security`）：识别 Figma / GitHub / 模型服务 / 云厂商 /
  Slack 凭据、私钥、硬编码口令、内部域名与本机用户路径，命中信息做脱敏展示。
- **提交与里程碑分析**（`talentpro.gitlog`、`talentpro.milestone`）：读取提交历史，评估约定式
  提交前缀覆盖率与含糊主题；按子系统自动划分里程碑并自检覆盖、顺序、重复与粒度。
- **后续工作清单**（`talentpro.backlog`）：从检查结论推导待办，并保证不少于 5 条。
- **题目脚手架**（`talentpro.scaffold`）：一条命令生成结构完整、可直接通过校验的题目，
  含确定性样例日志与自洽的判卷断言。
- **命令行**（`talentpro.cli`）：`check`、`repo-check`、`report`、`compare`、`scaffold`、
  `milestones`、`todos`、`history` 八个子命令，返回码约定 `0/1/2`。
- **示例与文档**：`examples/exam_001` 完整示例题目；`docs/TASK_SPEC.md`（题目规范）、
  `docs/ARCHITECTURE.md`（架构与扩展）、`docs/PLATFORM_WORKFLOW.md`（平台作业流程对齐）。
- **测试与 CI**：pytest 单元测试覆盖规则、脚手架、里程碑与 CLI；GitHub Actions 在
  Python 3.11 / 3.12 上执行 ruff 与 pytest。

### Notes

- 运行时零第三方依赖，仅需 Python 3.11+（使用标准库 `tomllib`）。
- 判卷侧模板固定 `Harbor v0.5.0` 与 `task.toml` schema `version = "1.0"`。
