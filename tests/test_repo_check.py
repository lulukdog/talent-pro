"""仓库级检查的测试（含对本仓库自身的自检）。"""

from __future__ import annotations

from pathlib import Path

from talentpro.validators.repo import check_repository


def test_repo_root_missing(tmp_path: Path) -> None:
    report = check_repository(tmp_path / "nope")
    assert "repo.root" in report.failed_rule_ids


def test_empty_repository_reports_core_errors(tmp_path: Path) -> None:
    report = check_repository(tmp_path)
    failed = report.failed_rule_ids
    assert {"repo.subsystems", "repo.readme", "repo.tests"} <= failed


def test_readme_module_reference_must_exist(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# 项目\n\n引用不存在的模块 talentpro.nonexistent。\n" + "说明" * 400,
        encoding="utf-8",
    )
    report = check_repository(tmp_path)
    assert "repo.readme_code_consistency" in report.failed_rule_ids


def test_readme_file_reference_must_exist(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# 项目\n\n见 `talentpro/cli.py` 与 `docs/missing.md`。\n" + "说明" * 400,
        encoding="utf-8",
    )
    report = check_repository(tmp_path)
    assert "repo.readme_code_consistency" in report.failed_rule_ids


def test_entry_point_module_must_exist(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n\n[project.scripts]\ncmd = "nope.main:main"\n',
        encoding="utf-8",
    )
    report = check_repository(tmp_path)
    assert "repo.entry_points" in report.failed_rule_ids


def test_entry_point_function_must_exist(tmp_path: Path) -> None:
    package = tmp_path / "talentpro"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (pyproject := tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n\n[project.scripts]\ncmd = "talentpro.cli:main"\n',
        encoding="utf-8",
    )
    assert pyproject.exists()
    (package / "cli.py").write_text('"""cli"""\n\ndef other() -> int:\n    return 0\n', encoding="utf-8")
    report = check_repository(tmp_path)
    assert "repo.entry_points" in report.failed_rule_ids


def test_hygiene_reports_stray_artifacts(tmp_path: Path) -> None:
    (tmp_path / "leftover.pyc").write_bytes(b"\x00")
    (tmp_path / ".DS_Store").write_bytes(b"\x00")
    report = check_repository(tmp_path)
    messages = [item.message for item in report.results if item.rule_id == "repo.hygiene"]
    assert any("leftover.pyc" in message for message in messages)
    assert any(".DS_Store" in message for message in messages)
