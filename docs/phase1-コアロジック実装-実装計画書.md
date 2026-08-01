# Phase 1: コアロジック実装 (Models / Services) 実装計画書

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) 第6章 Phase 1（コアロジック実装）。

## 目的

Models 層・Services 層の実ロジックを実装し、GUI（Views/Controllers）に依存せずファイル名一括変換の中核機能（走査・置換・日付検証・衝突回避・実行・Undo・ログ出力・パターンプリセット管理）を完成させる。Services 層は tkinter を import せず、pytest により単体でテスト可能な状態を維持することが目的である。

開発計画書 6 章の Phase 1 タスク一覧には明記されていないが、Phase 2 の `ConfigFrame` が `PatternService` に依存すること、および開発計画書 3 章のアーキテクチャ図・11 章のテスト方針（`test_pattern_service.py`）に `PatternEntry` / `PatternService` が含まれることから、本フェーズのスコープに含める。

## 要件

- 開発計画書 5 章記載の `ItemStatus` / `RenameItem` / `ExecutionHistory` を仕様どおりに実装すること。
- `PatternEntry`（`name` / `pattern` / `output_template`）を新規実装し、`name` を一意キーとする。同名で保存された場合は上書きする。
- 正規表現・出力テンプレートの検証ロジック（コンパイル可否・キャプチャグループ数=3・プレースホルダ`{Y}{M}{D}`各1回以上・Windows禁止文字`\ / : * ? " < > |`不使用）と、対応する例外クラス `InvalidPatternError` / `InvalidTemplateError` を新規共有モジュール `services/validation.py` に集約し、`ScannerService` と `PatternService` の両方から再利用すること（重複実装しない）。
- `PatternService` / `LogService` は出力先ディレクトリをコンストラクタ引数 `base_dir: Path | None = None` で受け取れること。未指定時は `config.get_config_dir()` / `config.get_log_dir()`（`%APPDATA%\rename-date\...`）を既定値とする。
- `ScannerService` はフォルダの再帰走査（`os.walk(topdown=True, followlinks=False)`、隠しファイル/フォルダ・既定除外ディレクトリ・symlink除外）と、個別ファイル指定（隠しファイルチェックのみ適用）の両方に対応し、`Path.resolve()` で重複除去した上で決定的な順序（`(親ディレクトリ, ファイル名)` でソート）で処理すること。
- 1 ファイル名中の複数マッチはすべて置換し、いずれか 1 つでも `datetime.date` として不正なら、そのファイル全体を `ItemStatus.INVALID_DATE` として実行対象外にすること。
- 置換後の連続空白畳み込み・トリムを行い、変更前後で stem が同一のファイルは結果に含めないこと。
- 名前衝突は親ディレクトリごとに `casefold()` で比較し、`_1`, `_2` … の連番で自動回避し `RESOLVED_CONFLICT` として記録すること。
- `RenameService` は `Path.rename()` のみを使用し、`FileExistsError` → `SKIPPED`、その他の `OSError` → `ERROR` として記録し処理を継続すること。成功項目のみを含む `ExecutionHistory` を返すこと。
- `UndoService` はメモリ上の LIFO スタックで `ExecutionHistory` を管理し、実行時と逆順で復元、欠損・競合時は該当項目のみ `SKIPPED` として継続すること。
- `LogService` は `logging.handlers.RotatingFileHandler`（`maxBytes=1MiB`, `backupCount=5`, `encoding="utf-8"`, `delay=True`）を用い、ロガー名 `rename_date.audit` を `propagate=False` で使用し、世代ファイル名を `rename_log.N.txt` とすること。TSV 出力時はファイル名中のタブ・改行をエスケープすること。
- `PatternService` は起動時に `patterns.json` を読み込み、欠損・破損・スキーマ不正時は既定プリセット1件で新規生成すること。保存は一時ファイル+`os.replace()`によるアトミック書き込みとし、保存前に全件検証し、削除時は最後の1件を残すこと。
- Services 層のテストカバレッジ目標 85% 以上（`uv run pytest --cov=src/rename_date`）。ファイルシステムはモックせず `tmp_path` フィクスチャで実 I/O 検証すること。

## タスク

### 1. Models 層

