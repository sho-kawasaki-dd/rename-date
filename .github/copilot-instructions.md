# Project Guidelines — rename-date

Windows 向け tkinter GUI アプリ。指定フォルダを再帰走査、またはドラッグ&ドロップされた個別ファイルを対象に、正規表現で年月・単日・期間をマッチし、年月テンプレート（既定 `{Y}-{M}`）、単日テンプレート（既定 `{Y}{M}{D}`）または期間テンプレート（既定 `{Y}{M}{D}-{Y2}{M2}{D2}`）へ一括変換する。全仕様は [docs/rename-date開発計画書.md](../docs/rename-date開発計画書.md) を参照。このファイルには「必ず守るべき契約」と「頻繁に間違えやすい点」のみを記載する。

## 環境 & コマンド

- Python 3.12+、パッケージ/環境管理は **uv**（pip/venv を直接使わない）。
- 初期化: `uv init --app --package .`（src レイアウト）
- 依存追加: `uv add tkinterdnd2`、`uv add --dev pytest pytest-cov pyinstaller`
- 実行: `uv run main.py`
- テスト: `uv run pytest --cov=src/rename_date`
- exe ビルド: `uv run pyinstaller installer/rename-date.spec`（`tkinterdnd2` の tcl アセット同梱を要確認）

## アーキテクチャ（一方向依存）

`main.py(SingleInstanceGuard)` → `views/`(tkinter/ttk + tkinterdnd2) → `controllers/app_controller.py` → `services/`(scanner, rename, undo, log, pattern, output template, date span) → `models/`(rename_item, execution_history, pattern_entry, output_template_entry)

- **Services 層は tkinter を import しない**（GUI なしでテスト可能な状態を維持）。
- 配置は `src/rename_date/{models,services,controllers,views}`。

## 変更してはいけない契約（ドキュメント確認なしに変えない）

- 正規表現のキャプチャグループ数で種類を判定する。2は年月（Y/M）、3は単日（Y/M/D）、4は期間（Y/M/D/D2）、5は期間（Y/M/D/M2/D2）、6は期間（Y/M/D/Y2/M2/D2）。コンパイル失敗時またはグループ数が2〜6以外の場合は `InvalidPatternError` を送出し走査しない。
- 適用順は期間→単日→年月。各種別内の相対順は一覧の表示順を保つ（安定ソート）。先行パターンの変換後文字列が後続パターンに再マッチする場合があるため、併用時はパイプライン結果をプレビューで確認する。
- 期間用テンプレートは `%APPDATA%\rename-date\config\range_output_templates.json` に保存する。既存の単日テンプレートは `output_templates.json` と別管理。期間テンプレートは `{Y}` `{M}` `{D}` `{Y2}` `{M2}` `{D2}` を各1回以上含むことが必須。`{Y2}` は元の名前に終了年がある場合だけ出力し、無ければ空文字。`{Y2}` の直後に区切り文字を置くテンプレートでは区切り文字が残る場合がある。
- 年月用テンプレートは `%APPDATA%\rename-date\config\month_output_templates.json` に保存し、既存の単日・期間テンプレートと別管理する。既定は `{Y}-{M}`。`{Y}` と `{M}` を各1回以上含め、他のプレースホルダー・不正な波括弧・Windowsのファイル名禁止文字および制御文字を含めない。
- 標準の年月パターンは年月の期間表記（年月同士が `-`・`〜`・`～` で空白なく接続）を両端とも除外する。年月ルールは拡張子が `.[0-9]{1,2}` の場合も適用しない。他のパターン種別にはこの拡張子除外を適用しない。
- 置換対象は `Path.stem` のみ。拡張子は不可侵。
- 1ファイル名中の**すべてのマッチ**を `re.sub` で置換。年月は `{Y}-{M}`、単日は `{Y}{M}{D}`、期間は `{Y}{M}{D}-{Y2}{M2}{D2}` を既定とする。年月・単日は `{Y}`=4桁、`{M}`=2桁、単日の `{D}`=2桁、期間は開始日・補完後の終了日を同じ桁数で描画し、括弧は除去する。
- 正規表現パターンは `PatternEntry`（`name` + `pattern`）として `%APPDATA%\rename-date\config\patterns.json` に永続化。年月・単日・期間テンプレートは `OutputTemplateEntry`（`name` + `template`）としてそれぞれ `month_output_templates.json`、`output_templates.json`、`range_output_templates.json` に永続化。GUI から選択・追加・編集・削除可能（各プリセットで最後の1件は削除不可）。
- 年月は `datetime.date(y, m, 1)` で年・月を検証し、単日・期間は `datetime.date(y, m, d)` で検証する。期間では終了日の省略を開始日から補い、月・年の繰り上げは数値比較で判定してから `date()` を生成する。終了年が明示された場合は終了日が開始日より前なら無効。`ValueError` → `ItemStatus.INVALID_DATE` とし実行対象外（プレビューには表示するが実行しない）。
- 置換後は連続空白を1つに畳み前後をトリム。置換後 stem が元と同一なら結果リストから除外（非表示）。
- 名前衝突は `_1`, `_2` … で自動回避。比較は大小文字を区別しない `casefold()`。解決した項目は `ItemStatus.RESOLVED_CONFLICT`。
- 変更対象は**ファイルのみ**（フォルダ名は変更しない）。
- 走査除外: 隠しファイル/フォルダ（`.` 始まり or `FILE_ATTRIBUTE_HIDDEN`）、既定除外ディレクトリ（`.git`, `.svn`, `.hg`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`）、シンボリックリンク/ジャンクション（`os.walk(followlinks=False)`、`dirnames` をその場で書き換えて探索打ち切り）。
- 対象指定はフォルダ選択（再帰走査）に加え、フォルダ/ファイルのドラッグ&ドロップに対応（`tkinterdnd2`）。ドロップされたフォルダは再帰走査、ファイルは走査せず直接リネーム対象に追加。混在時は両方の結果を合算し `Path.resolve()` で重複除去。
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
- 対応表: `test_scanner.py` / `test_renamer.py` / `test_undo.py` / `test_log.py` / `test_pattern_service.py` / `test_output_template_service.py` / `test_validation.py` / `test_date_span.py` / `test_app_controller.py`。

## スコープ外（実装しない）

プレビューの個別チェック選択、Redo、フォルダ名リネーム、Undo 履歴の永続化、正規表現以外の変換ルール、除外パターンの GUI 編集、フォルダ選択履歴の永続化、多言語対応。
