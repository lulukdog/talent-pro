"""题目目录解析与路径抽取的测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from talentpro.spec import (
    TaskFormatError,
    extract_absolute_paths,
    extract_container_paths,
    fenced_blocks,
    iter_text_files,
    load_task,
)


def test_load_task_reads_all_parts(task) -> None:
    assert task.has_config
    assert task.version == "1.0"
    assert task.name == "harbor/exam-777"
    assert task.slug == "exam-777"
    assert task.difficulty == "easy"
    assert task.author_name == "tester"
    assert task.tags == ("log-analysis", "shell", "file-processing")
    assert task.allow_internet is True
    assert task.dockerfile and "FROM ubuntu" in task.dockerfile
    assert task.solve_sh and task.solve_sh.startswith("#!/bin/bash")
    assert "test_state.py" in task.test_sources


def test_load_task_all_sources_keys(task) -> None:
    sources = task.all_sources
    assert set(sources) == {
        "instruction.md",
        "environment/Dockerfile",
        "solution/solve.sh",
        "tests/test.sh",
        "tests/test_state.py",
    }


def test_declared_output_and_input_paths(task) -> None:
    assert task.declared_output_paths() == {"/output/report.txt"}
    assert task.instruction_input_paths() == {"/data/access.log"}


def test_load_task_missing_config(tmp_path: Path) -> None:
    with pytest.raises(TaskFormatError, match="task.toml"):
        load_task(tmp_path)


def test_load_task_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(TaskFormatError, match="不存在"):
        load_task(tmp_path / "nope")


def test_load_task_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "task.toml").write_text("version = [", encoding="utf-8")
    with pytest.raises(TaskFormatError, match="解析失败"):
        load_task(tmp_path)


def test_load_task_tolerates_missing_optional_files(tmp_path: Path) -> None:
    (tmp_path / "task.toml").write_text('version = "1.0"\n', encoding="utf-8")
    task = load_task(tmp_path)
    assert task.instruction == ""
    assert task.dockerfile is None
    assert task.test_sources == {}
    assert task.environment_files == ()


def test_extract_absolute_paths_ignores_urls() -> None:
    text = "见 https://example.com/a/b 与 /output/report.txt，还有 /data/access.log"
    assert extract_absolute_paths(text) == {"/output/report.txt", "/data/access.log"}


def test_extract_container_paths_filters_api_routes() -> None:
    text = '输入 /data/access.log；示例 "GET /api/users HTTP/1.1"；产出 /output/report.txt'
    assert extract_container_paths(text) == {"/data/access.log", "/output/report.txt"}


def test_fenced_blocks_extracts_code() -> None:
    text = "前言\n```bash\necho hi\n```\n中间\n```\nraw\n```\n"
    assert fenced_blocks(text) == ["echo hi\n", "raw\n"]


def test_iter_text_files_skips_binary_and_hidden_dirs(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "b.png").write_bytes(b"\x89PNG")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "c.py").write_text("x", encoding="utf-8")
    names = [name for name, _ in iter_text_files(tmp_path)]
    assert names == ["a.py"]


def test_iter_text_files_skips_large_files(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("x" * (600 * 1024), encoding="utf-8")
    assert list(iter_text_files(tmp_path)) == []