- [x] `models/rename_item.py`: `ItemStatus(StrEnum)`（`PENDING`/`INVALID_DATE`/`RESOLVED_CONFLICT`/`SUCCESS`/`SKIPPED`/`ERROR`）と `RenameItem` dataclass（`original_path`, `target_path`, `status`, `message`、プロパティ `original_name`/`target_name`/`parent_dir`/`is_executable`）を開発計画書5章のとおり実装する。
- [x] `models/execution_history.py`: `ExecutionHistory` dataclass（`timestamp`, `session_id`, `items: list[RenameItem]`）を開発計画書5章のとおり実装する。
- [x] `models/pattern_entry.py`（新規作成）: `PatternEntry` dataclass（`name`, `pattern`, `output_template`）と `to_dict()` / `from_dict(cls, data: dict)` を実装する。

### 2. `config.py`

- [x] 既定プリセット定数（`DEFAULT_PATTERN_NAME`, `DEFAULT_PATTERN_REGEX`, `DEFAULT_OUTPUT_TEMPLATE`）を定義する。
- [x] 既定除外ディレクトリ集合 `EXCLUDED_DIR_NAMES`（`.git`, `.svn`, `.hg`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`）を定義する。
- [x] ログローテーション定数 `LOG_MAX_BYTES=1_048_576`, `LOG_BACKUP_COUNT=5`, ロガー名定数 `AUDIT_LOGGER_NAME="rename_date.audit"` を定義する。
- [x] `get_appdata_dir()` / `get_config_dir()` / `get_log_dir()`（`%APPDATA%\rename-date\...`）を実装する。

### 3. 共有検証ロジック

- [x] `services/validation.py`（新規作成）: `InvalidPatternError` / `InvalidTemplateError`（`ValueError`継承）を定義する。
- [x] `compile_pattern(pattern: str) -> re.Pattern[str]`: コンパイル失敗、またはキャプチャグループ数が3でない場合に `InvalidPatternError` を送出する。
- [x] `validate_output_template(template: str) -> None`: `{Y}` `{M}` `{D}` を各1回以上含むこと、Windows のファイル名不可文字を含まないことを検証し、違反時は `InvalidTemplateError` を送出する。

### 4. `PatternService`

- [x] `services/pattern_service.py`（新規作成）: `PatternService(base_dir: Path | None = None)` を実装する。
- [x] `load() -> list[PatternEntry]`: `patterns.json` 読込。欠損・パース失敗・スキーマ不正時は既定プリセット1件で新規生成し保存する。
- [x] `save(entries: list[PatternEntry]) -> None`: `validation.py` を用いて全件検証し、空リストは拒否する。一時ファイル書き込み後 `os.replace()` でアトミックに保存する。
- [x] `upsert(entry: PatternEntry) -> list[PatternEntry]`: `name` 一致で上書き、なければ追加してから保存する。
- [x] `delete(name: str) -> list[PatternEntry]`: 削除後の残数が0になる場合は拒否する。

### 5. `ScannerService`

- [x] `services/scanner_service.py`: `scan(targets, pattern, output_template, cancel_event=None) -> list[RenameItem]` を実装する。
- [x] `validation.compile_pattern` / `validate_output_template` による事前検証を行う。
- [x] フォルダ対象は `os.walk(topdown=True, followlinks=False)` で走査し、`dirnames` を書き換えて除外ディレクトリ・隠しフォルダ・symlink/junctionの探索を打ち切る。
- [x] ファイル対象（直接指定）は隠しファイルチェックのみ適用してそのまま追加する。
- [x] `Path.resolve()` で全対象の重複除去を行い、`(親ディレクトリ, ファイル名)` でソートして決定的順序にする。
- [x] `re.sub` で `stem` 中の全マッチを置換し、`datetime.date` による日付妥当性検証で1つでも不正なら `INVALID_DATE` とする。
- [x] 置換後の連続空白畳み込み・トリムを行い、変更前後で同一の場合は結果から除外する。
- [x] 親ディレクトリごとに実在エントリ（casefold比較）を予約済み名として初期化し、衝突時は `_1, _2...` を付与して `RESOLVED_CONFLICT` とする。
- [x] `cancel_event` を走査ループ内で定期確認し、要求時は途中結果を返す。

### 6. `RenameService` / `UndoService`

- [ ] `services/rename_service.py`: `execute(items, cancel_event=None) -> tuple[list[RenameItem], ExecutionHistory]` を実装する。`is_executable` な項目のみ `Path.rename()` を実行し、`FileExistsError` → `SKIPPED`、その他 `OSError` → `ERROR`、成功は `SUCCESS` とする。戻り値の第1要素は全項目（最終ステータス反映）、第2要素は成功項目のみの `ExecutionHistory` とする。
- [ ] `services/undo_service.py`: `UndoService` クラス（`push(history)`, `has_history() -> bool`, `undo(cancel_event=None) -> list[RenameItem]`）を実装する。スタック末尾を pop し、`reversed(history.items)` の順で復元する。欠損・競合時は該当項目のみ `SKIPPED`、その他 `OSError` は `ERROR` とし処理を継続する。

### 7. `LogService`

- [ ] `services/log_service.py`: `LogService(base_dir: Path | None = None)` を実装する。
- [ ] `RotatingFileHandler`（`maxBytes=config.LOG_MAX_BYTES`, `backupCount=config.LOG_BACKUP_COUNT`, `encoding="utf-8"`, `delay=True`）をロガー `rename_date.audit`（`propagate=False`）に設定し、多重初期化時のハンドラ重複を防ぐ。
- [ ] `handler.namer` をカスタマイズし世代ファイル名を `rename_log.N.txt` にする。
- [ ] `log_rename(items, session_id)` / `log_undo(items, session_id)`: ISO8601日時・`session_id`・action・status・変更前後パス・メッセージをタブ区切りで1行出力する。タブ・改行はエスケープする。
- [ ] `close()`: ハンドラを解放する。

### 8. テスト実装

- [ ] `tests/conftest.py`: 開発計画書11.2章のダミーフォルダ構造を `tmp_path` 上に生成する fixture、既定 `PatternEntry` を返す fixture を実装する。
- [ ] `tests/test_scanner.py`: 基本変換/ゼロ埋め/複数マッチ/拡張子非対象/不正日付/隠しファイル・除外フォルダ/シンボリックリンク/衝突（既存・バッチ内）/不正パターン・グループ数不一致/変更なし除外/出力テンプレート可変/個別ファイルプレビュー/フォルダ・ファイル混在の重複除去を検証する。
- [ ] `tests/test_renamer.py`: 成功時の履歴生成/直前衝突のSKIP（`monkeypatch`で`FileExistsError`注入）/権限エラー時の継続（`OSError`注入）/無効項目のスキップを検証する。
- [ ] `tests/test_undo.py`: 逆順復元/ファイル欠損時SKIP/復元先衝突時SKIP/多段スタック/空スタックを検証する。
- [ ] `tests/test_log.py`: ディレクトリ自動作成/追記/タブ・改行エスケープ/ローテーション（`maxBytes`を極小にして世代ファイル生成・上限確認）を検証する。
- [ ] `tests/test_pattern_service.py`: JSON読込/保存/初回起動時の既定プリセット生成/不正テンプレート（プレースホルダ欠落・禁止文字）の保存拒否/壊れたJSONからのフォールバック/最後の1件削除拒否/同名上書きを検証する。

### 9. 動作確認

- [ ] `uv run pytest --cov=src/rename_date --cov-report=term-missing` を実行し、全テストが green であり Services 層カバレッジ85%以上であることを確認する。
- [ ] ダミー `tmp_path` 構造に対して `ScannerService.scan` を手動実行し、開発計画書11.2章の期待結果（無効日付・衝突回避・隠しフォルダ除外等）と一致することを確認する。
- [ ] Pylance等の静的検査でエラーが出ていないことを確認する。

## スコープ外（本フェーズで実装しないこと）

- View / Controller の実装（Phase 2, Phase 3）
- `single_instance.py` の実ロジック、`__main__.py` の実処理（Phase 3）
- PyInstaller / Inno Setup の実設定内容（Phase 4）
- カバレッジ85%未達時の CI 強制失敗設定（本フェーズでは目視確認のみ）
- Redo、フォルダ名リネーム、Undo履歴の永続化など、開発計画書12章記載のスコープ外事項
