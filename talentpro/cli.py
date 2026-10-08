"""命令行入口：把校验、报告、脚手架与里程碑能力串成可编排的流水线。

返回码约定：``0`` 通过，``1`` 有未通过项（``--strict`` 时警告也算），``2`` 输入或环境错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .backlog import render_todos, suggest_todos
from .gitlog import GitError, assess_messages, chronological, history_summary, read_commits
from .milestone import plan_milestones, render_milestones, validate_milestones
from .models import CheckReport, Severity
from .report import analyze, compare_reports, load_log, render_report
from .scaffold import scaffold_task
from .spec import TaskFormatError, load_task
from .validators import check_repository, run_checks

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    """构建参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="talentpro",
        description="考核题库开发工具链：题目校验、报告解析、脚手架与里程碑划分",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="校验题目目录是否符合题库规范")
    check.add_argument("task", type=Path, help="题目目录，例如 examples/exam_001")
    check.add_argument("--json", action="store_true", help="以 JSON 输出")
    check.add_argument("--strict", action="store_true", help="警告同样视为失败")
    check.add_argument("--category", help="只运行指定分类的规则，例如 security")
    check.add_argument("--rules", nargs="*", help="只运行指定规则 id")

    repo = subparsers.add_parser("repo-check", help="仓库级质量检查（骨架、README、测试、敏感信息）")
    repo.add_argument("repo", type=Path, nargs="?", default=Path("."))
    repo.add_argument("--json", action="store_true")
    repo.add_argument("--strict", action="store_true")

    report = subparsers.add_parser("report", help="由访问日志生成标准 report.txt")
    report.add_argument("log", type=Path)
    report.add_argument("-o", "--output", type=Path, help="输出文件，缺省打印到标准输出")

    compare = subparsers.add_parser("compare", help="比较期望报告与实际报告")
    compare.add_argument("expected", type=Path)
    compare.add_argument("actual", type=Path)

    scaffold = subparsers.add_parser("scaffold", help="生成新题目目录")
    scaffold.add_argument("task_id", help="题目编号，例如 exam_002")
    scaffold.add_argument("--dest", type=Path, required=True, help="题目目录路径")
    scaffold.add_argument("--title", default="日志分析任务")
    scaffold.add_argument("--description", default="分析 Web 服务器访问日志并输出统计报告。")
    scaffold.add_argument("--org", default="harbor")
    scaffold.add_argument("--author", default="talent-pro")
    scaffold.add_argument("--difficulty", default="easy", choices=["easy", "medium", "hard"])
    scaffold.add_argument("--category", default="programming")
    scaffold.add_argument("--tags", nargs="*", default=["log-analysis", "shell", "file-processing"])
    scaffold.add_argument("--log-lines", type=int, default=40)
    scaffold.add_argument("--seed", type=int, default=20250101)

    milestones = subparsers.add_parser("milestones", help="按提交历史自动划分里程碑")
    milestones.add_argument("repo", type=Path, nargs="?", default=Path("."))
    milestones.add_argument("--json", action="store_true")
    milestones.add_argument("--out", type=Path, help="写入 Markdown 文件")
    milestones.add_argument("--max-per-milestone", type=int, default=8)

    todos = subparsers.add_parser("todos", help="生成后续工作清单")
    todos.add_argument("task", type=Path, nargs="?", help="题目目录；缺省只输出通用清单")
    todos.add_argument("--json", action="store_true")
    todos.add_argument("--minimum", type=int, default=5)

    history = subparsers.add_parser("history", help="汇总提交历史与提交说明质量")
    history.add_argument("repo", type=Path, nargs="?", default=Path("."))
    history.add_argument("--json", action="store_true")

    return parser


def print_report(report: CheckReport, *, strict: bool = False) -> None:
    """按严重级别打印检查结果。"""
    for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
        for result in report.results:
            if result.severity is not severity:
                continue
            print(f"[{severity.label}] {result.rule_id}: {result.message}")
            if result.hint:
                print(f"         提示：{result.hint}")
    print(f"-- {report.summary()}" + ("（strict 模式：警告视为失败）" if strict else ""))


def _exit_code(report: CheckReport, strict: bool) -> int:
    if report.errors:
        return EXIT_FINDINGS
    if strict and report.warnings:
        return EXIT_FINDINGS
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    try:
        task = load_task(args.task)
    except TaskFormatError as exc:
        print(f"无法解析题目目录：{exc}", file=sys.stderr)
        return EXIT_ERROR

    report = run_checks(task, category=args.category, rule_ids=args.rules)
    if args.json:
        print(json.dumps({"task": task.name, **report.to_dict()}, ensure_ascii=False, indent=2))
    else:
        print(f"{task.root.name} · {task.name}")
        print_report(report, strict=args.strict)
    return _exit_code(report, args.strict)


