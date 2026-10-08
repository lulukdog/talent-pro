"""提交历史读取与提交说明质量评估。

平台的「Repo 质量检查」会看提交说明质量，本模块把这件事变成可计算指标：
约定式提交前缀覆盖率、主题长度、含糊主题占比等。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

#: 约定式提交：``type(scope)!: subject``
CONVENTIONAL_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<subject>.+)$"
)

VALID_TYPES = ("feat", "fix", "docs", "test", "chore", "refactor", "perf", "style", "build", "ci", "revert")

#: 看不出改了什么含糊主题。
VAGUE_SUBJECTS = frozenset(
    {
        "update",
        "updates",
        "fix",
        "fixes",
        "wip",
        "init",
        "initial commit",
        "changes",
        "misc",
        "tmp",
        "temp",
        "test",
        "save",
        "修改",
        "更新",
        "提交",
        "修复",
        "保存",
        "补充",
    }
)

MAX_SUBJECT_LENGTH = 72

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"


class GitError(RuntimeError):
    """调用 git 失败。"""


@dataclass(frozen=True)
class Commit:
    """一条提交记录。"""

    sha: str
    short_sha: str
    author: str
    email: str
    date: datetime
    subject: str
    body: str

    @property
    def type(self) -> str | None:
        return parse_conventional(self.subject)[0]

    @property
    def scope(self) -> str | None:
        return parse_conventional(self.subject)[1]

    @property
    def subject_length(self) -> int:
        return len(self.subject)

    @property
    def is_vague(self) -> bool:
        return self.subject.strip().lower().rstrip("。.") in VAGUE_SUBJECTS

    def to_dict(self) -> dict[str, object]:
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "author": self.author,
            "date": self.date.isoformat(),
            "subject": self.subject,
            "type": self.type,
            "scope": self.scope,
        }


@dataclass(frozen=True)
class MessageQuality:
    """提交说明质量统计。"""

    total: int
    conventional: int
    vague: tuple[str, ...]
    long_subjects: tuple[str, ...]
    empty_bodies: int

    @property
    def prefix_coverage(self) -> float:
        return self.conventional / self.total if self.total else 0.0

    @property
    def vague_ratio(self) -> float:
        return len(self.vague) / self.total if self.total else 0.0

    @property
    def long_ratio(self) -> float:
        return len(self.long_subjects) / self.total if self.total else 0.0

    @property
    def score(self) -> float:
        """0~1 区间综合分，便于在 CI 中设置阈值。"""
        if not self.total:
            return 0.0
        return round(
            0.4 * self.prefix_coverage + 0.4 * (1 - self.vague_ratio) + 0.2 * (1 - self.long_ratio),
            3,
        )

    def issues(self) -> list[str]:
        problems: list[str] = []
        if self.vague:
            problems.append(f"{len(self.vague)} 条提交主题过于含糊：{', '.join(self.vague[:3])}")
        if self.long_subjects:
            problems.append(f"{len(self.long_subjects)} 条主题超过 {MAX_SUBJECT_LENGTH} 字符")
        if self.prefix_coverage < 0.5:
            problems.append(f"约定式提交前缀覆盖率仅 {self.prefix_coverage:.0%}")
        return problems

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "conventional": self.conventional,
            "prefix_coverage": round(self.prefix_coverage, 3),
            "vague": list(self.vague),
            "long_subjects": list(self.long_subjects),
            "empty_bodies": self.empty_bodies,
            "score": self.score,
            "issues": self.issues(),
        }


def parse_conventional(subject: str) -> tuple[str | None, str | None]:
    """解析约定式提交前缀，返回 ``(type, scope)``；不符合约定时返回 ``(None, None)``。"""
    match = CONVENTIONAL_PATTERN.match(subject.strip())
    if match is None:
        return None, None
    commit_type = match.group("type")
    if commit_type not in VALID_TYPES:
        return None, None
    return commit_type, match.group("scope")


def read_commits(path: str | Path = ".", ref: str | None = None, limit: int | None = None) -> list[Commit]:
    """读取提交历史，**按时间倒序**（最新在前），与 ``git log`` 一致。

    Raises:
        GitError: 目录不是 git 仓库，或 git 命令执行失败。
    """
    repo = Path(path).expanduser()
    pretty = FIELD_SEP.join(["%H", "%h", "%an", "%ae", "%aI", "%s", "%b"]) + RECORD_SEP
    command = ["git", "-C", str(repo), "log", f"--pretty=format:{pretty}"]
    if limit is not None:
        command.append(f"-n{limit}")
    if ref:
        command.append(ref)

    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:  # pragma: no cover - 环境缺少 git
        raise GitError("未找到 git 可执行文件") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise GitError(f"git log 执行失败：{message}")

    return parse_git_log(completed.stdout)


def parse_git_log(output: str) -> list[Commit]:
    """解析 ``git log --pretty=format:`` 的输出。"""
    commits: list[Commit] = []
    for record in output.split(RECORD_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        fields = record.split(FIELD_SEP)
        if len(fields) < 6:
            continue
        sha, short_sha, author, email, date_text, subject = fields[:6]
        body = fields[6] if len(fields) > 6 else ""
        try:
            date = datetime.fromisoformat(date_text)
        except ValueError:
            date = datetime.fromtimestamp(0)
        commits.append(
            Commit(
                sha=sha,
                short_sha=short_sha,
                author=author,
                email=email,
                date=date,
                subject=subject.strip(),
                body=body.strip(),
            )
        )
    return commits


def chronological(commits: list[Commit]) -> list[Commit]:
    """把倒序提交列表转成时间正序（最早在前）。"""
    return list(reversed(commits))


def assess_messages(commits: list[Commit]) -> MessageQuality:
    """统计提交说明质量。"""
    vague = tuple(c.subject for c in commits if c.is_vague)
    long_subjects = tuple(c.subject for c in commits if c.subject_length > MAX_SUBJECT_LENGTH)
    conventional = sum(1 for c in commits if parse_conventional(c.subject)[0] is not None)
    empty_bodies = sum(1 for c in commits if not c.body)
    return MessageQuality(
        total=len(commits),
        conventional=conventional,
        vague=vague,
        long_subjects=long_subjects,
        empty_bodies=empty_bodies,
    )


def history_summary(path: str | Path = ".", ref: str | None = None) -> dict[str, object]:
    """汇总仓库历史概况：提交数、作者数、时间跨度与质量分。"""
    commits = read_commits(path, ref)
    quality = assess_messages(commits)
    dates = [c.date for c in commits]
    authors = {c.author for c in commits}
    return {
        "commits": len(commits),
        "authors": sorted(authors),
        "first_commit": min(dates).isoformat() if dates else None,
        "last_commit": max(dates).isoformat() if dates else None,
        "quality": quality.to_dict(),
    }
