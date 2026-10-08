"""访问日志解析、统计与 ``report.txt`` 的生成 / 解析 / 比对。

题目侧的 ``/output/report.txt`` 由考生脚本产出，判卷侧需要独立地根据原始日志
重算真值。本模块同时服务这两个方向：

* 生成：``analyze`` → ``render_report``（等价于参考解的语义）
* 校验：``parse_report`` → ``compare_reports``（等价于判卷断言）
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .models import Analysis, Mismatch

#: Nginx / Apache common log 的一行。
LOG_PATTERN = re.compile(
    r"^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+"
    r'"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)\s*$'
)

#: 双引号内的请求行。
REQUEST_PATTERN = re.compile(
    r"^(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+(?P<protocol>[A-Z]+/\d(?:\.\d)?)$"
)

#: 报告区块标题，例如 ``=== Top IP ===``。
SECTION_PATTERN = re.compile(r"^===\s*(?P<title>.*?)\s*===$")

SECTION_TOP_IP = "Top IP"
SECTION_STATUS_CODES = "Status Code Distribution"
SECTION_REQUESTS_PER_IP = "Requests per IP"

#: 标准题库模板要求的区块顺序。
REPORT_SECTIONS = (SECTION_TOP_IP, SECTION_STATUS_CODES, SECTION_REQUESTS_PER_IP)


class LogFormatError(ValueError):
    """日志行不符合预期格式。"""

    def __init__(self, line: str, line_no: int | None = None) -> None:
        where = f"第 {line_no} 行" if line_no is not None else "日志行"
        super().__init__(f"{where} 格式不正确: {line!r}")
        self.line = line
        self.line_no = line_no


@dataclass(frozen=True)
class LogEntry:
    """一条解析后的日志记录。"""

    ip: str
    time: str
    method: str
    path: str
    protocol: str
    status: str
    size: int | None

    @property
    def request_line(self) -> str:
        return f"{self.method} {self.path} {self.protocol}"

    def to_dict(self) -> dict[str, object]:
        return {
            "ip": self.ip,
            "time": self.time,
            "method": self.method,
            "path": self.path,
            "protocol": self.protocol,
            "status": self.status,
            "size": self.size,
        }


def parse_line(line: str, line_no: int | None = None) -> LogEntry:
    """解析单行日志；格式不符时抛出 :class:`LogFormatError`。"""
    match = LOG_PATTERN.match(line.strip())
    if match is None:
        raise LogFormatError(line, line_no)

    request = match.group("request")
    request_match = REQUEST_PATTERN.match(request)
    if request_match is None:
        raise LogFormatError(line, line_no)

    raw_size = match.group("size")
    size = int(raw_size) if raw_size.isdigit() else None

    return LogEntry(
        ip=match.group("ip"),
        time=match.group("time"),
        method=request_match.group("method"),
        path=request_match.group("path"),
        protocol=request_match.group("protocol"),
        status=match.group("status"),
        size=size,
    )


def parse_log(text: str) -> list[LogEntry]:
    """解析整份日志文本，自动跳过空行。"""
    entries: list[LogEntry] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        entries.append(parse_line(raw, line_no))
    return entries


def load_log(path: str | Path) -> list[LogEntry]:
    """读取并解析日志文件。"""
    return parse_log(Path(path).read_text(encoding="utf-8", errors="replace"))


def analyze(entries: Sequence[LogEntry]) -> Analysis:
    """统计每 IP 请求数、状态码分布与 Top IP。

    Top IP 的并列情况按 IP 字典序取最小，保证结果稳定可复现。
    """
    if not entries:
        raise ValueError("日志为空，无法统计")

    ip_counts = Counter(entry.ip for entry in entries)
    status_counts = Counter(entry.status for entry in entries)
    top_ip, top_count = min(ip_counts.items(), key=lambda item: (-item[1], item[0]))

    return Analysis(
        ip_counts=dict(sorted(ip_counts.items(), key=lambda item: (-item[1], item[0]))),
        status_counts=dict(sorted(status_counts.items())),
        top_ip=top_ip,
        top_count=top_count,
    )


def analyze_log_text(text: str) -> Analysis:
    """一步完成「解析 + 统计」。"""
    return analyze(parse_log(text))


def render_report(analysis: Analysis) -> str:
    """按题库统一格式渲染报告文本。"""
    lines: list[str] = [
        f"=== {SECTION_TOP_IP} ===",
        f"{analysis.top_ip}: {analysis.top_count} requests",
        "",
        f"=== {SECTION_STATUS_CODES} ===",
    ]
    lines.extend(f"{code}: {analysis.status_counts[code]}" for code in sorted(analysis.status_counts))
    lines.append("")
    lines.append(f"=== {SECTION_REQUESTS_PER_IP} ===")
    lines.extend(
        f"{ip}: {count}"
        for ip, count in sorted(analysis.ip_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    return "\n".join(lines) + "\n"


def parse_report(text: str) -> dict[str, list[str]]:
    """把报告文本切成 ``{区块标题: [行, ...]}``。"""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        match = SECTION_PATTERN.match(stripped)
        if match is not None:
            current = match.group("title")
            sections[current] = []
        elif current is not None and stripped:
            sections[current].append(stripped)
    return sections


def compare_reports(expected: str, actual: str) -> list[Mismatch]:
    """逐区块比较两份报告，返回全部差异。"""
    expected_sections = parse_report(expected)
    actual_sections = parse_report(actual)

    mismatches: list[Mismatch] = []
    for section, expected_lines in expected_sections.items():
        if section not in actual_sections:
            mismatches.append(Mismatch("missing_section", section))
            continue

        expected_counter = Counter(expected_lines)
        actual_counter = Counter(actual_sections[section])
        for line in (expected_counter - actual_counter).elements():
            mismatches.append(Mismatch("missing_line", section, line))
        for line in (actual_counter - expected_counter).elements():
            mismatches.append(Mismatch("extra_line", section, line))

    for section in actual_sections:
        if section not in expected_sections:
            mismatches.append(Mismatch("extra_line", section, f"=== {section} ==="))

    return mismatches
