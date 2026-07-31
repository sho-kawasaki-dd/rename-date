# Phase 0: プロジェクト初期化 実装計画書

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) 第6章 Phase 0（プロジェクト初期化）。

## 目的

`uv` によるプロジェクト初期化を行い、開発計画書 3.2 節のディレクトリ構成に沿ったパッケージ骨組み（スタブ）を作成する。Phase 1 以降の実装（Models / Services / Views / Controllers の実ロジック）に着手できる土台を整えることが目的であり、本フェーズではビジネスロジックは一切実装しない。

## 要件

- `pyproject.toml` の `requires-python` が `>=3.12` であること。
- `[tool.pytest.ini_options]` に `pythonpath = ["src"]` が設定されていること。
- `pytest`, `pytest-cov`, `pyinstaller` が dev 依存として追加され、`uv.lock` に反映されていること。
- 開発計画書 3.2 節のツリーに記載された全ファイルが存在すること（中身は docstring / `pass` / `...` のみのスタブとし、ロジックは実装しない）。
- `tests/` 配下は `conftest.py` のみ作成し、`test_scanner.py` 等の `test_*.py` は作成しない（Phase 1 で実装時に作成）。
- `.gitignore` に `dist/`, `build/`, `.venv/`, `__pycache__/`, `installer/Output/` に加え、一般的な Python 向け除外項目（`.pytest_cache/`, `.coverage`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`, `*.pyo`）が含まれること。
- 既存の `README.md` および `.git/` がこの初期化によって上書き・再初期化されないこと。
- `uv run main.py` がエラーなく終了すること。
- `uv run pytest --cov=src/rename_date` が実行できること（test\_\*.py 未作成のため「no tests ran」は許容する）。

## タスク

### 1. プロジェクト初期化

- [ ] リポジトリ直下（`d:\programming\rename-date`）で `uv init --app --package .` を実行する。
- [ ] 実行後に生成された `pyproject.toml` / `.python-version` / `src/rename_date/` の内容を確認する。
- [ ] `git status` / `git diff` で `README.md` の内容と `.git/` が変更・再初期化されていないことを確認する。

### 2. `pyproject.toml` 調整

- [ ] `requires-python = ">=3.12"` を設定する。
- [ ] `[tool.pytest.ini_options]` を追加し `pythonpath = ["src"]` を設定する。
- [ ] `[project]` の name / version / description を確認する（既定のままで可）。
- [ ] uv が `[project.scripts]` を自動生成していた場合、`rename_date.__main__:main` との整合性を確認する。

### 3. 開発用依存関係の追加

- [ ] `uv add --dev pytest pytest-cov pyinstaller` を実行する。
- [ ] `pyproject.toml` の dev 依存グループと `uv.lock` が更新されたことを確認する。

### 4. パッケージ骨組みの作成（全ファイルスタブ）

ルート:

- [ ] `main.py` — `rename_date.__main__.main` を呼び出す薄いラッパーのみ作成する。

`src/rename_date/`:

- [ ] `__init__.py` — `__version__ = "0.1.0"` のみ定義する。
- [ ] `__main__.py` — `def main() -> None: ...` のみ（実装は Phase 3）。
- [ ] `config.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `single_instance.py` — モジュール docstring のみ（実装は Phase 3）。
- [ ] `models/__init__.py` — 空ファイルを作成する。
- [ ] `models/rename_item.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `models/execution_history.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `services/__init__.py` — 空ファイルを作成する。
- [ ] `services/scanner_service.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `services/rename_service.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `services/undo_service.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `services/log_service.py` — モジュール docstring のみ（実装は Phase 1）。
- [ ] `controllers/__init__.py` — 空ファイルを作成する。
- [ ] `controllers/app_controller.py` — モジュール docstring のみ（実装は Phase 3）。
- [ ] `views/__init__.py` — 空ファイルを作成する。
- [ ] `views/main_window.py` — モジュール docstring のみ（実装は Phase 2）。
- [ ] `views/config_frame.py` — モジュール docstring のみ（実装は Phase 2）。
- [ ] `views/preview_frame.py` — モジュール docstring のみ（実装は Phase 2）。
- [ ] `views/action_frame.py` — モジュール docstring のみ（実装は Phase 2）。

`tests/`:

- [ ] `conftest.py` — 最小限のプレースホルダのみ作成する（`test_*.py` はこのフェーズでは作成しない）。

`installer/`（中身は Phase 4 実装分のプレースホルダ）:

- [ ] `rename-date.spec` — プレースホルダである旨のコメントのみ記載する。
- [ ] `setup.iss` — プレースホルダである旨のコメントのみ記載する。

### 5. `.gitignore` 整備

- [ ] `dist/`, `build/`, `.venv/`, `__pycache__/`, `installer/Output/` を含める。
- [ ] `.pytest_cache/`, `.coverage`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`, `*.pyo` を追加する。
- [ ] uv が生成した既定の `.gitignore`（存在する場合）と重複を排除しつつマージする。

### 6. 動作確認

- [ ] `uv run main.py` がエラーなく終了することを確認する。
- [ ] `uv run pytest --cov=src/rename_date` を実行し、「no tests ran」（exit code 5）が想定内であることを確認する。
- [ ] `pyproject.toml` の `requires-python` と `pythonpath` 設定を目視確認する。
- [ ] `uv.lock` に `pytest` / `pytest-cov` / `pyinstaller` が dev 依存として記録されていることを確認する。
- [ ] `git status` で意図しないファイル変更（`README.md`, `.git/` 配下）がないこと、新規追加ファイルが想定どおりであることを確認する（コミットはユーザーが手動で実施）。

## スコープ外（本フェーズで実装しないこと）

- `RenameItem` / `ItemStatus` / `ExecutionHistory` の実データモデル実装（Phase 1）
- `ScannerService` / `RenameService` / `UndoService` / `LogService` の実ロジック（Phase 1）
- View / Controller の実装（Phase 2, Phase 3）
- 多重起動抑止の実ロジック（Phase 3）
- PyInstaller / Inno Setup の実設定内容（Phase 4）
- `git commit` の実行（ユーザー確認後に手動で行う）
