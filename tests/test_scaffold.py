"""脚手架与日志生成器的测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from talentpro.report import analyze_log_text
from talentpro.scaffold import (
    generate_access_log,
    next_task_id,
    render,
    scaffold_task,
)
from talentpro.spec import load_task
from talentpro.validators import run_checks

EXPECTED_FILES = {
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "environment/access.log",
    "solution/solve.sh",
    "tests/test.sh",
    "tests/test_state.py",
}


def test_generate_access_log_is_deterministic() -> None:
    assert generate_access_log(seed=7, lines=20) == generate_access_log(seed=7, lines=20)
    assert generate_access_log(seed=7, lines=20) != generate_access_log(seed=8, lines=20)


def test_generate_access_log_line_count_and_top_ip() -> None:
    text = generate_access_log(seed=42, lines=32)
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 32
    analysis = analyze_log_text(text)
    counts = sorted(analysis.ip_counts.values(), reverse=True)
    assert counts[0] > counts[1], "Top IP 必须唯一，否则题目有歧义"


def test_generate_access_log_rejects_tiny_input() -> None:
    with pytest.raises(ValueError, match="至少"):
        generate_access_log(lines=4)


def test_scaffold_creates_expected_files(tmp_path: Path) -> None:
    result = scaffold_task(tmp_path / "exam_001", "exam_001", author="tester")
    assert set(result.files) == EXPECTED_FILES
    for relative in EXPECTED_FILES:
        assert (result.root / relative).is_file(), relative
    assert (result.root / "solution/solve.sh").stat().st_mode & 0o111


def test_scaffolded_task_passes_all_checks(tmp_path: Path) -> None:
    result = scaffold_task(tmp_path / "exam_002", "exam_002", author="tester")
    report = run_checks(load_task(result.root))
    assert report.errors == [], [item.message for item in report.errors]
    assert report.warnings == []


def test_scaffolded_instruction_and_tests_are_consistent(tmp_path: Path) -> None:
    result = scaffold_task(tmp_path / "exam_003", "exam_003", author="tester")
    task = load_task(result.root)
    assert "/output/report.txt" in task.instruction
    assert "/output/report.txt" in task.verifier_source


def test_scaffold_refuses_existing_directory(tmp_path: Path) -> None:
    target = tmp_path / "exam_004"
    target.mkdir()
    (target / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scaffold_task(target, "exam_004")


def test_scaffold_overwrite_allows_existing_directory(tmp_path: Path) -> None:
    target = tmp_path / "exam_005"
    target.mkdir()
    (target / "keep.txt").write_text("x", encoding="utf-8")
    result = scaffold_task(target, "exam_005", overwrite=True)
    assert (result.root / "task.toml").is_file()
    assert (target / "keep.txt").is_file()


def test_scaffold_task_toml_is_valid(tmp_path: Path) -> None:
    result = scaffold_task(
        tmp_path / "exam_006",
        "exam_006",
        title="自定义题目",
        description="用于验证元数据渲染的自定义题目。",
        difficulty="medium",
        tags=("custom", "unit-test"),
        log_lines=16,
    )
    task = load_task(result.root)
    assert task.name == "harbor/exam-006"
    assert task.difficulty == "medium"
    assert task.tags == ("custom", "unit-test")
    assert "自定义题目" in task.instruction


def test_next_task_id(tmp_path: Path) -> None:
    assert next_task_id(tmp_path) == "exam_001"
    (tmp_path / "exam_001").mkdir()
    (tmp_path / "exam_007").mkdir()
    (tmp_path / "other").mkdir()
    assert next_task_id(tmp_path) == "exam_008"
    assert next_task_id(tmp_path, prefix="task") == "task_001"


def test_render_replaces_placeholders() -> None:
    assert render("a={{x}} b={{ y }}", x="1") == "a=1 b={{ y }}"
    assert render("{{x}}/{{x}}", x="1") == "1/1"


def test_scaffold_log_seed_controls_sample(tmp_path: Path) -> None:
    first = scaffold_task(tmp_path / "exam_010", "exam_010", seed=1)
    second = scaffold_task(tmp_path / "exam_011", "exam_011", seed=2)
    log_a = (first.root / "environment/access.log").read_text(encoding="utf-8")
    log_b = (second.root / "environment/access.log").read_text(encoding="utf-8")
    assert log_a != log_b
