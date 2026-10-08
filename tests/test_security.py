"""安全扫描规则的测试。

构造假密钥时一律使用字符串拼接，避免仓库自身命中敏感信息扫描。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from talentpro.spec import load_task
from talentpro.validators import run_checks, scan_secrets

FAKE_FIGMA = "figd_" + "A" * 24
FAKE_PRIVATE_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----"
FAKE_PASSWORD = 'password = "' + "s3cret-value" + '"'
INTERNAL_DOMAIN = "lingyiwanwu" + ".net"
PERSONAL_PATH = "/" + "Users" + "/someone/project"


def copy_task(source: Path, target_dir: Path) -> Path:
    destination = target_dir / "copy" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination


def test_clean_task_has_no_secret_findings(task) -> None:
    report = run_checks(task, category="security")
    assert report.passed
    assert report.of("security.secrets")[0].message.startswith("通过")


def test_scan_secrets_finds_figma_token() -> None:
    results = scan_secrets([("solve.sh", f"TOKEN={FAKE_FIGMA}")])
    assert len(results) == 1
    assert "Figma" in results[0].message
    assert FAKE_FIGMA not in results[0].message


def test_scan_secrets_finds_private_key() -> None:
    results = scan_secrets([("notes.md", FAKE_PRIVATE_KEY)])
    assert results and "私钥" in results[0].message


def test_scan_secrets_finds_hardcoded_password() -> None:
    results = scan_secrets([("config.py", FAKE_PASSWORD)])
    assert results and "口令" in results[0].message


def test_scan_secrets_reports_line_number() -> None:
    results = scan_secrets([("config.py", "a = 1\nb = 2\n" + FAKE_PASSWORD)])
    assert results[0].message.startswith("config.py:3")


def test_scan_secrets_clean_input() -> None:
    assert scan_secrets([("readme.md", "这里没有密钥，只有说明文字。")]) == []


def test_internal_domain_is_error(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    solve = task_root / "solution/solve.sh"
    solve.write_text(
        solve.read_text(encoding="utf-8") + f"\ncurl https://{INTERNAL_DOMAIN}/api\n",
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "security.internal_hosts" in report.failed_rule_ids


def test_personal_path_is_warning(sample_task: Path, tmp_path: Path) -> None:
    task_root = copy_task(sample_task, tmp_path)
    dockerfile = task_root / "environment/Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8") + f"\n# 参考 {PERSONAL_PATH}/notes.txt\n",
        encoding="utf-8",
    )
    report = run_checks(load_task(task_root))
    assert "security.personal_paths" in {item.rule_id for item in report.warnings}


def test_private_network_is_info_only(task) -> None:
    report = run_checks(task, rule_ids=["security.private_networks"])
    assert report.passed
    assert all(item.severity.value == "info" for item in report.results)


def test_secret_scan_is_also_used_by_repo_checks(tmp_path: Path) -> None:
    from talentpro.validators.repo import check_repository

    (tmp_path / "leak.py").write_text(f"KEY = '{FAKE_FIGMA}'\n", encoding="utf-8")
    report = check_repository(tmp_path)
    assert "repo.secrets" in report.failed_rule_ids
