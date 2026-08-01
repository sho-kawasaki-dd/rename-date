# Phase 2: GUI コンポーネントのモジュール化 実装計画書

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) 第6章 Phase 2（GUIコンポーネントのモジュール化）、第4.1章（画面機能）。

## 目的

Models / Services 層（Phase 1 で完成済み）に依存せず、`ConfigFrame` / `PreviewFrame` / `ActionFrame` / `MainWindow` の各 View を実装し、ダミーデータを用いた手動確認によって画面表示・レイアウト・基本操作（対象選択・ドラッグ&ドロップ・パターンプリセット編集・プレビュー表示・実行系ボタンの状態遷移）が正しく動作することを確認する。本フェーズでは `AppController`（Phase 3）を実装しないため、View と Controller の連携はコンストラクタ引数 + `set_callbacks(**kwargs)` によるコールバック注入方式のインターフェースとして定義するに留め、実際のビジネスロジック呼び出しは行わない。

## 要件

- Views 層は `services/validation.py`（副作用のない純粋な検証関数）以外の Services を直接 import しないこと。`ScannerService` / `RenameService` / `UndoService` / `PatternService` / `OutputTemplateService` の呼び出しは Phase 3 の `AppController` がコールバック経由で行う。
- 各 Frame はコンストラクタでコールバック関数（既定値は no-op）を受け取り、`set_callbacks(**kwargs)` で後から差し替え可能にすること。
- `ConfigFrame`（開発計画書4.1章-1）:
  - 対象パスは `filedialog.askdirectory` によるフォルダ選択、および `tkinterdnd2` によるフォルダ/ファイルのドラッグ&ドロップの両方で追加できること。
  - 選択済み/ドロップ済みの対象は Listbox に一覧表示し、個別に削除できること。追加時は `Path.resolve()` + `casefold()` で重複を除去すること。
  - 正規表現パターンは**複数選択可能な一覧**（`Listbox(selectmode="extended")` 等）でパターンプリセット名から選択できること。選択順序は一覧の表示順とし、`get_selected_patterns() -> list[PatternEntry]` は表示順（＝適用順）でリストを返すこと。
  - 出力テンプレートは `ttk.Combobox`（readonly、単一選択）で出力テンプレートプリセット名から選択できること。`get_selected_template() -> OutputTemplateEntry | None` を公開すること。
  - パターンプリセットの新規作成・編集はモーダルダイアログ（`PatternEditDialog`、name+pattern のみを扱う）で行い、保存前に `services.validation.compile_pattern` で即時検証してエラーを表示すること。出力テンプレートプリセットの新規作成・編集は別のモーダルダイアログ（`OutputTemplateEditDialog`、name+template のみを扱う）で行い、保存前に `services.validation.validate_output_template` で即時検証してエラーを表示すること。
  - いずれのプリセット編集時も `name` を読み取り専用にすること（`upsert` は `name` 一致で上書きするため、改名を許すと旧エントリが孤児化するのを防ぐ）。改名したい場合は新規作成＋旧削除で対応する運用とする。
  - プリセット削除（パターン・出力テンプレートとも）は確認ダイアログ（`messagebox.askyesno`）を経てから対応するコールバック（`on_pattern_delete` / `on_template_delete`）を呼ぶこと。
  - 「プレビュー更新」ボタン押下で `on_preview_request` コールバックを呼ぶこと。
- `PreviewFrame`（開発計画書4.1章-2）:
  - `ttk.Treeview` で 状態 / 変更前ファイル名 / 変更後ファイル名 / パス の4列を表示すること。表示専用とし、個別チェックによる取捨選択は行わない。
  - `set_items(items, base_dir=None)` で `RenameItem` のリストを描画すること。`base_dir` 指定時はそれからの相対パス、未指定時またはリンク失敗時はフルパスを表示すること。
  - `ItemStatus.INVALID_DATE` は灰色表示、`ItemStatus.RESOLVED_CONFLICT` は背景色（薄い黄色）で強調表示すること。
- `ActionFrame`（開発計画書4.1章-3）:
  - 実行対象件数・無効件数を表示すること。
  - 「一括変換を実行」「Undo」ボタンを持ち、Undo は既定で無効化され `set_undo_enabled(bool)` で活性化できること。
  - ログ保存の可否を `ttk.Checkbutton` で選択できること（既定 ON）。
  - `ttk.Progressbar`（determinate）とステータスラベル、処理中のみ有効化される「キャンセル」ボタンを持つこと。`set_processing(bool)` で実行中は実行/Undoボタンを無効化しキャンセルボタンを有効化すること。
- `MainWindow`（開発計画書3.2章・付録コメント）:
  - `tkinterdnd2.TkinterDnD.Tk` をルートウィンドウとすること（ドラッグ&ドロップに必須）。
  - `ConfigFrame` を上段、`PreviewFrame` を中段、`ActionFrame` を下段に配置し、**`PreviewFrame` のみ**が伸縮するようグリッドの重み付けを行うこと。
  - `config_frame` / `preview_frame` / `action_frame` をパブリック属性として公開し、Phase 3 の `AppController` からコールバックを差し替えられるようにすること。