def cmd_repo_check(args: argparse.Namespace) -> int:
    report = check_repository(args.repo)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"仓库检查：{Path(args.repo).resolve()}")
        print_report(report, strict=args.strict)
    return _exit_code(report, args.strict)


def cmd_report(args: argparse.Namespace) -> int:
    try:
        entries = load_log(args.log)
    except OSError as exc:
        print(f"无法读取日志：{exc}", file=sys.stderr)
        return EXIT_ERROR
    except ValueError as exc:
        print(f"日志解析失败：{exc}", file=sys.stderr)
        return EXIT_ERROR

    text = render_report(analyze(entries))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"已写入 {args.output}（{len(entries)} 条记录）")
    else:
        print(text, end="")
    return EXIT_OK


def cmd_compare(args: argparse.Namespace) -> int:
    expected = args.expected.read_text(encoding="utf-8", errors="replace")
    actual = args.actual.read_text(encoding="utf-8", errors="replace")
    mismatches = compare_reports(expected, actual)
    if not mismatches:
        print("两份报告一致")
        return EXIT_OK
    for mismatch in mismatches:
        print(f"[DIFF] {mismatch.describe()}")
    print(f"-- 共 {len(mismatches)} 处差异")
    return EXIT_FINDINGS


def cmd_scaffold(args: argparse.Namespace) -> int:
    try:
        result = scaffold_task(
            args.dest,
            args.task_id,
            title=args.title,
            description=args.description,
            org=args.org,
            author=args.author,
            difficulty=args.difficulty,
            category=args.category,
            tags=tuple(args.tags),
            log_lines=args.log_lines,
            seed=args.seed,
        )
    except (FileExistsError, ValueError) as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return EXIT_ERROR

    print(f"已生成题目：{result.root}")
    for relative in result.files:
        print(f"  - {relative}")
    print(f"样例日志 {result.log_lines} 行；示例数据首行用于题面样例。")

    report = run_checks(load_task(result.root))
    print_report(report)
    return _exit_code(report, strict=False)


def cmd_milestones(args: argparse.Namespace) -> int:
    try:
        commits = read_commits(args.repo)
    except GitError as exc:
        print(f"读取提交历史失败：{exc}", file=sys.stderr)
        return EXIT_ERROR

    ordered = chronological(commits)
    drafts = plan_milestones(ordered, max_per_milestone=args.max_per_milestone)
    issues = validate_milestones(drafts, ordered)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_milestones(drafts), encoding="utf-8")

    if args.json:
        print(
            json.dumps(
                {
                    "milestones": [draft.to_dict() for draft in drafts],
                    "issues": [item.to_dict() for item in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render_milestones(drafts), end="")
        print(f"提交总数 {len(ordered)}，划分里程碑 {len(drafts)} 个")
        for issue in issues:
            print(f"[{issue.severity.label}] {issue.message}")
        if not issues:
            print("-- 里程碑自检通过")

    return EXIT_FINDINGS if any(item.severity is Severity.ERROR for item in issues) else EXIT_OK


def cmd_todos(args: argparse.Namespace) -> int:
    findings = None
    if args.task is not None:
        try:
            task = load_task(args.task)
        except TaskFormatError as exc:
            print(f"无法解析题目目录：{exc}", file=sys.stderr)
            return EXIT_ERROR
        findings = run_checks(task).results

    items = suggest_todos(findings, minimum=args.minimum)
    if args.json:
        print(json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2))
    else:
        print(render_todos(items), end="")
    return EXIT_OK


def cmd_history(args: argparse.Namespace) -> int:
    try:
        summary = history_summary(args.repo)
        quality = assess_messages(read_commits(args.repo))
    except GitError as exc:
        print(f"读取提交历史失败：{exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps({**summary, "quality": quality.to_dict()}, ensure_ascii=False, indent=2))
        return EXIT_OK

    print(f"提交总数：{summary['commits']}")
    print(f"作者：{', '.join(summary['authors']) if summary['authors'] else '(无)'}")
    print(f"时间范围：{summary['first_commit']} → {summary['last_commit']}")
    print(
        f"提交说明质量：{quality.score:.2f}"
        f"（约定式前缀覆盖 {quality.prefix_coverage:.0%}，含糊主题 {len(quality.vague)} 条）"
    )
    for problem in quality.issues():
        print(f"[WARN ] {problem}")
    return EXIT_OK if not quality.issues() else EXIT_FINDINGS


COMMANDS = {
    "check": cmd_check,
    "repo-check": cmd_repo_check,
    "report": cmd_report,
    "compare": cmd_compare,
    "scaffold": cmd_scaffold,
    "milestones": cmd_milestones,
    "todos": cmd_todos,
    "history": cmd_history,
}


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS[args.command]
    try:
        return int(handler(args))
    except KeyboardInterrupt:  # pragma: no cover - 交互中断
        print("已中断", file=sys.stderr)
        return EXIT_ERROR
    except BrokenPipeError:  # pragma: no cover - 管道提前关闭
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
