"""提交历史读取与提交说明质量评估的测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from talentpro.gitlog import (
    FIELD_SEP,
    RECORD_SEP,
    Commit,
    GitError,
    assess_messages,
    chronological,
    history_summary,
    parse_conventional,
    parse_git_log,
    read_commits,
)


def make_commit(subject: str, sha: str = "a" * 40, offset: int = 0) -> Commit:
    return Commit(
        sha=sha,
        short_sha=sha[:7],
        author="tester",
        email="tester@example.com",
        date=datetime(2024, 1, 1) + timedelta(minutes=offset),
        subject=subject,
        body="",
    )


def test_read_commits_newest_first(git_repo: Path) -> None:
    commits = read_commits(git_repo)
    assert [commit.subject for commit in commits][0] == "docs: 补充使用说明"
    assert len(commits) == 4


def test_read_commits_limit(git_repo: Path) -> None:
    assert len(read_commits(git_repo, limit=2)) == 2


def test_read_commits_parses_metadata(git_repo: Path) -> None:
    commit = read_commits(git_repo)[-1]
    assert commit.author == "tester"
    assert commit.email == "tester@example.com"
    assert len(commit.sha) == 40
    assert commit.short_sha == commit.sha[:7]


def test_read_commits_outside_repository_raises(tmp_path: Path) -> None:
    with pytest.raises(GitError):
        read_commits(tmp_path)


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("feat(spec): 解析题目", ("feat", "spec")),
        ("fix: 修正统计", ("fix", None)),
        ("chore(deps)!: 升级依赖", ("chore", "deps")),
        ("随便写点什么", (None, None)),
        ("unknown(x): 非法类型", (None, None)),
    ],
)
def test_parse_conventional(subject: str, expected: tuple[str | None, str | None]) -> None:
    assert parse_conventional(subject) == expected


def test_assess_messages_flags_vague_subjects() -> None:
    quality = assess_messages([make_commit("update"), make_commit("feat: 正常提交")])
    assert quality.vague == ("update",)
    assert quality.prefix_coverage == 0.5
    assert quality.issues()


def test_assess_messages_flags_long_subject() -> None:
    quality = assess_messages([make_commit("feat: " + "很长" * 60)])
    assert quality.long_subjects


def test_assess_messages_score_bounds() -> None:
    assert assess_messages([]).score == 0.0
    perfect = assess_messages([make_commit("feat(spec): 增加解析")])
    assert 0 < perfect.score <= 1


def test_assess_messages_detects_empty_bodies() -> None:
    quality = assess_messages([make_commit("feat: x")])
    assert quality.empty_bodies == 1


def test_chronological_reverses() -> None:
    commits = [make_commit("feat: b", offset=1), make_commit("feat: a")]
    assert [c.subject for c in chronological(commits)] == ["feat: a", "feat: b"]


def test_parse_git_log_handles_multiline_body() -> None:
    record = FIELD_SEP.join(
        ["b" * 40, "bbbbbbb", "tester", "t@example.com", "2024-01-01T00:00:00+00:00", "feat: x", "第一行\n第二行"]
    )
    commits = parse_git_log(record + RECORD_SEP)
    assert len(commits) == 1
    assert commits[0].body == "第一行\n第二行"
    assert commits[0].date == datetime.fromisoformat("2024-01-01T00:00:00+00:00")


def test_parse_git_log_ignores_incomplete_records() -> None:
    assert parse_git_log("只有两个字段" + FIELD_SEP + "x") == []


def test_commit_type_and_scope_properties() -> None:
    commit = make_commit("docs(readme): 补充说明")
    assert commit.type == "docs"
    assert commit.scope == "readme"


def test_history_summary(git_repo: Path) -> None:
    summary = history_summary(git_repo)
    assert summary["commits"] == 4
    assert summary["authors"] == ["tester"]
    assert summary["first_commit"] <= summary["last_commit"]
    assert "quality" in summary
