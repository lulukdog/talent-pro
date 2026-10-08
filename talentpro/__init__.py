"""talent-pro：考核题库开发工具链。

公开 API::

    from talentpro import load_task, analyze_log_text, render_report

子命令入口见 :mod:`talentpro.cli`。
"""

from __future__ import annotations

from .models import Analysis, CheckReport, Mismatch, RuleResult, Severity
from .report import (
    REPORT_SECTIONS,
    LogEntry,
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
from .spec import (
    TASK_CONFIG_FILE,
    TaskFormatError,
    TaskSpec,
    extract_absolute_paths,
    extract_container_paths,
    fenced_blocks,
    iter_text_files,
    load_task,
)

__version__ = "0.1.0"

__all__ = [
    "REPORT_SECTIONS",
    "TASK_CONFIG_FILE",
    "Analysis",
    "CheckReport",
    "LogEntry",
    "LogFormatError",
    "Mismatch",
    "RuleResult",
    "Severity",
    "TaskFormatError",
    "TaskSpec",
    "__version__",
    "analyze",
    "analyze_log_text",
    "compare_reports",
    "extract_absolute_paths",
    "extract_container_paths",
    "fenced_blocks",
    "iter_text_files",
    "load_log",
    "load_task",
    "parse_line",
    "parse_log",
    "parse_report",
    "render_report",
]
