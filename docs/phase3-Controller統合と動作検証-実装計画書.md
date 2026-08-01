# Phase 3: Controller による統合と動作検証 実装計画書

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) 第6章 Phase 3、第4.2章（サービスロジック要件）、
第7章（例外処理・安全対策方針）、第9章（多重起動抑止）。

## 目的

Phase 1（Models / Services）・Phase 2（Views）で実装済みの各層を `AppController` で結線し、
実際にフォルダ／ファイルを対象としたプレビュー→一括変換→Undoの一連の操作をワーカースレッド上で
実行できる状態にする。あわせて `single_instance.py` による多重起動抑止と、`__main__.py` からの
アプリケーション起動処理を実装し、Phase 4（配布パッケージング）に進める状態にする。

## 決定事項（本計画に先立ちユーザーと合意済み）

1. **進捗表示**: `ScannerService.scan()` / `RenameService.execute()` / `UndoService.undo()` に
   後方互換な `progress_callback: Callable[[int, int], None] | None = None` 引数を追加し、
   ファイル単位の実進捗を `ActionFrame` の determinate progressbar に反映する。
2. **Undo監査ログの `session_id`**: `UndoService` は変更せず、`AppController` が Undo 実行のたびに
   `uuid.uuid4().hex[:8]` を新規発行し `LogService.log_undo()` に渡す。
3. **ログ保存チェックボックスの適用範囲**: `ActionFrame.get_log_enabled()` は一括変換(RENAME)と
   Undo(UNDO)の両方のログ記録を制御する（個別制御はしない）。
4. **実行/Undo後のプレビュー更新**: 完了後は直前に使用したスキャンパラメータ（対象・選択パターン列・
   出力テンプレート）で自動的に再スキャンし、プレビューと件数表示を最新状態に更新する。
5. **多重起動時の前面化**: `ctypes` 経由の `FindWindowW(None, "rename-date")` +
   `SetForegroundWindow` で実装する。ウィンドウが見つからない場合のみメッセージボックスを表示する。
6. **終了処理（`WM_DELETE_WINDOW`）**: タイムアウト付き `join()` は採用しない。処理中でなければ
   即座に閉じる。処理中の場合は確認ダイアログ（「処理中です。中断して終了しますか？（ここまでの変更は
   ログ・Undo履歴に記録されない場合があります）」）を表示し、承諾時のみ `cancel_event.set()` を呼んだ上で
   `join()` せずに即 `window.destroy()` する（ワーカースレッドは `daemon=True` のためプロセス終了時に
   自動的に破棄される）。

## 要件

- `AppController` は tkinter に直接依存する Services 層の呼び出しをすべて仲介し、View からは
  コンストラクタ注入 / `set_callbacks(**kwargs)` 経由でのみ呼び出されること（Views 層は Services を
  直接 import しない、という Phase 2 の方針を維持する）。
- 走査・実行・Undo は必ずワーカースレッド（`threading.Thread(daemon=True)`）で行い、UI 更新は
  `widget.after(0, ...)` を経由してメインスレッドで行うこと。
- 各操作は `cancel_event: threading.Event` を都度新規生成して Services に渡し、キャンセルボタン押下時に
  `.set()` すること。
- 多重操作防止のため、いずれかの操作（プレビュー/実行/Undo）が進行中は他の操作開始要求を無視すること。
- パターン・出力テンプレートの保存/削除は `PatternService` / `OutputTemplateService` の例外
  （`InvalidPatternError` / `InvalidTemplateError` / 最後の1件削除時の `ValueError`）を捕捉し、
  `messagebox.showerror` で通知すること。
- 単体テストはウィジェットを実際に起動せず、`MainWindow` / 各 Frame と同じ公開インターフェースを持つ
  フェイクのテストダブル（`after(delay, func, *args)` は即座に同期実行する）を用いて `AppController` の
  ロジックのみを検証すること。

## タスク

### 1. サービス層への進捗コールバック追加（前提作業）

