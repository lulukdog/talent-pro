"""访问日志解析、统计与报告比对的测试。"""

from __future__ import annotations

import pytest

from talentpro.models import Mismatch
from talentpro.report import (
    LogFormatError,
    analyze,
    analyze_log_text,
    compare_reports,
    load_log,
    parse_line,
    parse_log,
    parse_report,
    render_report,
)

VALID_LINE = (
    '10.0.0.1 - - [01/Jan/2024:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234'
)


def test_parse_line_extracts_fields() -> None:
    entry = parse_line(VALID_LINE)
    assert entry.ip == "10.0.0.1"
    assert entry.method == "GET"
    assert entry.path == "/api/users"
    assert entry.protocol == "HTTP/1.1"
    assert entry.status == "200"
    assert entry.size == 1234
    assert entry.request_line == "GET /api/users HTTP/1.1"


def test_parse_line_accepts_missing_size() -> None:
    entry = parse_line(VALID_LINE.replace("200 1234", "204 -"))
    assert entry.size is None


@pytest.mark.parametrize(
    "line",
    [
        "",
        "not a log line",
        '10.0.0.1 - - [01/Jan/2024:10:00:00 +0000] "GET /api/users" 200 1',
        '10.0.0.1 - - 01/Jan/2024 "GET /api/users HTTP/1.1" 200 1',
        '10.0.0.1 - - [01/Jan/2024:10:00:00 +0000] "GET /api/users HTTP/1.1" 20 1',
    ],
)
def test_parse_line_rejects_malformed(line: str) -> None:
    with pytest.raises(LogFormatError):
        parse_line(line, line_no=3)


def test_log_format_error_mentions_line_number() -> None:
    with pytest.raises(LogFormatError) as excinfo:
        parse_line("bad", line_no=7)
    assert "第 7 行" in str(excinfo.value)
    assert excinfo.value.line_no == 7


def test_parse_log_skips_blank_lines(sample_log: str) -> None:
    entries = parse_log(sample_log)
    assert len(entries) == 5


def test_analyze_counts_and_top_ip(sample_log: str) -> None:
    analysis = analyze_log_text(sample_log)
    assert analysis.total_requests == 5
    assert analysis.ip_counts == {"10.0.0.1": 3, "10.0.0.2": 1, "10.0.0.3": 1}
    assert analysis.status_counts == {"200": 2, "401": 1, "404": 1, "500": 1}
    assert (analysis.top_ip, analysis.top_count) == ("10.0.0.1", 3)


def test_analyze_tie_break_uses_smallest_ip() -> None:
    text = "\n".join(
        [
            '10.0.0.9 - - [01/Jan/2024:10:00:00 +0000] "GET /a HTTP/1.1" 200 1',
            '10.0.0.2 - - [01/Jan/2024:10:00:01 +0000] "GET /a HTTP/1.1" 200 1',
        ]
    )
    analysis = analyze_log_text(text)
    assert analysis.top_ip == "10.0.0.2"
    assert analysis.top_count == 1


def test_analyze_empty_raises() -> None:
    with pytest.raises(ValueError, match="日志为空"):
        analyze([])


def test_render_report_matches_contract(sample_log: str) -> None:
    report = render_report(analyze_log_text(sample_log))
    assert report == (
        "=== Top IP ===\n"
        "10.0.0.1: 3 requests\n"
        "\n"
        "=== Status Code Distribution ===\n"
        "200: 2\n"
        "401: 1\n"
        "404: 1\n"
        "500: 1\n"
        "\n"
        "=== Requests per IP ===\n"
        "10.0.0.1: 3\n"
        "10.0.0.2: 1\n"
        "10.0.0.3: 1\n"
    )


def test_report_roundtrip(sample_log: str) -> None:
    report = render_report(analyze_log_text(sample_log))
    sections = parse_report(report)
    assert list(sections) == ["Top IP", "Status Code Distribution", "Requests per IP"]
    assert sections["Top IP"] == ["10.0.0.1: 3 requests"]
    assert sections["Requests per IP"] == ["10.0.0.1: 3", "10.0.0.2: 1", "10.0.0.3: 1"]


def test_compare_reports_identical(sample_log: str) -> None:
    report = render_report(analyze_log_text(sample_log))
    assert compare_reports(report, report) == []


def test_compare_reports_detects_wrong_count(sample_log: str) -> None:
    expected = render_report(analyze_log_text(sample_log))
    actual = expected.replace("10.0.0.1: 3\n10.0.0.2: 1", "10.0.0.1: 2\n10.0.0.2: 1")
    mismatches = compare_reports(expected, actual)
    assert Mismatch("missing_line", "Requests per IP", "10.0.0.1: 3") in mismatches


def test_compare_reports_detects_missing_section(sample_log: str) -> None:
    expected = render_report(analyze_log_text(sample_log))
    actual = "=== Top IP ===\n10.0.0.1: 3 requests\n"
    kinds = {mismatch.kind for mismatch in compare_reports(expected, actual)}
    assert "missing_section" in kinds


def test_compare_reports_reports_extra_section(sample_log: str) -> None:
    expected = render_report(analyze_log_text(sample_log))
    mismatches = compare_reports(expected, expected + "\n=== Extra ===\nfoo: 1\n")
    assert any(item.kind == "extra_line" and item.section == "Extra" for item in mismatches)


def test_mismatch_describe_is_human_readable() -> None:
    assert "缺少区块" in Mismatch("missing_section", "Top IP").describe()
    assert "Top IP" in Mismatch("missing_line", "Top IP", "x: 1").describe()


def test_load_log_reads_file(log_file) -> None:
    entries = load_log(log_file)
    assert len(entries) == 5
    assert entries[0].ip == "10.0.0.1"
