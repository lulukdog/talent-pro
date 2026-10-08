"""里程碑（Milestone）划分与质量评估。

平台要求「按业务开发顺序划分 Milestone，选择对应 Commit 区间并填写标题与说明」。
本模块把提交历史按功能子系统聚合成分段，直接产出可粘贴到平台的标题与说明，
并在提交前做一次质量自检（覆盖、粒度、可验证性）。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .gitlog import Commit, parse_conventional
from .models import RuleResult, Severity

#: 子系统 → 里程碑标题。
SCOPE_TITLES: dict[str, str] = {
    "spec": "题目解析与数据模型",
    "report": "报告生成与解析",
    "validators": "规范校验规则集",
    "security": "敏感信息扫描",
    "gitlog": "提交历史分析",
    "milestone": "里程碑划分与质量评估",
    "backlog": "后续工作清单",
    "scaffold": "题目脚手架",
    "cli": "命令行入口",
    "docs": "文档与规范",
    "ci": "持续集成流水线",
    "tests": "测试体系",
    "release": "版本发布",
    "deps": "依赖与构建",
}

#: 子系统 → 独立目标（写入里程碑说明的「目标」）。
SCOPE_GOALS: dict[str, str] = {
    "spec": "让工具链能够稳定解析题目目录，并把 task.toml / 题面 / 判卷脚本统一成可复用的数据模型。",
    "report": "统一 report.txt 的生成与解析语义，使参考解与判卷断言基于同一套真值。",
    "validators": "把题库规范固化成可执行的规则集合，替代人工逐项核对。",
    "security": "在提交前自动阻断密钥、内网地址与本机路径泄漏。",
    "gitlog": "把提交历史与提交说明质量变成可量化指标，服务 repo 质量评估。",
    "milestone": "按业务顺序把提交历史切分成可独立验收的里程碑，并自检覆盖与粒度。",
    "backlog": "根据检查结论自动生成可执行的后续工作清单。",
    "scaffold": "一条命令生成结构完整、可直接通过校验的新题目。",
    "cli": "提供命令行入口，把校验、解析、划分能力串成可编排的流水线。",
    "docs": "沉淀题目规范、作业流程与架构说明，降低协作成本。",
    "ci": "在 CI 中自动执行 lint 与测试，保证提交质量稳定。",
    "tests": "用单元测试覆盖核心路径与异常分支，保证重构安全。",
}

#: 子系统 → 验证方式（写入里程碑说明的「验证」）。
SCOPE_VERIFY: dict[str, str] = {
    "spec": "`uv run pytest tests/test_spec.py -q` 通过；缺失 task.toml 时抛出 TaskFormatError。",
    "report": "`uv run pytest tests/test_report.py -q` 通过；对照样例日志的统计结果与人工核算一致。",
    "validators": "`uv run pytest tests/test_validators.py -q` 通过；对 exam_001 样例执行 check 无 error。",
    "security": "`uv run pytest tests/test_security.py -q` 通过；样例仓库扫描结果为 0 个 error。",
    "gitlog": "`uv run pytest tests/test_gitlog.py -q` 通过；对临时仓库的历史统计与 git 输出一致。",
    "milestone": "`uv run pytest tests/test_milestone.py -q` 通过；milestones 子命令输出覆盖全部提交。",
    "backlog": "`uv run pytest tests/test_backlog.py -q` 通过；生成的 TODO 数量不少于 5 条。",
    "scaffold": "`uv run pytest tests/test_scaffold.py -q` 通过；脚手架产物直接通过 check。",
    "cli": "`uv run pytest tests/test_cli.py -q` 通过；各子命令返回码符合约定。",
    "docs": "仓库级检查 repo.docs_links 与 repo.readme_code_consistency 均为通过。",
    "ci": "GitHub Actions 工作流在 3.11 / 3.12 上绿灯。",
    "tests": "`uv run pytest -q` 全量通过，且测试函数数量不低于仓库门槛。",
}

TYPE_TITLES: dict[str, str] = {
    "feat": "功能开发",
    "fix": "缺陷修复",
    "docs": "文档完善",
    "test": "测试补齐",
    "chore": "工程配置",
    "refactor": "代码重构",
    "ci": "持续集成",
    "perf": "性能优化",
}

DEFAULT_TITLE = "其他变更"

MIN_MILESTONES = 2
MAX_MILESTONES = 12

@dataclass(frozen=True)
class Stage:
    """业务阶段：把若干子系统聚合成一个可独立验收的里程碑。"""

    key: str
    title: str
    scopes: tuple[str, ...]
    goal: str
    verify: str


#: 按业务开发顺序排列的阶段划分（平台「Milestone 划分」步骤的建议粒度）。
STAGES: tuple[Stage, ...] = (
    Stage(
        key="skeleton",
        title="工程骨架与依赖锁定",
        scopes=("chore", "deps", "build"),
        goal="仓库可安装、可导入，具备打包配置、忽略规则与锁定的开发依赖。",
        verify='`uv pip install -e ".[dev]"` 成功，`python -c "import talentpro"` 无报错。',
    ),
    Stage(
        key="spec",
        title="题目解析与数据模型",
        scopes=("spec",),
        goal="让工具链能够稳定解析题目目录，并把 task.toml / 题面 / 判卷脚本统一成可复用的数据模型。",
        verify="`uv run pytest tests/test_spec.py -q` 通过；缺 task.toml 时抛 TaskFormatError。",
    ),
    Stage(
        key="report",
        title="报告生成与解析",
        scopes=("report",),
        goal="统一 report.txt 的生成与解析语义，使参考解与判卷断言基于同一套真值。",
        verify="`uv run pytest tests/test_report.py -q` 通过；`talentpro compare` 能定位差异。",
    ),
    Stage(
        key="validators",
        title="规范校验规则集",
        scopes=("validators", "security"),
        goal="把题库规范固化成可执行规则，覆盖结构、元数据、题面、一致性与敏感信息。",
        verify="`uv run pytest tests/test_validators.py tests/test_consistency.py tests/test_security.py -q` 通过。",
    ),
    Stage(
        key="repo",
        title="仓库级质量检查",
        scopes=("repo",),
        goal="对照平台 Repo 质量检查，校验功能子系统、README 与代码一致性、测试覆盖与整洁度。",
        verify="`uv run pytest tests/test_repo_check.py -q` 通过；本仓库自检 0 error。",
    ),
    Stage(
        key="process",
        title="提交历史与里程碑分析",
        scopes=("gitlog", "milestone", "release"),
        goal="把过程质量量化：提交说明质量分、里程碑划分与覆盖 / 粒度自检。",
        verify="`uv run pytest tests/test_gitlog.py tests/test_milestone.py -q` 通过。",
    ),
    Stage(
        key="authoring",
        title="待办清单与题目脚手架",
        scopes=("backlog", "scaffold"),
        goal="一条命令造出可通过校验的题目，并由检查结论生成后续工作清单。",
        verify="`uv run pytest tests/test_backlog.py tests/test_scaffold.py -q` 通过；脚手架产物 0 error。",
    ),
    Stage(
        key="cli",
        title="命令行编排",
        scopes=("cli",),
        goal="把校验、解析、划分、造题能力串成可编排的流水线，并给出稳定的返回码约定。",
        verify="`uv run pytest tests/test_cli.py -q` 通过；各子命令返回码符合约定。",
    ),
    Stage(
        key="quality",
        title="文档、示例与持续集成",
        scopes=("docs", "tests", "ci"),
        goal="沉淀规范与流程文档，收录示例题目，并在 CI 中固化 lint 与测试。",
        verify="`talentpro repo-check . --strict` 0 warning；CI 在 3.11 / 3.12 上绿灯。",
    ),
)


def stage_for(key: str) -> Stage | None:
    """按 scope（或 type）找到所属业务阶段。"""
    for stage in STAGES:
        if key in stage.scopes:
            return stage
    return None


def plan_milestones_by_stage(commits: Sequence[Commit]) -> list[MilestoneDraft]:
    """按业务阶段聚合提交，颗粒度对齐平台建议（通常 6~10 个里程碑）。

    同一阶段在后续再次出现（迭代增强）时单独成段并加「迭代增强」后缀，避免出现两个
    同名里程碑，同时保证每段仍是连续的提交区间。
    """
    groups: list[tuple[Stage, str, str, list[Commit]]] = []
    seen: set[str] = set()
    current: Stage | None = None

    for commit in commits:
        commit_type, scope = parse_conventional(commit.subject)
        stage = stage_for(scope or commit_type or "other")

        if stage is None:
            # 无法识别的 scope 并入前一段，避免出现只有一条提交的孤立里程碑
            if groups:
                groups[-1][3].append(commit)
            continue

        if stage is current:
            groups[-1][3].append(commit)
            continue

        current = stage
        repeated = stage.key in seen
        seen.add(stage.key)
        title = f"{stage.title}（迭代增强）" if repeated else stage.title
        goal = f"在既有「{stage.title}」能力上迭代增强：{stage.goal}" if repeated else stage.goal
        groups.append((stage, title, goal, [commit]))

    drafts: list[MilestoneDraft] = []
    for position, (stage, title, goal, group) in enumerate(groups, start=1):
        drafts.append(
            MilestoneDraft(
                index=position,
                key=stage.key,
                title=title,
                goal=goal,
                verify=stage.verify,
                commits=tuple(group),
            )
        )
    return drafts


@dataclass(frozen=True)
class MilestoneDraft:
    """一个候选里程碑。"""

    index: int
    key: str
    title: str
    goal: str
    verify: str
    commits: tuple[Commit, ...]

    @property
    def commit_count(self) -> int:
        return len(self.commits)

    @property
    def start_sha(self) -> str:
        return self.commits[0].short_sha

    @property
    def end_sha(self) -> str:
        return self.commits[-1].short_sha

    @property
    def commit_range(self) -> str:
        return f"{self.start_sha}..{self.end_sha}"

    @property
    def description(self) -> str:
        """可直接粘贴到平台「说明」栏的文本。"""
        lines = [f"目标：{self.goal}", f"验证：{self.verify}", "包含提交："]
        lines.extend(f"- {commit.short_sha} {commit.subject}" for commit in self.commits)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "title": self.title,
            "commit_range": self.commit_range,
            "commit_count": self.commit_count,
            "description": self.description,
            "commits": [commit.to_dict() for commit in self.commits],
        }


def plan_milestones(
    commits: Sequence[Commit],
    *,
    max_per_milestone: int = 8,
) -> list[MilestoneDraft]:
    """把**时间正序**的提交序列切分成里程碑。

    切分依据是约定式提交的 ``scope``（缺失时退化为 ``type``），并保证单段不超过
    ``max_per_milestone`` 个提交。
    """
    if not commits:
        return []

    groups: list[list[Commit]] = []
    current_key: str | None = None
    for commit in commits:
        commit_type, scope = parse_conventional(commit.subject)
        key = scope or commit_type or "other"
        if key != current_key or not groups or len(groups[-1]) >= max_per_milestone:
            groups.append([])
            current_key = key
        groups[-1].append(commit)

    drafts: list[MilestoneDraft] = []
    for position, group in enumerate(groups, start=1):
        commit_type, scope = parse_conventional(group[0].subject)
        key = scope or commit_type or "other"
        drafts.append(
            MilestoneDraft(
                index=position,
                key=key,
                title=_title_for(key),
                goal=SCOPE_GOALS.get(key, f"完成「{_title_for(key)}」这一独立可验证目标。"),
                verify=SCOPE_VERIFY.get(key, "`uv run pytest -q` 相关用例通过。"),
                commits=tuple(group),
            )
        )
    return drafts


def _title_for(key: str) -> str:
    if key in SCOPE_TITLES:
        return SCOPE_TITLES[key]
    if key in TYPE_TITLES:
        return TYPE_TITLES[key]
    return f"{key} 相关变更" if key != "other" else DEFAULT_TITLE


def validate_milestones(
    drafts: Sequence[MilestoneDraft],
    all_commits: Sequence[Commit],
    *,
    min_count: int = MIN_MILESTONES,
    max_count: int = MAX_MILESTONES,
) -> list[RuleResult]:
    """自检里程碑划分质量：覆盖、顺序、粒度、可验证性。"""
    rule_id = "milestone.plan"
    results: list[RuleResult] = []

    if len(drafts) < min_count:
        results.append(
            RuleResult(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=f"里程碑数量为 {len(drafts)}，少于下限 {min_count}",
                hint="按功能子系统切分，让每个里程碑都有独立可验收的目标",
            )
        )
    if len(drafts) > max_count:
        results.append(
            RuleResult(
                rule_id=rule_id,
                severity=Severity.WARNING,
                message=f"里程碑数量为 {len(drafts)}，超过建议上限 {max_count}",
                hint="过于细碎会让评审成本上升",
            )
        )

    planned = [commit.sha for draft in drafts for commit in draft.commits]
    actual = [commit.sha for commit in all_commits]
    missing = [sha for sha in actual if sha not in planned]
    extra = [sha for sha in planned if sha not in actual]
    if missing:
        results.append(
            RuleResult(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=f"{len(missing)} 个提交未被任何里程碑覆盖",
                hint="平台按 Commit 区间归档，遗漏会造成开发过程断档",
            )
        )
    if extra:
        results.append(
            RuleResult(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message=f"{len(extra)} 个提交不在仓库历史中",
                hint="区间选择有误，请重新划分",
            )
        )
    if len(set(planned)) != len(planned):
        results.append(
            RuleResult(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message="存在被多个里程碑重复选择的提交",
                hint="里程碑区间不应重叠",
            )
        )
    if planned != actual and not missing and not extra:
        results.append(
            RuleResult(
                rule_id=rule_id,
                severity=Severity.ERROR,
                message="里程碑顺序与提交时间顺序不一致",
                hint="按业务开发顺序排列里程碑",
            )
        )

    for draft in drafts:
        if draft.commit_count == 0:
            results.append(
                RuleResult(rule_id, Severity.ERROR, f"里程碑 {draft.index} 未包含任何提交")
            )
        if not draft.goal.strip() or not draft.verify.strip():
            results.append(
                RuleResult(
                    rule_id,
                    Severity.WARNING,
                    f"里程碑 {draft.index} 缺少目标或验证方式",
                    hint="说明需要回答「完成了什么」与「如何验证」",
                )
            )
    return results


def render_milestones(drafts: Iterable[MilestoneDraft]) -> str:
    """渲染为 Markdown，便于直接粘贴到平台表单。"""
    blocks: list[str] = []
    for draft in drafts:
        blocks.append(f"## Milestone {draft.index} · {draft.title}")
        blocks.append("")
        blocks.append(f"- 提交区间：`{draft.commit_range}`（{draft.commit_count} 个提交）")
        blocks.append(f"- 目标：{draft.goal}")
        blocks.append(f"- 验证：{draft.verify}")
        blocks.append("- 包含提交：")
        blocks.extend(f"    - `{commit.short_sha}` {commit.subject}" for commit in draft.commits)
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"
