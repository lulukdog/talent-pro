"""公共测试夹具。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from talentpro.scaffold import scaffold_task
from talentpro.spec import TaskSpec, load_task

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 覆盖 4 个 IP、5 种状态码，且 Top IP 唯一。
SAMPLE_LOG = """\
10.0.0.1 - - [01/Jan/2024:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234
10.0.0.2 - - [01/Jan/2024:10:00:01 +0000] "POST /api/login HTTP/1.1" 401 56
10.0.0.1 - - [01/Jan/2024:10:00:02 +0000] "GET /api/orders HTTP/1.1" 200 5678
10.0.0.3 - - [01/Jan/2024:10:00:03 +0000] "GET /health HTTP/1.1" 404 -

10.0.0.1 - - [01/Jan/2024:10:00:04 +0000] "GET /api/users HTTP/1.1" 500 12
"""

SAMPLE_LOG_SHA = "10.0.0.1"


@pytest.fixture
def sample_log() -> str:
    return SAMPLE_LOG


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "access.log"
    path.write_text(SAMPLE_LOG, encoding="utf-8")
    return path


@pytest.fixture
def sample_task(tmp_path: Path) -> Path:
    """一个由脚手架生成、可直接通过校验的题目目录。"""
    return scaffold_task(tmp_path / "exam_777", "exam_777", author="tester").root


@pytest.fixture
def task(sample_task: Path) -> TaskSpec:
    return load_task(sample_task)


def git(repo: Path, *args: str) -> str:
    """在临时仓库里执行 git 命令。"""
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} 失败：{completed.stderr.strip()}")
    return completed.stdout


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """包含 4 条约定式提交的临时仓库。"""
    repo = tmp_path / "history"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "tester")
    git(repo, "config", "user.email", "tester@example.com")
    git(repo, "config", "commit.gpgsign", "false")

    subjects = (
        "chore: 初始化仓库骨架",
        "feat(spec): 增加题目目录解析",
        "test(spec): 补齐解析用例",
        "docs: 补充使用说明",
    )
    for index, subject in enumerate(subjects):
        (repo / "file.txt").write_text(f"{index}\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "--no-verify", "-m", subject)
    return repo