- [x] `src/rename_date/services/scanner_service.py`: `scan()` に
      `progress_callback: Callable[[int, int], None] | None = None` を追加する。
      `_collect_files()` で得たファイル数を `total` とし、結果ループの各反復終了時
      （マッチなし・無効日付で `continue` するケースも含め、対象ファイル1件につき必ず1回）に
      `progress_callback(index, total)` を呼ぶ。
- [x] `src/rename_date/services/rename_service.py`: `execute()` に同様の `progress_callback` を追加する。
      `result_items` の長さを `total` とし、実行対象外でスキップする項目も含めループの各反復ごとに呼ぶ。
- [x] `src/rename_date/services/undo_service.py`: `undo()` に同様の `progress_callback` を追加する。
      `history.items` の長さを `total` とし、`reversed(history.items)` の各反復ごとに呼ぶ。
- [x] `tests/test_scanner.py` / `tests/test_renamer.py` / `tests/test_undo.py` に、
      `progress_callback` に渡した収集用リストが最終的に `(len, len)` で終わる正しい系列で
      呼ばれることを検証するテストケースを追加する。既定値 `None` のため既存テストは無改修で
      通過することを確認する。

### 2. `single_instance.py` の実装

- [x] `src/rename_date/single_instance.py`: `SingleInstanceGuard` クラスをコンテキストマネージャとして
      実装する。ミューテックス名は `r"Local\rename-date-single-instance"` の固定文字列とする。
- [x] `__enter__`: `ctypes.windll.kernel32.CreateMutexW(None, False, ミューテックス名)` を呼び、
      `ctypes.get_last_error()`（`use_last_error=True` を設定するか `GetLastError()` を用いる）が
      `ERROR_ALREADY_EXISTS`（1183）の場合に `self.already_running = True` を設定する。
- [x] `__exit__`: 取得したハンドルを `CloseHandle` で解放する。
- [x] `activate_existing_window() -> bool`: `ctypes.windll.user32.FindWindowW(None, "rename-date")` で
      既存ウィンドウの `hwnd` を検索し、見つかれば `SetForegroundWindow(hwnd)` を呼んで `True` を返す。
      見つからなければ `False` を返す。`MainWindow` の `title()` と文字列を一致させること。

### 3. `AppController` の実装

`src/rename_date/controllers/app_controller.py` に `AppController` を実装する。コンストラクタは
`MainWindow` と6つのサービスインスタンス（`ScannerService` / `RenameService` / `UndoService` /
`LogService` / `PatternService` / `OutputTemplateService`）を受け取る（依存性注入）。

- [x] **初期化**: `pattern_service.load()` / `output_template_service.load()` の結果を
      `config_frame.set_patterns()` / `set_templates()` に反映する。`config_frame.set_callbacks(...)` /
      `action_frame.set_callbacks(...)` で各ハンドラを登録する。
      `window.protocol("WM_DELETE_WINDOW", self._on_close)` を設定する。
- [x] **内部状態**: `self._busy: bool`（多重操作防止）、`self._cancel_event: threading.Event | None`、
      `self._last_items: list[RenameItem]`、`self._last_base_dir: Path | None`、
      `self._last_scan_params`（再スキャン用に対象パス・パターン文字列列・出力テンプレート文字列を保持）。
- [x] **パターン保存 (`_on_pattern_save`)**: `pattern_service.upsert(entry)` を呼び、
      `InvalidPatternError` を捕捉して `messagebox.showerror`。成功時は `config_frame.set_patterns(...)`
      で一覧を更新する。
- [x] **パターン削除 (`_on_pattern_delete`)**: `pattern_service.delete(name)` を呼び、最後の1件で
      `ValueError` が送出された場合は `messagebox.showerror` で通知する。成功時は一覧を更新する。
- [x] **出力テンプレート保存/削除 (`_on_template_save` / `_on_template_delete`)**: 上記と同様に
      `output_template_service` の `upsert` / `delete` を呼び、例外時はエラーダイアログを表示する。
