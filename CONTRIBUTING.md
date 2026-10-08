# 协作指南

## 环境准备

```bash
git clone https://github.com/lulukdog/talent-pro
cd talent-pro
uv venv --python 3.12
uv pip install -e ".[dev]"
```

不安装包也能直接跑测试：仓库根目录的 `conftest.py` 会把仓库加入 `sys.path`。

## 提交前必做

```bash
ruff check .            # 静态检查
pytest -q               # 单元测试
talentpro repo-check .  # 仓库级自检：文档与代码是否一致、有无敏感信息
talentpro check examples/exam_001   # 示例题目必须 0 error
```

## 提交信息规范

使用约定式提交，前缀取值：`feat`、`fix`、`docs`、`test`、`chore`、`refactor`、`perf`、
`build`、`ci`、`revert`。格式为 `type(scope): 主题`，主题不超过 72 字符且不要写
「更新」「修改」这类无法定位的内容；跨子系统的改动写在提交正文里。

```
feat(validators): 增加产物目录预建检查

说明为什么需要该规则，以及它会阻断哪类问题。
```

`talentpro history .` 会给出前缀覆盖率与含糊主题统计，质量分可作为 CI 门禁参考。

## 分支与评审

- 主分支为 `main`，保持可安装、可校验、测试全绿。
- 一个分支只做一件事，PR 描述里写清「改了什么 / 为什么 / 怎么验证」。
- 涉及规则的改动必须同时补测试：干净任务断言不报错，破坏后断言命中对应规则。

## 新增规则

```python
# talentpro/validators/instruction.py
@rule("instruction.example", "示例规则", "instruction")
def check_example(task: TaskSpec) -> list[RuleResult]:
    if (task.root / "README.md").is_file():
        return []
    return [finding("instruction.example", Severity.WARNING, "题目缺少说明文件", "补充后便于复核")]
```

约定：

- 规则只返回「有问题的项」，通过与否由框架补齐 `INFO`。
- 判定必须给出 `hint`（怎么改），否则复现成本高。
- 不要引入需要联网的规则，校验必须在离线环境可运行。
