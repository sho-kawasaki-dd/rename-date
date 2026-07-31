# Project Guidelines — rename-date

Windows 向け tkinter GUI アプリ。指定フォルダを再帰走査し、正規表現 `(YYYY.M.D)` 形式にマッチするファイル名を `YYYYMMDD` へ一括変換する。全仕様は [docs/rename-date開発計画書.md](../docs/rename-date開発計画書.md) を参照。このファイルには「必ず守るべき契約」と「頻繁に間違えやすい点」のみを記載する。

## 環境 & コマンド

- Python 3.12+、パッケージ/環境管理は **uv**（pip/venv を直接使わない）。
- 初期化: `uv init --app --package .`（src レイアウト）
- 依存追加: `uv add --dev pytest pytest-cov pyinstaller`
- 実行: `uv run main.py`
- テスト: `uv run pytest --cov=src/rename_date`
- exe ビルド: `uv run pyinstaller installer/rename-date.spec`

## アーキテクチャ（一方向依存）

`main.py(SingleInstanceGuard)` → `views/`(tkinter/ttk) → `controllers/app_controller.py` → `services/`(scanner, rename, undo, log) → `models/`(rename_item, execution_history)

- **Services 層は tkinter を import しない**（GUI なしでテスト可能な状態を維持）。
- 配置は `src/rename_date/{models,services,controllers,views}`。

## 変更してはいけない契約（ドキュメント確認なしに変えない）

- 正規表現は**年・月・日の3キャプチャグループ固定**。グループ数が3でない/コンパイル失敗時は `InvalidPatternError` を送出し走査しない。
- 置換対象は `Path.stem` のみ。拡張子は不可侵。
- 1ファイル名中の**すべてのマッチ**を `re.sub` で置換。月日はゼロ埋めし `YYYYMMDD` に連結、括弧は除去。
- 日付妥当性は `datetime.date(y, m, d)` で検証。`ValueError` → `ItemStatus.INVALID_DATE` とし実行対象外（プレビューには表示するが実行しない）。
- 置換後は連続空白を1つに畳み前後をトリム。置換後 stem が元と同一なら結果リストから除外（非表示）。
- 名前衝突は `_1`, `_2` … で自動回避。比較は大小文字を区別しない `casefold()`。解決した項目は `ItemStatus.RESOLVED_CONFLICT`。
- 変更対象は**ファイルのみ**（フォルダ名は変更しない）。
- 走査除外: 隠しファイル/フォルダ（`.` 始まり or `FILE_ATTRIBUTE_HIDDEN`）、既定除外ディレクトリ（`.git`, `.svn`, `.hg`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`）、シンボリックリンク/ジャンクション（`os.walk(followlinks=False)`、`dirnames` をその場で書き換えて探索打ち切り）。
- リネームは **`Path.rename()`** のみ使用。`os.replace()` は無断上書きするため禁止。
- 実行時例外: `FileExistsError` → `SKIPPED`、`PermissionError`/その他 `OSError` → `ERROR` として記録し処理継続（中断しない）。
- Undo 履歴はメモリ上の LIFO スタックのみ（永続化しない、アプリ終了で破棄）。復元は**実行時と逆順**、欠損/競合時は該当項目のみ `SKIPPED` として継続。
- 走査・実行・Undo は必ずワーカースレッドで行い、UI 更新は `widget.after(0, ...)` 経由。`threading.Event` でキャンセルに対応できること。
- 多重起動抑止は名前付きミューテックス（`ctypes` の `CreateMutexW`）で行う。ロックファイル方式は使わない。

## ログ

- 出力先: `%APPDATA%\rename-date\logs\rename_log.txt`、UTF-8、TSV。
- `logging.handlers.RotatingFileHandler`: `maxBytes=1MiB`, `backupCount=5`, `delay=True`。
- ロガー名 `rename_date.audit`、`propagate=False`（ルートへの二重出力防止）。
- 書式: `<ISO8601>\t<session_id>\t<action:RENAME|UNDO>\t<status>\t<変更前パス>\t<変更後パス>\t<メッセージ>`。ファイル名中のタブ・改行はエスケープしてから書き込む。

## 実装計画書のルール

- 実装計画書を作成する際は、以下のルールを守ること
  - **目的**: 何のために実装するのかを明確にする。
  - **要件**: 満たすべき仕様を明確にする。
  - **タスク**: 実装者が理解できるよう、具体的かつ段階的に記述し、完了確認用のチェックボックス（- [ ]）を配置する。

## 実装時のルール

- **重要**: 実装計画書に従って実装するときは、各タスクの完了確認後、実装計画書のチェックボックスを埋めること。

## テスト方針

- Services 層カバレッジ目標 85%以上。ファイルシステムはモックせず `tmp_path` フィクスチャで実 I/O 検証。
- 対応表: `test_scanner.py` / `test_renamer.py` / `test_undo.py` / `test_log.py`。

## スコープ外（実装しない）

プレビューの個別チェック選択、Redo、フォルダ名リネーム、Undo 履歴の永続化、正規表現以外の変換ルール、除外パターンの GUI 編集、設定の永続化、多言語対応。