- [x] **プレビュー要求 (`_on_preview_request`)**:
      1. `self._busy` なら無視する。
      2. `config_frame.get_targets()` / `get_selected_patterns()` / `get_selected_template()` を取得し、
         いずれかが空/`None` であれば `messagebox.showwarning` で通知して中断する。
      3. `base_dir` を決定する: 対象が1件かつ `is_dir()` の場合のみそのフォルダ、それ以外は `None`。
      4. `action_frame.set_processing(True)` / `set_status("プレビューを更新中...")` / `set_progress(0)` を
         呼び、`self._busy = True` とする。
      5. 新規 `threading.Event()` を生成して `self._cancel_event` に保持し、
         `threading.Thread(target=self._scan_worker, args=(...), daemon=True).start()` する。
      6. ワーカー内で `scanner_service.scan(targets, patterns, output_template, cancel_event=..., progress_callback=...)`
         を呼ぶ。`progress_callback` は `window.after(0, lambda d=done, t=total: action_frame.set_progress(int(d / t * 100)))`
         でメインスレッドにマーシャリングする。
      7. `InvalidPatternError` 発生時は `window.after(0, ...)` でエラーダイアログを表示し、
         `set_processing(False)` して終了する。
      8. 正常終了時は `window.after(0, self._on_scan_complete, items, base_dir, cancel_event.is_set())` を
         呼ぶ。`_on_scan_complete` で `preview_frame.set_items(items, base_dir)` /
         `action_frame.set_counts(executable, invalid, total)` / `set_processing(False)` /
         ステータス文言（キャンセル時は「キャンセルされました」）を更新し、`self._last_items` /
         `self._last_base_dir` / `self._last_scan_params` を保存、`self._busy = False` とする。
- [x] **実行 (`_on_execute`)**:
      1. `self._busy` なら無視。`self._last_items` が空なら `messagebox.showwarning`
         （「先にプレビューを更新してください」）で中断する。
      2. `set_processing(True)` / `set_status("実行中...")`。ワーカーで
         `rename_service.execute(self._last_items, cancel_event=..., progress_callback=...)` を呼ぶ。
      3. 完了時（メインスレッド）: 戻り値 `(items, history)` を受け取る。
         `action_frame.get_log_enabled()` が真なら `log_service.log_rename(items, history.session_id)` を
         呼ぶ（成功分のみでなく `items` 全件の最終ステータスをログする）。
      4. `history.items`（成功分）が非空なら `undo_service.push(history)` し
         `action_frame.set_undo_enabled(True)` を呼ぶ。
      5. 決定事項4に従い、`self._last_scan_params` を用いて自動的に再スキャンを実行し、
         プレビュー・件数・ステータスを更新してから `set_processing(False)` / `self._busy = False`。
- [x] **Undo (`_on_undo`)**:
      1. `self._busy` なら無視。`undo_service.has_history()` が偽なら何もしない。
      2. `set_processing(True)` / `set_status("元に戻しています...")`。ワーカーで
         `undo_service.undo(cancel_event=..., progress_callback=...)` を呼ぶ。
      3. 完了時: `get_log_enabled()` が真なら新規 `session_id = uuid.uuid4().hex[:8]` を発行し
         `log_service.log_undo(restored_items, session_id)` を呼ぶ。
      4. `action_frame.set_undo_enabled(undo_service.has_history())` を呼ぶ。
      5. 決定事項4に従い自動再スキャンしてプレビューを更新し、`set_processing(False)` / `self._busy = False`。
- [x] **キャンセル (`_on_cancel`)**: `self._cancel_event` が設定されていれば `.set()` し
      `set_status("キャンセル中...")` を表示する。
- [x] **終了処理 (`_on_close`)**: 決定事項6のとおり実装する。`self._busy` が偽なら即 `window.destroy()`。
      真なら `messagebox.askyesno` で確認し、「はい」の場合のみ `self._cancel_event` があれば `.set()` を
      呼び、`join()` せずに即 `window.destroy()` する。「いいえ」の場合は何もしない。

