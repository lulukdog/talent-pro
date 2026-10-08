"""仓库级规则：项目骨架、README 与代码一致性、测试与文档完备度。

与题目级规则不同，这里的输入是整个仓库根目录，对应平台的「Repo 质量检查」。
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable
from pathlib import Path

from ..models import CheckReport, RuleResult, Severity
from ..spec import SKIP_DIRS, iter_text_files
from .base import finding
from .security import scan_secrets

CATEGORY = "repo"

#: README 应覆盖的语义区块。
README_SECTIONS: dict[str, tuple[str, ...]] = {
    "项目简介": ("简介", "概述", "introduction", "overview", "about"),
    "安装": ("安装", "install", "快速开始", "quick start", "quickstart"),
    "使用": ("使用", "用法", "usage", "命令", "cli"),
    "目录结构": ("目录结构", "结构", "structure", "layout"),
    "开发与测试": ("开发", "测试", "test", "development", "contributing"),
    "许可证": ("license", "许可"),
}

MODULE_REF_PATTERN = re.compile(r"\btalentpro(?:\.[a-z_][\w]*)+")
FILE_REF_PATTERN = re.compile(r"`([\w./-]+\.(?:py|md|toml|sh|yml|yaml))`")
DOCS_LINK_PATTERN = re.compile(r"docs/[\w.-]+\.md")

MIN_README_CHARS = 1200
MIN_MODULES = 6
MIN_TEST_MODULES = 3
MIN_TEST_FUNCTIONS = 15
MAX_REPO_FILE_BYTES = 2 * 1024 * 1024

ARTIFACT_SUFFIXES = (".pyc", ".orig", ".rej", ".bak")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _project_config(root: Path) -> dict:
    try:
        return tomllib.loads(_read(root / "pyproject.toml"))
    except tomllib.TOMLDecodeError:
        return {}


def _module_exists(root: Path, dotted: str) -> bool:
    parts = dotted.split(".")
    for size in range(len(parts), 1, -1):
        candidate = root.joinpath(*parts[:size])
        if candidate.with_suffix(".py").is_file() or (candidate / "__init__.py").is_file():
            return True
    return False


def _repo_root(task_root: Path) -> Path:
    return task_root


RepoRule = Callable[[Path], list[RuleResult]]


def _rule_readme_present(root: Path) -> list[RuleResult]:
    readme = root / "README.md"
    if not readme.is_file():
        return [finding("repo.readme", Severity.ERROR, "缺少 README.md", "README 是仓库的门面与准入检查项")]
    text = _read(readme)
    if len(text) < MIN_README_CHARS:
        return [
            finding(
                "repo.readme",
                Severity.WARNING,
                f"README 仅 {len(text)} 字，信息量不足",
                f"建议不少于 {MIN_README_CHARS} 字，覆盖安装、使用、结构与测试",
            )
        ]
    return []


def _rule_readme_sections(root: Path) -> list[RuleResult]:
    text = _read(root / "README.md").lower()
    if not text:
        return []
    missing = [
        name
        for name, keywords in README_SECTIONS.items()
        if not any(keyword.lower() in text for keyword in keywords)
    ]
    if len(missing) >= 3:
        return [
            finding(
                "repo.readme_sections",
                Severity.ERROR,
                f"README 缺少关键章节：{', '.join(missing)}",
                "准入检查会看 README 基础完整性",
            )
        ]
    if missing:
        return [
            finding("repo.readme_sections", Severity.WARNING, f"README 可能缺少章节：{', '.join(missing)}")
        ]
    return []


def _rule_docs_links(root: Path) -> list[RuleResult]:
    readme = _read(root / "README.md")
    results: list[RuleResult] = []
    for link in sorted(set(DOCS_LINK_PATTERN.findall(readme))):
        if not (root / link).is_file():
            results.append(
                finding(
                    "repo.docs_links",
                    Severity.ERROR,
                    f"README 链接的文档不存在：{link}",
                    "README 与文档目录必须保持一致",
                )
            )
    docs_dir = root / "docs"
    if docs_dir.is_dir() and len(list(docs_dir.glob("*.md"))) < 2:
        results.append(
            finding("repo.docs_links", Severity.INFO, "docs/ 下文档少于 2 篇", "建议补充规范与流程文档")
        )
    return results


def _rule_readme_code_consistency(root: Path) -> list[RuleResult]:
    readme = _read(root / "README.md")
    if not readme:
        return []

    results: list[RuleResult] = []
    for dotted in sorted(set(MODULE_REF_PATTERN.findall(readme))):
        if not _module_exists(root, dotted):
            results.append(
                finding(
                    "repo.readme_code_consistency",
                    Severity.ERROR,
                    f"README 引用的模块不存在：{dotted}",
                    "文档描述的功能必须真的有对应代码",
                )
            )
    for reference in sorted(set(FILE_REF_PATTERN.findall(readme))):
        # 只校验带路径分隔符的引用：裸文件名可能指题目内部文件或仓库根文件，含义不唯一
        if "/" not in reference or reference.startswith("/"):
            continue
        if reference.startswith("http") or ".." in reference:
            continue
        if not (root / reference).exists():
            results.append(
                finding(
                    "repo.readme_code_consistency",
                    Severity.ERROR,
                    f"README 引用的文件不存在：{reference}",
                    "改为真实路径，或删除该引用",
                )
            )
    return results


def _rule_entry_points(root: Path) -> list[RuleResult]:
    config = _project_config(root)
    if not config:
        return [finding("repo.entry_points", Severity.ERROR, "pyproject.toml 缺失或无法解析")]
    project = config.get("project", {})
    results: list[RuleResult] = []
    for name, target in (project.get("scripts") or {}).items():
        module_path, _, attribute = str(target).partition(":")
        if not _module_exists(root, module_path):
            results.append(
                finding(
                    "repo.entry_points",
                    Severity.ERROR,
                    f"命令 {name} 指向不存在的模块：{module_path}",
                    "pyproject.toml 的 [project.scripts] 必须指向真实模块",
                )
            )
            continue
        source = _read(root.joinpath(*module_path.split(".")).with_suffix(".py"))
        if attribute and f"def {attribute}(" not in source:
            results.append(
                finding(
                    "repo.entry_points",
                    Severity.ERROR,
                    f"命令 {name} 指向的函数不存在：{target}",
                    "入口函数缺失会导致安装后无法执行",
                )
            )
    if not (project.get("scripts") or {}):
        results.append(finding("repo.entry_points", Severity.WARNING, "未声明命令行入口"))
    return results


def _rule_subsystems(root: Path) -> list[RuleResult]:
    package = root / "talentpro"
    if not package.is_dir():
        return [finding("repo.subsystems", Severity.ERROR, "缺少主包目录：talentpro/")]
    modules = sorted(package.rglob("*.py"))
    if len(modules) < MIN_MODULES:
        return [
            finding(
                "repo.subsystems",
                Severity.ERROR,
                f"主包仅 {len(modules)} 个模块，功能子系统不足（下限 {MIN_MODULES}）",
                "平台按功能子系统评估代码规模",
            )
        ]
    return []


def _rule_tests(root: Path) -> list[RuleResult]:
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return [finding("repo.tests", Severity.ERROR, "缺少 tests/ 目录", "没有测试无法证明功能可用")]
    modules = sorted(tests_dir.glob("test_*.py"))
    functions = sum(_read(path).count("\ndef test_") for path in modules)
    results: list[RuleResult] = []
    if len(modules) < MIN_TEST_MODULES:
        results.append(
            finding(
                "repo.tests",
                Severity.ERROR,
                f"测试模块仅 {len(modules)} 个（下限 {MIN_TEST_MODULES}）",
                "按功能子系统拆分测试文件，覆盖面更清晰",
            )
        )
    if functions < MIN_TEST_FUNCTIONS:
        results.append(
            finding(
                "repo.tests",
                Severity.WARNING,
                f"测试函数约 {functions} 个（建议 ≥{MIN_TEST_FUNCTIONS}）",
                "补齐边界用例：缺文件、格式错误、超时、敏感信息等",
            )
        )
    return results


def _rule_docstrings(root: Path) -> list[RuleResult]:
    package = root / "talentpro"
    if not package.is_dir():
        return []
    missing = [
        str(path.relative_to(root))
        for path in sorted(package.rglob("*.py"))
        if not _read(path).lstrip().startswith('"""')
    ]
    if missing:
        return [
            finding(
                "repo.docstrings",
                Severity.WARNING,
                f"{len(missing)} 个模块缺少模块级 docstring",
                "示例：" + ", ".join(missing[:3]),
            )
        ]
    return []