- 動作確認は自動テストではなく、`scripts/demo_views.py`（新規、配布対象外の開発用スクリプト）でダミーの `PatternEntry` / `RenameItem` を各 Frame に流し込んだ上での目視確認とする（開発計画書11章のテスト方針に View 自動テストは含まれないため）。

## タスク

### 1. `PatternEditDialog` / `OutputTemplateEditDialog`（新規）

- [x] `src/rename_date/views/pattern_dialog.py`（新規作成）: `PatternEditDialog(tk.Toplevel)` を実装する。コンストラクタは `parent`, `initial: PatternEntry | None = None` を受け取る。
- [x] name / pattern の2つの `ttk.Entry` を配置する。`initial` が指定された場合は値を初期表示し、`initial` がある場合（編集モード）は name の Entry を読み取り専用（`state="readonly"` または `state="disabled"`）にする。
- [x] 「OK」ボタン押下時に `services.validation.compile_pattern(pattern)` を呼び、`InvalidPatternError` を捕捉して `ttk.Label` 等でエラーメッセージを表示し、ダイアログを閉じないこと。
- [x] 検証成功時は `self.result = PatternEntry(name, pattern)` を設定してダイアログを閉じる。「キャンセル」ボタン押下時は `self.result = None` とする。呼び出し元は `dialog.wait_window()` 後に `dialog.result` を参照する。
- [x] `src/rename_date/views/output_template_dialog.py`（新規作成）: `OutputTemplateEditDialog(tk.Toplevel)` を実装する。コンストラクタは `parent`, `initial: OutputTemplateEntry | None = None` を受け取り、name / template の2つの `ttk.Entry` を配置する。編集モードでは name を読み取り専用にする。
- [x] `OutputTemplateEditDialog` の「OK」ボタン押下時に `services.validation.validate_output_template(template)` を呼び、`InvalidTemplateError` を捕捉してエラーメッセージを表示し、ダイアログを閉じないこと。検証成功時は `self.result = OutputTemplateEntry(name, template)` を設定する。「キャンセル」時は `self.result = None` とする。

### 2. `ConfigFrame`

- [x] `src/rename_date/views/config_frame.py`: `ConfigFrame(ttk.Frame)` を実装する。コンストラクタ引数 `on_pattern_save`, `on_pattern_delete`, `on_template_save`, `on_template_delete`, `on_preview_request`（すべて既定 no-op の `Callable`）と `set_callbacks(**kwargs)` を定義する。
- [x] 対象パス欄: `Listbox` + 「フォルダ選択...」ボタン（`filedialog.askdirectory` で選択したフォルダを追加）+「選択項目を削除」ボタン（Listbox の選択行を内部リストと表示から削除）を配置する。
- [x] Listbox を `drop_target_register(DND_FILES)` でドロップ対象として登録し、`<<Drop>>` イベントで `event.data` を解析するヘルパー（中括弧`{}`で囲まれたパスを含む空白区切り文字列をパスのリストに分解する）を実装し、フォルダ・ファイルの両方を対象リストに追加する。
- [x] 内部状態 `self._targets: list[Path]` を持ち、追加時は `Path.resolve()` + `casefold()` 比較で重複を除外する。`get_targets() -> list[Path]` を公開する。
- [x] パターンプリセット欄: `Listbox(selectmode="extended")`（表示は `PatternEntry.name`、複数選択可）+「新規」「編集」「削除」ボタンを配置する。`set_patterns(entries: list[PatternEntry]) -> None` で一覧を更新し、`get_selected_patterns() -> list[PatternEntry]` を一覧の表示順（＝適用順）で公開する。
- [x] 出力テンプレート欄: `ttk.Combobox`（`state="readonly"`、単一選択、表示は `OutputTemplateEntry.name`）+「新規」「編集」「削除」ボタンを配置する。`set_templates(entries: list[OutputTemplateEntry]) -> None` で選択肢を更新し、`get_selected_template() -> OutputTemplateEntry | None` を公開する。
- [x] パターンの「新規」ボタン: `PatternEditDialog(self, initial=None)` を開き、`dialog.result` が得られたら `self._on_pattern_save(dialog.result)` を呼ぶ。「編集」ボタンは選択中の1件（複数選択時は先頭）で同ダイアログを開く。「削除」ボタンは `messagebox.askyesno` で確認後 `self._on_pattern_delete(selected.name)` を呼ぶ。
- [x] 出力テンプレートの「新規」「編集」「削除」ボタンは同様に `OutputTemplateEditDialog` と `on_template_save` / `on_template_delete` を用いて実装する。
- [x] 「プレビュー更新」ボタン: `self._on_preview_request()` を呼ぶ。

### 3. `PreviewFrame`

