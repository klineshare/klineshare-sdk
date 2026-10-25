# PyPI 发布清单

发布前按本清单执行。版本号规则见 [DEVELOPMENT.md §10](DEVELOPMENT.md)。

## 发布前

- [x] `CHANGELOG.md` 已写清本版本变更，并将 `[Unreleased]` 条目移入版本节
- [x] `pyproject.toml` / `src/klineshare/__init__.py` 的 `__version__` 一致（`0.2.7`）
- [x] 本地：`pip install -e ".[dev]" && pytest -q` 全绿（595 passed）
- [ ] CI（GitHub Actions）在目标 commit 上绿
- [x] `python scripts/check_endpoint_coverage.py` 已跑过（排除东财路径后 100%）
- [ ] README 快速开始可在干净环境跑通（真实 Key）
- [ ] 确认无密钥写入仓库（`.env` 已忽略）
- [ ] （建议）`KLINESHARE_RUN_LIVE=1 pytest -m live` 与 `python scripts/live_smoke.py --quick`

## 构建

```bash
python -m pip install --upgrade build twine
rm -rf dist/ build/
python -m build
twine check dist/*
```

## 上传

TestPyPI（可选）：

```bash
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ klineshare==VERSION
```

正式 PyPI：

```bash
twine upload dist/*
```

## 发布后

- [ ] `pip install klineshare==VERSION` 验证 import 与 `pro.health()`
- [ ] 打 git tag：`vVERSION` 并推送
- [ ] 官网 / 文档站如有安装说明，更新版本号

## 版本选择速查

| 场景 | 版本 |
|------|------|
| 文档、测试、限额收紧、修 bug | patch `0.1.x` |
| 默认行为变更、稳定公开 API 新增 | minor `0.2.0` |
| 删除/重命名公共 API | major |