def _rule_hygiene(root: Path) -> list[RuleResult]:
    results: list[RuleResult] = []
    if not (root / ".gitignore").is_file():
        results.append(finding("repo.hygiene", Severity.WARNING, "缺少 .gitignore"))
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # 跳过版本库、虚拟环境与缓存目录，避免把工具产物当成仓库内容
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in ARTIFACT_SUFFIXES or path.name == ".DS_Store":
            results.append(
                finding(
                    "repo.hygiene",
                    Severity.WARNING,
                    f"存在临时产物：{path.relative_to(root)}",
                    "清理后再提交",
                )
            )
        elif path.stat().st_size > MAX_REPO_FILE_BYTES and path.suffix not in {".log"}:
            results.append(
                finding(
                    "repo.hygiene",
                    Severity.WARNING,
                    f"文件过大：{path.relative_to(root)}（{path.stat().st_size // 1024} KB）",
                    "大文件请放到对象存储或数据集中",
                )
            )
    return results


def _rule_secrets(root: Path) -> list[RuleResult]:
    return scan_secrets(sorted(iter_text_files(root)), rule_id="repo.secrets")


def _rule_metadata_files(root: Path) -> list[RuleResult]:
    results: list[RuleResult] = []
    for name, level, hint in (
        ("LICENSE", Severity.WARNING, "标明开源许可，便于合规审查"),
        ("CHANGELOG.md", Severity.WARNING, "记录版本变更，便于复核开发过程"),
        ("CONTRIBUTING.md", Severity.INFO, "说明协作方式"),
    ):
        if not (root / name).is_file():
            results.append(finding("repo.metadata_files", level, f"缺少 {name}", hint))
    return results


