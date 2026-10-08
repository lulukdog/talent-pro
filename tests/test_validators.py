"""规则框架与题目级规则的测试。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from talentpro.models import RuleResult, Severity
from talentpro.spec import load_task
from talentpro.validators import categories, registered_rules, run_checks
from talentpro.validators.base import RegisteredRule


def copy_task(source: Path, target_dir: Path) -> Path:
    """按原名复制一份题目，避免触发目录命名告警。"""
    destination = target_dir / "copy" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination


def test_rule_ids_are_unique() -> None:
    ids = [item.id for item in registered_rules()]
    assert len(ids) == len(set(ids))


def test_categories_cover_expected_groups() -> None:
    assert set(categories()) == {
        "consistency",
        "instruction",
        "metadata",
        "report",
        "security",
        "structure",
    }


def test_registered_rules_filter_by_category() -> None:
    security_rules = registered_rules("security")
    assert security_rules
    assert all(item.category == "security" for item in security_rules)


def test_clean_task_has_no_findings(task) -> None:
    report = run_checks(task)
    assert report.passed
    assert report.warnings == []


def test_run_checks_can_limit_rules(task) -> None:
    report = run_checks(task, rule_ids=["structure.canary"])
    assert report.rule_ids == {"structure.canary"}


def test_missing_verifier_script_reports_error(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    (task_root / "tests/test.sh").unlink()
    report = run_checks(load_task(task_root))
    assert "structure.required_files" in report.failed_rule_ids


def test_missing_solution_reports_warning(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    (task_root / "solution/solve.sh").unlink()
    report = run_checks(load_task(task_root))
    assert report.passed
    assert "structure.required_files" in {item.rule_id for item in report.warnings}


def test_empty_instruction_reports_error(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    (task_root / "instruction.md").write_text("", encoding="utf-8")
    report = run_checks(load_task(task_root))
    assert "structure.empty_files" in report.failed_rule_ids
    assert "instruction.sections" in report.failed_rule_ids


def test_schema_version_mismatch(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    config = (task_root / "task.toml").read_text(encoding="utf-8")
    (task_root / "task.toml").write_text(config.replace('version = "1.0"', 'version = "2.0"'), encoding="utf-8")
    report = run_checks(load_task(task_root))
    assert "metadata.schema_version" in report.failed_rule_ids


def test_internet_disabled_but_verifier_needs_network(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    config = (task_root / "task.toml").read_text(encoding="utf-8")
    (task_root / "task.toml").write_text(config.replace("allow_internet = true", "allow_internet = false"), encoding="utf-8")
    report = run_checks(load_task(task_root))
    assert "metadata.internet" in report.failed_rule_ids


def test_short_description_reports_warning(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    config = (task_root / "task.toml").read_text(encoding="utf-8")
    (task_root / "task.toml").write_text(
        config.replace('description = "分析 Web 服务器访问日志并输出统计报告。"', 'description = "短"'),
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "metadata.task_info" in {item.rule_id for item in report.warnings}


def test_instruction_without_output_path(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    instruction = (task_root / "instruction.md").read_text(encoding="utf-8")
    (task_root / "instruction.md").write_text(
        instruction.replace("/output/report.txt", "报告文件"), encoding="utf-8"
    )
    report = run_checks(load_task(task_root))
    assert "instruction.output_path" in report.failed_rule_ids


def test_instruction_missing_sections(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    (task_root / "instruction.md").write_text(
        "随便写一点内容，说明要完成的任务即可。\n", encoding="utf-8"
    )
    report = run_checks(load_task(task_root))
    assert "instruction.sections" in report.failed_rule_ids


def test_rule_exception_is_downgraded(task, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_task) -> list[RuleResult]:
        raise RuntimeError("规则内部错误")

    fake = RegisteredRule(id="test.boom", title="异常规则", category="test", func=boom)
    monkeypatch.setattr("talentpro.validators.base.registered_rules", lambda category=None: [fake])

    report = run_checks(task)
    assert "test.boom" in report.failed_rule_ids
    assert "规则执行异常" in report.errors[0].message


def test_repo_checks_report_severity_labels() -> None:
    assert Severity.ERROR.label == "ERROR"
    assert Severity.WARNING.label == "WARN "
    assert Severity.INFO.label == "INFO "
