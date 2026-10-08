"""命令行入口的测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from talentpro.cli import main
from talentpro.report import render_report

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_check_clean_task(sample_task: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(sample_task)]) == 0
    assert "通过" in capsys.readouterr().out


def test_check_json_output(sample_task: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(sample_task), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["errors"] == 0


def test_check_missing_task_returns_input_error(tmp_path: Path) -> None:
    assert main(["check", str(tmp_path)]) == 2


def test_check_reports_findings(sample_task: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (sample_task / "tests/test.sh").unlink()
    assert main(["check", str(sample_task)]) == 1
    assert "structure.required_files" in capsys.readouterr().out


def test_check_category_filter(sample_task: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(sample_task), "--category", "security"]) == 0
    output = capsys.readouterr().out
    assert "security." in output
    assert "structure." not in output


def test_repo_check_on_this_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["repo-check", str(REPO_ROOT)]) == 0
    assert "仓库检查" in capsys.readouterr().out


def test_report_writes_file(log_file: Path, tmp_path: Path) -> None:
    output = tmp_path / "report.txt"
    assert main(["report", str(log_file), "-o", str(output)]) == 0
    assert output.read_text(encoding="utf-8").startswith("=== Top IP ===")


def test_report_matches_reference(log_file: Path, tmp_path: Path) -> None:
    from talentpro.report import analyze, load_log

    output = tmp_path / "report.txt"
    main(["report", str(log_file), "-o", str(output)])
    expected = render_report(analyze(load_log(log_file)))
    assert output.read_text(encoding="utf-8") == expected


def test_report_invalid_log_returns_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.log"
    bad.write_text("这不是日志\n", encoding="utf-8")
    assert main(["report", str(bad)]) == 2


def test_compare_identical(log_file: Path, tmp_path: Path) -> None:
    from talentpro.report import analyze, load_log

    report = tmp_path / "report.txt"
    report.write_text(render_report(analyze(load_log(log_file))), encoding="utf-8")
    assert main(["compare", str(report), str(report)]) == 0


def test_compare_different(log_file: Path, tmp_path: Path) -> None:
    from talentpro.report import analyze, load_log

    expected = tmp_path / "expected.txt"
    actual = tmp_path / "actual.txt"
    expected.write_text(render_report(analyze(load_log(log_file))), encoding="utf-8")
    actual.write_text(expected.read_text(encoding="utf-8").replace(": 3", ": 9"), encoding="utf-8")
    assert main(["compare", str(expected), str(actual)]) == 1


def test_scaffold_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    destination = tmp_path / "exam_042"
    assert main(["scaffold", "exam_042", "--dest", str(destination), "--author", "tester"]) == 0
    assert (destination / "task.toml").is_file()
    assert "已生成题目" in capsys.readouterr().out


def test_scaffold_command_rejects_existing(tmp_path: Path) -> None:
    destination = tmp_path / "exam_043"
    destination.mkdir()
    (destination / "keep.txt").write_text("x", encoding="utf-8")
    assert main(["scaffold", "exam_043", "--dest", str(destination)]) == 2


def test_milestones_command(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["milestones", str(git_repo)]) == 0
    output = capsys.readouterr().out
    assert "## Milestone 1" in output
    assert "里程碑自检通过" in output


def test_milestones_json(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["milestones", str(git_repo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["milestones"]
    assert payload["issues"] == []


def test_milestones_out_file(git_repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "milestones.md"
    assert main(["milestones", str(git_repo), "--out", str(target)]) == 0
    assert "## Milestone" in target.read_text(encoding="utf-8")


def test_milestones_outside_repository(tmp_path: Path) -> None:
    assert main(["milestones", str(tmp_path)]) == 2


def test_todos_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["todos"]) == 0
    assert capsys.readouterr().out.count("### TODO") >= 5


def test_todos_json_with_task(sample_task: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["todos", str(sample_task), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) >= 5
    assert {"title", "rationale", "acceptance"} == set(payload[0])


def test_history_command(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["history", str(git_repo)])
    output = capsys.readouterr().out
    assert "提交总数：4" in output
    assert "提交说明质量" in output


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "talentpro" in capsys.readouterr().out


def test_missing_subcommand_exits() -> None:
    with pytest.raises(SystemExit):
        main([])
