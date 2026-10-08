"""后续工作清单的测试。"""

from __future__ import annotations

from talentpro.backlog import (
    DEFAULT_TODOS,
    TodoItem,
    render_todos,
    suggest_from_report,
    suggest_todos,
    validate_todos,
)
from talentpro.models import CheckReport, RuleResult, Severity
from talentpro.spec import load_task
from talentpro.validators import run_checks


def test_default_todos_meet_minimum() -> None:
    assert len(DEFAULT_TODOS) >= 5
    assert validate_todos(DEFAULT_TODOS) == []


def test_suggest_todos_without_findings_returns_minimum() -> None:
    items = suggest_todos()
    assert len(items) >= 5


def test_suggest_todos_includes_findings_first() -> None:
    findings = [
        RuleResult("structure.required_files", Severity.ERROR, "缺少判卷入口", "补上 test.sh"),
        RuleResult("instruction.length", Severity.WARNING, "题面过短"),
    ]
    items = suggest_todos(findings, minimum=3)
    assert items[0].title.startswith("修复 structure.required_files")
    assert items[0].rationale == "补上 test.sh"


def test_suggest_todos_deduplicates_rules() -> None:
    findings = [
        RuleResult("security.secrets", Severity.ERROR, "命中 A"),
        RuleResult("security.secrets", Severity.ERROR, "命中 B"),
    ]
    items = suggest_todos(findings, minimum=5)
    assert sum(1 for item in items if "security.secrets" in item.title) == 1


def test_suggest_todos_ignores_info_findings() -> None:
    findings = [RuleResult("metadata.difficulty", Severity.INFO, "标签为空")]
    items = suggest_todos(findings, minimum=5)
    assert all("metadata.difficulty" not in item.title for item in items)


def test_suggest_from_report_uses_task_findings(task) -> None:
    report = run_checks(task)
    items = suggest_from_report(report)
    assert len(items) >= 5
    assert all(item.acceptance for item in items)


def test_validate_todos_reports_short_list() -> None:
    problems = validate_todos([TodoItem("a", "b", "c")], minimum=5)
    assert any("少于要求下限" in problem for problem in problems)


def test_validate_todos_requires_acceptance() -> None:
    items = [TodoItem(f"标题 {index}", "背景", "") for index in range(5)]
    problems = validate_todos(items)
    assert any("缺少验收标准" in problem for problem in problems)


def test_validate_todos_detects_duplicates() -> None:
    items = [TodoItem("同一个标题", "背景", "验收") for _ in range(5)]
    assert any("重复" in problem for problem in validate_todos(items))


def test_render_todos_markdown() -> None:
    markdown = render_todos(DEFAULT_TODOS[:2])
    assert markdown.startswith("### TODO 1")
    assert "验收：" in markdown
    assert markdown.endswith("\n")


def test_report_of_load_task_has_expected_shape(task) -> None:
    report: CheckReport = run_checks(load_task(task.root))
    assert isinstance(report.to_dict()["passed"], bool)