def _rule_ci(root: Path) -> list[RuleResult]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir() or not list(workflows.glob("*.y*ml")):
        return [
            finding(
                "repo.ci",
                Severity.WARNING,
                "缺少 CI 工作流",
                "在 .github/workflows/ 下提交 lint + 测试流水线",
            )
        ]
    return []


REPO_RULES: tuple[tuple[str, str, RepoRule], ...] = (
    ("repo.subsystems", "功能子系统", _rule_subsystems),
    ("repo.readme", "README 完整性", _rule_readme_present),
    ("repo.readme_sections", "README 章节结构", _rule_readme_sections),
    ("repo.readme_code_consistency", "README 与代码一致性", _rule_readme_code_consistency),
    ("repo.docs_links", "文档链接有效性", _rule_docs_links),
    ("repo.entry_points", "命令行入口一致性", _rule_entry_points),
    ("repo.tests", "测试覆盖", _rule_tests),
    ("repo.docstrings", "模块文档", _rule_docstrings),
    ("repo.secrets", "敏感信息扫描", _rule_secrets),
    ("repo.metadata_files", "仓库元文件", _rule_metadata_files),
    ("repo.ci", "持续集成", _rule_ci),
    ("repo.hygiene", "仓库整洁度", _rule_hygiene),
)


def check_repository(root: str | Path) -> CheckReport:
    """对仓库根目录执行全部仓库级规则。"""
    repo_root = Path(root).expanduser().resolve()
    report = CheckReport()
    if not repo_root.is_dir():
        report.add(finding("repo.root", Severity.ERROR, f"目录不存在：{repo_root}"))
        return report

    for rule_id, title, func in REPO_RULES:
        try:
            results = func(repo_root)
        except Exception as exc:  # noqa: BLE001 - 与题目级规则保持一致的降级策略
            report.add(
                finding(rule_id, Severity.ERROR, f"规则执行异常：{exc.__class__.__name__}: {exc}")
            )
            continue
        if results:
            report.extend(results)
        else:
            report.add(finding(rule_id, Severity.INFO, f"通过：{title}"))
    return report
