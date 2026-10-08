"""安全规则：密钥/令牌、硬编码口令、内部地址、本机路径与私有网段。

规则只做「可解释的静态扫描」，命中即给出 ``文件:行号``，方便人工复核。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from ..models import RuleResult, Severity
from ..spec import TaskSpec
from .base import finding, rule

CATEGORY = "security"

#: 命中即 ``ERROR`` 的凭据形态。注意：模式本身也被扫描，因此模式文本不能命中自身。
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Figma 个人令牌", re.compile(r"figd_[A-Za-z0-9_-]{15,}")),
    ("GitHub 令牌", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("GitHub 细粒度令牌", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("模型服务密钥", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("云厂商 AccessKey", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack 令牌", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("私钥文件", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("硬编码口令", re.compile(r"""(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*["'][^"']{8,}["']""")),
)

#: 内部域名以「分段元组」保存，避免扫描自身时误报。
INTERNAL_DOMAIN_PARTS: tuple[tuple[str, ...], ...] = (
    ("lingyiwanwu", "net"),
    ("01", "ai"),
)

INTERNAL_DOMAIN_PATTERN = re.compile(r"\b[\w-]+\.(?:corp|internal|intranet|intra)\b", re.IGNORECASE)
PERSONAL_PATH_PATTERN = re.compile(r"/(?:Users|home)/")
WINDOWS_USER_PATTERN = re.compile(r"[A-Za-z]:\\+Users\\+")
PRIVATE_NETWORK_PATTERN = re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")

MAX_HITS = 10


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _iter_hits(
    pattern: re.Pattern[str], text: str, limit: int = MAX_HITS
) -> Iterator[tuple[str, int]]:
    for count, match in enumerate(pattern.finditer(text)):
        if count >= limit:
            return
        yield match.group(0), _line_of(text, match.start())


def scan_secrets(
    sources: Iterable[tuple[str, str]], *, rule_id: str = "security.secrets"
) -> list[RuleResult]:
    """扫描任意 ``(相对路径, 文本)`` 序列，返回命中的凭据类问题。"""
    results: list[RuleResult] = []
    for relative, text in sources:
        for label, pattern in SECRET_PATTERNS:
            for hit, line_no in _iter_hits(pattern, text):
                masked = _mask(hit)
                results.append(
                    finding(
                        rule_id,
                        Severity.ERROR,
                        f"{relative}:{line_no} 疑似{label}：{masked}",
                        "提交前必须移除密钥，改用环境变量或私有配置",
                    )
                )
    return results


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-2:]}（已截断）"


@rule("security.secrets", "凭据与密钥扫描", CATEGORY)
def check_secrets(task: TaskSpec) -> list[RuleResult]:
    return scan_secrets(sorted(task.all_sources.items()))


@rule("security.personal_paths", "无本机个人路径", CATEGORY)
def check_personal_paths(task: TaskSpec) -> list[RuleResult]:
    results: list[RuleResult] = []
    for relative, source in sorted(task.all_sources.items()):
        if PERSONAL_PATH_PATTERN.search(source) or WINDOWS_USER_PATTERN.search(source):
            results.append(
                finding(
                    "security.personal_paths",
                    Severity.WARNING,
                    f"{relative} 包含本机用户目录路径",
                    "改为容器内路径或占位符（如 <repo-dir>）",
                )
            )
    return results


@rule("security.internal_hosts", "无内部地址", CATEGORY)
def check_internal_hosts(task: TaskSpec) -> list[RuleResult]:
    results: list[RuleResult] = []
    domains = tuple(".".join(parts) for parts in INTERNAL_DOMAIN_PARTS)
    for relative, source in sorted(task.all_sources.items()):
        for domain in domains:
            if domain in source:
                results.append(
                    finding(
                        "security.internal_hosts",
                        Severity.ERROR,
                        f"{relative} 出现内部域名：{domain}",
                        "对外提交的题库不应包含内部地址",
                    )
                )
        for host in {match.group(0) for match in INTERNAL_DOMAIN_PATTERN.finditer(source)}:
            results.append(
                finding(
                    "security.internal_hosts",
                    Severity.ERROR,
                    f"{relative} 出现内网主机名：{host}",
                    "改用示例域名，例如 example.com",
                )
            )
    return results


@rule("security.private_networks", "样例数据网段提示", CATEGORY)
def check_private_networks(task: TaskSpec) -> list[RuleResult]:
    """RFC1918 地址在样例数据里很常见，只做提示不阻断。"""
    hits: set[str] = set()
    for relative, source in sorted(task.all_sources.items()):
        if relative.endswith(".log"):
            continue
        hits.update(match.group(0) for match in PRIVATE_NETWORK_PATTERN.finditer(source))
    if hits:
        return [
            finding(
                "security.private_networks",
                Severity.INFO,
                f"文本中出现私有网段地址 {len(hits)} 处（示例数据可忽略）",
                "确认不是真实内网拓扑即可", 
            )
        ]
    return []