- [x] `src/rename_date/views/preview_frame.py`: `PreviewFrame(ttk.Frame)` を実装する。
- [x] `ttk.Treeview(columns=("status", "original_name", "target_name", "path"), show="headings")` を配置し、見出し（状態/変更前ファイル名/変更後ファイル名/パス）を設定する。
- [x] `set_items(items: list[RenameItem], base_dir: Path | None = None) -> None`: 既存行をクリアしてから各 `RenameItem` を挿入する。パス列は `base_dir` 指定時 `original_path.parent.relative_to(base_dir)`、`ValueError` 発生時または未指定時は `str(original_path.parent)` とする。
- [x] `tag_configure("invalid", foreground="gray")` / `tag_configure("conflict", background="#fff8b0")` を設定し、`ItemStatus.INVALID_DATE` / `ItemStatus.RESOLVED_CONFLICT` の行にそれぞれタグを付与する。
- [x] `items` が空の場合の表示（プレースホルダ行またはラベルで「対象がありません」）を実装する。

### 4. `ActionFrame`

- [x] `src/rename_date/views/action_frame.py`: `ActionFrame(ttk.Frame)` を実装する。コンストラクタ引数 `on_execute`, `on_undo`, `on_cancel`（既定 no-op）と `set_callbacks(**kwargs)` を定義する。
- [x] 件数表示ラベル: `set_counts(executable: int, invalid: int, total: int) -> None` で「実行対象: N件 / 無効: M件 / 合計: T件」形式の文字列を更新する。
- [x] 「一括変換を実行」ボタン（押下で `on_execute()`）、「Undo」ボタン（押下で `on_undo()`、既定 disabled）を配置し、`set_undo_enabled(bool) -> None` を公開する。
- [x] 「ログ保存」`ttk.Checkbutton`（`BooleanVar`、既定 `True`）を配置し、`get_log_enabled() -> bool` を公開する。
- [x] `ttk.Progressbar(mode="determinate")` とステータス `ttk.Label` を配置し、`set_progress(value: int) -> None` / `set_status(text: str) -> None` を公開する。
- [x] 「キャンセル」ボタン（押下で `on_cancel()`）を配置し、`set_processing(is_processing: bool) -> None` で処理中は実行/Undoボタンを無効化しキャンセルボタンを有効化、非処理中は逆にする。

### 5. `MainWindow`

- [ ] `src/rename_date/views/main_window.py`: `MainWindow(tkinterdnd2.TkinterDnD.Tk)` を実装する。
- [ ] タイトル・既定サイズ（例: `900x600`）・`minsize` を設定する。
- [ ] `grid` レイアウトで `ConfigFrame` を上段（`row=0, sticky="ew"`）、`PreviewFrame` を中段（`row=1, sticky="nsew"`）、`ActionFrame` を下段（`row=2, sticky="ew"`）に配置し、`rowconfigure(1, weight=1)` / `columnconfigure(0, weight=1)` で `PreviewFrame` のみを伸縮させる。
- [ ] `self.config_frame` / `self.preview_frame` / `self.action_frame` をパブリック属性として公開する。

### 6. 手動デモスクリプト

- [ ] `scripts/`（新規ディレクトリ、配布対象外）を作成する。
- [ ] `scripts/demo_views.py`（新規作成）: 先頭コメントで「開発用の手動確認スクリプトであり配布物には含めない」旨を明記する。`MainWindow` を生成し、ダミーの `PatternEntry` リスト（複数件）とダミーの `OutputTemplateEntry` リスト（複数件）、ダミーの `RenameItem` リスト（`PENDING` / `INVALID_DATE` / `RESOLVED_CONFLICT` を含む）、ダミーの件数を各 Frame の `set_patterns` / `set_templates` / `set_items` / `set_counts` に渡し、コールバックには `print()` するのみのダミー関数を注入して `mainloop()` を起動する。

### 7. 動作確認

- [ ] `uv run python scripts/demo_views.py` を実行し、フォルダ選択・ドラッグ&ドロップでの対象追加・個別削除、パターンプリセットの**複数選択**と新規/編集（不正な正規表現でエラー表示されること）/削除（確認ダイアログ）、出力テンプレートプリセットの単一選択と新規/編集（不正なテンプレートでエラー表示されること）/削除、プレビュー更新ボタンのコールバック発火、Treeview での灰色（無効）・強調表示（衝突）、進捗バー・ステータス・件数ラベルの更新、Undoボタンの活性/非活性切り替えを目視確認する。
- [ ] `uv run pytest --cov=src/rename_date` を実行し、既存テスト（Services層）に回帰がないことを確認する。
- [ ] Pylance等の静的検査でエラーが出ていないことを確認する。

## スコープ外（本フェーズで実装しないこと）

- `AppController` の実装、View と実サービスの実際の連携（Phase 3）
- ワーカースレッド化・進捗の実データ反映・`cancel_event` を用いた実キャンセル処理（Phase 3）
- `single_instance.py` の実ロジック、`__main__.py` の実処理（Phase 3）
- View に対する pytest 自動テスト（開発計画書11章のテスト方針に含まれないため、手動デモスクリプトでの目視確認に留める）
- PyInstaller / Inno Setup の実設定内容、ビルド後の実行ファイルでのドラッグ&ドロップ動作検証（Phase 4）
- Redo、フォルダ名リネーム、Undo履歴の永続化など、開発計画書12章記載のスコープ外事項
