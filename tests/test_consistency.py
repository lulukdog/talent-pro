"""一致性规则的测试。"""

from __future__ import annotations

import shutil
from pathlib import Path

from talentpro.spec import load_task
from talentpro.validators import run_checks
from talentpro.validators.consistency import path_covered


def copy_task(source: Path, target_dir: Path) -> Path:
    destination = target_dir / "copy" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination


def test_path_covered_accepts_literal() -> None:
    assert path_covered("/output/report.txt", "cat /output/report.txt")


def test_path_covered_accepts_concatenation() -> None:
    text = 'OUT_DIR="/output"\nOUT="${OUT_DIR}/report.txt"\n'
    assert path_covered("/output/report.txt", text)


def test_path_covered_rejects_unrelated_text() -> None:
    assert not path_covered("/output/report.txt", "cat /tmp/other.txt")


def test_output_path_missing_in_verifier(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    test_file = task_root / "tests/test_state.py"
    test_file.write_text(
        test_file.read_text(encoding="utf-8").replace("/output/report.txt", "/output/summary.txt"),
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "consistency.output_paths" in report.failed_rule_ids


def test_solution_not_writing_output(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    solve = task_root / "solution/solve.sh"
    solve.write_text(
        solve.read_text(encoding="utf-8").replace("OUT_DIR=\"/output\"", "OUT_DIR=\"/tmp\""),
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "consistency.solution_outputs" in report.failed_rule_ids


def test_dockerfile_copy_source_missing(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    dockerfile = task_root / "environment/Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8").replace("COPY access.log", "COPY missing.log"),
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "consistency.dockerfile_sources" in report.failed_rule_ids


def test_declared_input_not_referenced(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    instruction = task_root / "instruction.md"
    instruction.write_text(
        instruction.read_text(encoding="utf-8") + "\n另见 `/data/missing.log`。\n",
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "consistency.input_paths" in {item.rule_id for item in report.warnings}


def test_personal_absolute_path_rejected(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    instruction = task_root / "instruction.md"
    instruction.write_text(
        instruction.read_text(encoding="utf-8").replace(
            "/data/access.log", "/Users/someone/project/access.log"
        ),
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "consistency.absolute_paths" in report.failed_rule_ids