### 4. `__main__.py` / `main.py` の統合

- [x] `src/rename_date/__main__.py` の `main()` を実装する。
      1. `SingleInstanceGuard()` を `with` で使用する。`already_running` が真なら
         `activate_existing_window()` を試み、失敗した場合のみ一時的な非表示 `tk.Tk()` ルート経由で
         `messagebox.showinfo`（「既に起動しています」）を表示して終了する。
      2. `PatternService` / `OutputTemplateService` / `ScannerService` / `RenameService` /
         `UndoService` / `LogService` を生成する。
      3. `MainWindow()` を生成し、`AppController(window, ...)` を生成する。
      4. `window.mainloop()` を呼ぶ。
      5. `finally` 節で `log_service.close()` と `logging.shutdown()` を呼ぶ。
- [x] ルートの `main.py` は現状の委譲コードのまま変更不要であることを確認する。

### 5. テスト

- [x] `tests/test_app_controller.py`（新規作成）: 実際の tkinter ウィジェットではなく、
      `MainWindow` / `ConfigFrame` / `PreviewFrame` / `ActionFrame` と同じ公開インターフェースを持つ
      フェイクのテストダブル（`after(delay, func, *args)` は即座に同期実行）を用意し、`mainloop` を
      起動せずに以下を検証する。
      - プレビュー要求 → `ScannerService.scan()` が正しい引数で呼ばれ、結果が
        `preview_frame.set_items` / `action_frame.set_counts` に反映されること。
      - 対象/パターン/テンプレート未選択時に警告のみで `scan()` が呼ばれないこと。
      - 実行 → `RenameService.execute()` 呼び出し → ログ記録（ログ保存チェックON/OFF双方）→
        `UndoService.push()` → 自動再スキャンが行われること。
      - Undo → `UndoService.undo()` 呼び出し → 毎回新しい `session_id` でログ記録されること →
        自動再スキャンが行われること。
      - キャンセルボタンで `cancel_event.set()` が呼ばれること。
      - パターン/出力テンプレートの保存・削除が正常系・異常系（不正パターン、最後の1件削除）で
        期待どおりに動作すること。
      - 処理中に別の操作要求が来ても無視されること（多重操作防止）。
      - `_on_close` が非処理中/処理中（確認ダイアログの承諾・拒否）それぞれで期待どおりに動作すること。
      - `tests/conftest.py` の `sample_tree` / `default_pattern` / `default_output_template` フィクスチャを
        再利用する。

### 6. 動作確認

- [x] `uv run pytest --cov=src/rename_date` を実行し、既存テスト・新規テストがすべて通過し、
      Services 層カバレッジ 85% 以上を維持していることを確認する。
- [x] `uv run main.py` を実行し、開発計画書11.2章のダミーフォルダ構造でプレビュー→実行→Undoの
      一連を確認する。
- [x] `%APPDATA%\rename-date\logs\rename_log.txt` に `RENAME` / `UNDO` の行が記録されることを確認する。
- [x] アプリを二重起動し、既存ウィンドウが前面化されることを確認する。
- [x] 大量ファイルを対象に走査・実行中の進捗バー更新とキャンセルボタンの動作を確認する。
- [x] 処理中に閉じるボタンを押した際の確認ダイアログの挙動を確認する。
- [x] Pylance等の静的検査でエラーが出ていないことを確認する。

## スコープ外（本フェーズで実装しないこと）

- PyInstaller (`installer/rename-date.spec`) / Inno Setup (`installer/setup.iss`) の実設定・
  ビルド・配布検証（Phase 4）。
- Redo、フォルダ名リネーム、Undo履歴の永続化など、開発計画書12章記載のスコープ外事項。
- View に対する実 tkinter ウィジェットを用いた自動テスト（Phase 2 の方針を踏襲し、
  `AppController` のテストはフェイクのテストダブルに留める）。
