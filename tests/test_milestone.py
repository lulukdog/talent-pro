"""里程碑划分与质量自检测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

from talentpro.gitlog import Commit
from talentpro.milestone import (
    STAGES,
    MilestoneDraft,
    plan_milestones,
    plan_milestones_by_stage,
    render_milestones,
    stage_for,
    validate_milestones,
)


def make_commits(subjects: list[str]) -> list[Commit]:
    """按给定主题构造时间正序的提交序列。"""
    commits = []
    for index, subject in enumerate(subjects):
        sha = f"{index:040d}"
        commits.append(
            Commit(
                sha=sha,
                short_sha=sha[:7],
                author="tester",
                email="t@example.com",
                date=datetime(2024, 1, 1) + timedelta(minutes=index),
                subject=subject,
                body="",
            )
        )
    return commits


SAMPLE_SUBJECTS = [
    "chore: 初始化仓库骨架",
    "feat(spec): 增加题目解析",
    "test(spec): 补齐解析用例",
    "feat(validators): 增加结构规则",
    "test(validators): 增加规则用例",
    "docs: 补充使用说明",
]


def test_plan_milestones_groups_by_scope() -> None:
    drafts = plan_milestones(make_commits(SAMPLE_SUBJECTS))
    keys = [draft.key for draft in drafts]
    assert keys == ["chore", "spec", "validators", "docs"]
    assert [draft.commit_count for draft in drafts] == [1, 2, 2, 1]


def test_plan_milestones_splits_long_groups() -> None:
    subjects = [f"feat(spec): 改动 {index}" for index in range(5)]
    drafts = plan_milestones(make_commits(subjects), max_per_milestone=2)
    assert [draft.commit_count for draft in drafts] == [2, 2, 1]


def test_plan_milestones_empty() -> None:
    assert plan_milestones([]) == []


def test_milestone_titles_and_commit_range() -> None:
    drafts = plan_milestones(make_commits(SAMPLE_SUBJECTS))
    spec = next(draft for draft in drafts if draft.key == "spec")
    assert spec.title == "题目解析与数据模型"
    assert spec.commit_range.endswith(spec.end_sha)
    assert spec.commit_range.startswith(spec.start_sha)
    assert "目标：" in spec.description
    assert "验证：" in spec.description
    assert spec.description.count("- ") == spec.commit_count


def test_milestone_to_dict_contains_commits() -> None:
    draft = plan_milestones(make_commits(SAMPLE_SUBJECTS))[0]
    payload = draft.to_dict()
    assert payload["commit_count"] == 1
    assert payload["commits"][0]["subject"] == "chore: 初始化仓库骨架"


def test_validate_milestones_passes_for_full_plan() -> None:
    commits = make_commits(SAMPLE_SUBJECTS)
    drafts = plan_milestones(commits)
    assert validate_milestones(drafts, commits) == []


def test_validate_milestones_detects_uncovered_commit() -> None:
    commits = make_commits(SAMPLE_SUBJECTS)
    drafts = plan_milestones(commits)[:2]
    issues = validate_milestones(drafts, commits)
    assert any("未被任何里程碑覆盖" in issue.message for issue in issues)


def test_validate_milestones_detects_duplicate_commits() -> None:
    commits = make_commits(SAMPLE_SUBJECTS)
    drafts = plan_milestones(commits)
    duplicated = [drafts[0], drafts[0], *drafts[1:]]
    issues = validate_milestones(duplicated, commits)
    assert any("重复选择" in issue.message for issue in issues)


def test_validate_milestones_detects_wrong_order() -> None:
    commits = make_commits(SAMPLE_SUBJECTS)
    drafts = plan_milestones(commits)
    reordered = list(reversed(drafts))
    issues = validate_milestones(reordered, commits)
    assert any("顺序" in issue.message for issue in issues)


def test_validate_milestones_requires_minimum_count() -> None:
    commits = make_commits(SAMPLE_SUBJECTS)
    drafts = plan_milestones(commits)[:1]
    issues = validate_milestones(drafts, commits)
    assert any("少于下限" in issue.message for issue in issues)


def test_validate_milestones_warns_when_goal_missing() -> None:
    commit = make_commits(["feat(spec): x"])[0]
    draft = MilestoneDraft(index=1, key="spec", title="t", goal="", verify="", commits=(commit,))
    issues = validate_milestones([draft, draft], [commit, commit])
    assert any("缺少目标或验证方式" in issue.message for issue in issues)


def test_render_milestones_markdown() -> None:
    drafts = plan_milestones(make_commits(SAMPLE_SUBJECTS))
    markdown = render_milestones(drafts)
    assert "## Milestone 1" in markdown
    assert "提交区间" in markdown
    assert "题目解析与数据模型" in markdown
    assert markdown.endswith("\n")


STAGE_SUBJECTS = [
    "chore: 初始化仓库骨架",
    "feat(spec): 增加题目解析",
    "feat(report): 统一报告契约",
    "feat(validators): 增加规则框架",
    "feat(security): 增加敏感信息扫描",
    "feat(gitlog): 读取提交历史",
    "feat(milestone): 划分里程碑",
    "docs: 补充规范文档",
    "ci: 增加流水线",
]


def test_stage_for_maps_scope_and_type() -> None:
    assert stage_for("spec") is not None
    assert stage_for("security") is stage_for("validators")
    assert stage_for("unknown-scope") is None


def test_stages_come_in_business_order() -> None:
    keys = [stage.key for stage in STAGES]
    assert keys[0] == "skeleton"
    assert keys[-1] == "quality"
    assert len(keys) == len(set(keys))


def test_plan_by_stage_merges_subsystems() -> None:
    drafts = plan_milestones_by_stage(make_commits(STAGE_SUBJECTS))
    titles = [draft.title for draft in drafts]
    assert titles == [
        "工程骨架与依赖锁定",
        "题目解析与数据模型",
        "报告生成与解析",
        "规范校验规则集",
        "提交历史与里程碑分析",
        "文档、示例与持续集成",
    ]
    validators = next(draft for draft in drafts if draft.key == "validators")
    assert validators.commit_count == 2


def test_plan_by_stage_covers_every_commit() -> None:
    commits = make_commits(STAGE_SUBJECTS)
    drafts = plan_milestones_by_stage(commits)
    assert validate_milestones(drafts, commits) == []


def test_plan_by_stage_attaches_unknown_scopes_to_previous_group() -> None:
    commits = make_commits(["feat(spec): 解析", "随手改一下"])
    drafts = plan_milestones_by_stage(commits)
    assert len(drafts) == 1
    assert drafts[0].commit_count == 2
