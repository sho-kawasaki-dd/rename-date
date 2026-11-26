# Phase 7: 年月表記対応 実装計画書（v0.4.0）

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) の変換・プリセット仕様。[Phase 5](./phase5-期間表記対応-実装計画書.md) のパターン種別判定と [Phase 6](./phase6-プリセットJSON保存・取込-実装計画書.md) のプリセット入出力を拡張する。

## 目的

`売上_2026.7.pdf` を `売上_2026-07.pdf` に変換できるようにする。年月を単日・期間とは別の種別として扱い、既存の変換結果や設定を維持したまま、同じプレビューで併用できるようにする。この改修を含むアプリとインストーラーのバージョンを `v0.4.0` とする。

## 要件

### A. 入力パターンと変換

- 正規表現のキャプチャグループ数で判定する。**2グループは年月（年、月）**とし、3は単日、4〜6は期間のまま変更しない。コンパイル失敗または2〜6以外のグループ数は `InvalidPatternError` とし、保存・取込・走査を拒否する。
- 入力パターン一覧は共用し、年月の項目に `[年月]` を表示する。`patterns.json` は引き続き `name` と `pattern` の配列を使う。既存・新規の設定に年月パターンは自動追加せず、利用者が新規作成または取込し、選択した場合に適用する。
- 標準の入力例は `(?<![0-9])([0-9]{4})\.([0-9]{1,2})(?![0-9]|[.-][0-9])` とする。`YYYY.M`・`YYYY.MM` にマッチし、`2026.11.26.pdf`・`2026.11-26.pdf` のような続きに数字がある表記を部分変換しない。独自パターンでは対象の表記に合わせて境界を指定し、プレビューで確認する。
- 適用順は **期間 → 単日 → 年月**。同種内は一覧順を維持し、先行ルールの出力に後続ルールを適用する既存の逐次置換を維持する。各パターンのすべてのマッチを置換し、空白の正規化・変更なしの非表示・名前衝突の回避は既存処理を使う。
- 年は1〜9999、月は1〜12を有効とし、年は4桁、月は2桁にゼロ埋めする。非数値や必須グループの欠落も不正とする。1箇所でも不正な年月にマッチしたファイルは `ItemStatus.INVALID_DATE` としてプレビューに残し、部分的に変換して実行しない。
- 書き換えるのは `Path.stem` のみとし、拡張子を変更しない。`2026.11` 単独は stem が `2026` になるため対象外。`2026.11.26` は stem が `2026.11` になるため、**拡張子がドットに続く1〜2桁の半角数字だけなら、年月ルールを適用しない**。この除外は年月ルールに限り、単日・期間には影響させない。

### B. 年月出力テンプレートとJSON入出力

- 既定プリセット名は `既定 YYYY-MM`、既定テンプレートは `{Y}-{M}` とする。`{Y}` と `{M}` を各1回以上含め、他のプレースホルダー・対応しない波括弧（ネストした波括弧を含む）・Windowsのファイル名禁止文字は拒否する。単日・期間のテンプレート検証は変更しない。
- `%APPDATA%\rename-date\config\month_output_templates.json` に `name` と `template` の配列として別保存する。ファイルがない場合は既定1件を作成する。既存の内部設定3ファイルを移行・書き換えしない。
- メイン画面に年月用テンプレートの選択・追加・編集・削除を追加し、最後の1件は削除できないようにする。年月パターンの選択時だけ年月用テンプレートの選択を必須にし、未選択なら警告して走査しない。年月パターン未選択かつ年月用テンプレート未選択時は既定テンプレート `{Y}-{M}` を補って走査し、既存の単日・期間の選択条件は変えない。選択パターンの種別確認時にコンパイル不能なパターンが含まれていても UI スレッドで落とさず、従来の走査エラー通知へ流す。
- 「プリセット」メニューに「年月出力テンプレート」を追加し、Phase 6 と同様に全件を書き出し、取込は追加のみとする。同名や不正項目が1件でもあれば全件を拒否する。内部設定4ファイルへの直接入出力を禁止し、取込成功時は対象一覧の選択とUndo履歴を維持しつつ、古いプレビューを破棄して再プレビューを案内する。
- **旧版との設定共用は対象外。** 2グループの項目を含む `patterns.json` を v0.3.0 が読み込むと、入力パターン一覧全体が既定値で上書きされる。更新前に設定をバックアップし、旧版に戻す場合は旧版の初回起動前に、年月項目を含まない更新前の `patterns.json` を復元する手順を [取扱説明書](../取扱説明書.md) に明記し、v0.4.0 リリースノート作成時はその記載を参照する。

## タスク

### 1. Services：種別判定・変換・テンプレート管理

- [ ] [validation.py](../src/rename_date/services/validation.py) に `PatternKind.MONTH` と `validate_month_output_template` を追加する。キャプチャグループ数の対応表を検証と判定で共用し、グループ数エラー文言を `"pattern must contain 2 (month), 3 (single), or 4 to 6 (range) capture groups"` に更新する。年月テンプレート検証は `{Y}`・`{M}` の存在確認後、単一パス置換（`re.sub(r"\{(?:Y|M)\}", "", template)`）の残余に `{` / `}` が含まれないことと Windows 禁止文字がないことを確認する。
- [ ] [date_span.py](../src/rename_date/services/date_span.py) に `YearMonth(year: int, month: int)` と `parse_month_match` / `render_month` を追加する。整数変換は既存の `_to_int` を再利用し、`date(year, month, 1)` で年・月の有効範囲を検証して日は保持・描画しない。既存の `parse_match` は `PatternKind.RANGE` を明示判定し、`PatternKind.MONTH` を渡された場合は `ValueError` を送出する。
- [ ] [ScannerService](../src/rename_date/services/scanner_service.py) に既定値付きのキーワード専用引数 `month_output_template: str = config.DEFAULT_MONTH_OUTPUT_TEMPLATE` を追加する。既存の位置引数を維持し、走査前に年月用テンプレートを検証する。種類の優先順位（期間 → 単日 → 年月）で安定ソートし、年月用の解析・描画と、`re.fullmatch(r"\.[0-9]{1,2}", source.suffix)` による ASCII 半角1〜2桁数字拡張子の除外（`PatternKind.MONTH` のみスキップ）を組み込む。
- [ ] [config.py](../src/rename_date/config.py) に `DEFAULT_MONTH_TEMPLATE_NAME = "既定 YYYY-MM"`、`DEFAULT_MONTH_OUTPUT_TEMPLATE = "{Y}-{M}"`、`MONTH_OUTPUT_TEMPLATES_FILE_NAME = "month_output_templates.json"` を追加し、`PRESET_FILE_NAMES` に含める。[OutputTemplateService](../src/rename_date/services/output_template_service.py) の既存サブクラス方式で `MonthOutputTemplateService` を追加し、内部保存・厳密な外部JSON検証・原子的な書き込みを再利用する。

### 2. Views・Controller：設定とプレビュー

- [ ] [起動処理](../src/rename_date/__main__.py) で `MonthOutputTemplateService` を生成し、[AppController](../src/rename_date/controllers/app_controller.py) に渡す。[ConfigFrame](../src/rename_date/views/config_frame.py) の出力テンプレート欄は「単日」「期間」「年月」それぞれを2段構成（上段: 左に種別ラベル・右寄せで `New`/`Edit`/`Delete`、下段: 全幅の `Combobox`）へ見直し、`700x450` でもプレビュー領域を圧迫せずに年月用の選択・編集操作を追加する。[出力テンプレート編集ダイアログ](../src/rename_date/views/output_template_dialog.py) に年月用検証とタイトル・説明文（`年月用テンプレートプリセット`、利用可能な `{Y}{M}` と他プレースホルダー・波括弧の禁止）を渡す。`set_patterns` の種別表示を暗黙の `else:` ではなく明示分岐にして `[年月]` を表示し、[パターン編集ダイアログ](../src/rename_date/views/pattern_dialog.py) のグループ数の案内を更新する。
- [ ] [MainWindow](../src/rename_date/views/main_window.py) のプリセットメニューと保存・取込ダイアログに年月用を追加し、Controllerの種類別処理につなぐ。`_on_preset_import` の暗黙の `else:` を明示分岐（未知種別は `ValueError`）に改め、Phase 6 の選択復元、処理中の取込拒否、上書き確認、エラー通知、プレビュー無効化を再利用する。
- [ ] `_on_preview_request` で年月パターン選択時のみ年月テンプレート選択を必須とし、年月パターン判定中の `InvalidPatternError` は捕捉して従来の走査エラー経路へ流す。年月パターン未選択かつ年月テンプレート未選択時は `config.DEFAULT_MONTH_OUTPUT_TEMPLATE` を補って走査ワーカーへ渡し、再走査用の `_last_scan_params` にも保持する。実行・Undo 後のプレビューは、設定欄の現在値ではなく元の走査条件を使う。ワーカースレッド、キャンセル、UI更新の方式は変更しない。

### 3. テスト

- [ ] [test_validation.py](../tests/test_validation.py) と [test_date_span.py](../tests/test_date_span.py) で、2グループの認識、0・1・7グループの拒否（既存テストの2グループ拒否ケースとエラー文言アサートを更新）、`YearMonth` の値域・ゼロ埋め、`parse_match` の `PatternKind.MONTH` 拒否、年月テンプレートの必須不足・未知プレースホルダー（`{D}`, `{Y2}`, `{foo}`, `{}`）・不正な波括弧（`{Y}-{M}{`, `{{Y}}-{M}`, `{Y}-{M}-{Y{M}}`）・禁止文字の拒否および複数回利用（`{Y}_{Y}-{M}`）の受理を確認する。単日・期間の既存結果も維持する。
- [ ] [test_scanner.py](../tests/test_scanner.py) で、既存テストの2グループ拒否ケースを更新した上で、次の例と、1ファイル内の複数マッチ・変更なし・名前衝突を `tmp_path` で検証する。期間・単日・年月の混在は、先行ルールの出力に後続ルールがマッチする設定で適用順を確認し、同種内の順序も検証する。

  | 入力例（標準の年月パターンのみ選択） | 期待結果 |
  |---|---|
  | `売上_2026.7.pdf` | `売上_2026-07.pdf` |
  | `2026.13.pdf` | `INVALID_DATE`、実行対象外 |
  | `2026.11.26.pdf` / `2026.11-26.pdf` | 年月の部分変換なし |
  | `2026.11` / `2026.11.26` / `売上_2026.7.1` | 変更なし、プレビュー対象外 |
  | `2026.13.26` | 年月ルール未適用のため `INVALID_DATE` にせず対象外 |
  | `売上_2026.7.001` / `売上_2026.7.２６` | 3桁数字・全角数字の拡張子は除外対象外のため変換される |
  | `(2024.1.5).01`（単日＋年月を併用） | 単日ルールは影響を受けず `20240105.01` になる |

- [ ] [test_pattern_service.py](../tests/test_pattern_service.py) と [test_output_template_service.py](../tests/test_output_template_service.py) で、既存テストの2グループ拒否ケースを更新した上で、2グループを含む入力パターンの保存・取込、年月テンプレートの別保存・JSON往復、異なる種別や同名の拒否、失敗時のファイル非変更、既存種別からも年月用の内部ファイルに直接入出力できないことを確認する。
- [ ] [test_app_controller.py](../tests/test_app_controller.py) で、年月テンプレート未選択時の警告、年月パターン未選択かつ年月テンプレート未選択時の既定値フォールバック走査、不正パターン混在時の従来の走査エラー通知、実行・Undo後の走査条件の維持、年月用JSON取込成功時だけ選択を維持してプレビューを破棄することを確認する。
- [ ] 対象テストと変更箇所の静的解析を実行した後、`uv run pytest --cov=src/rename_date --cov-report=term-missing` で回帰とServices層の集計カバレッジ85%以上を確認する。

### 4. ドキュメント・バージョン更新・配布検証

- [ ] [開発計画書](./rename-date開発計画書.md) と [プロジェクトガイドライン](../.github/copilot-instructions.md) のグループ数（既存ガイドラインの「2・7以外」誤記も「2〜6以外」へ修正）・適用順・保存先を更新する。[取扱説明書](../取扱説明書.md) と [パターン設定ガイド](../パターン設定ガイド.md) に入力例・出力例・拡張子の制約（`.1`〜`.99` の半角1〜2桁数字だけの拡張子には年月ルールが適用されない点を含む）・年月用JSON入出力を追記する。旧版での上書きリスクと復元手順は [取扱説明書](../取扱説明書.md) に明記する（v0.4.0 リリースノート作成時に参照）。
- [ ] `uv version 0.4.0` で [pyproject.toml](../pyproject.toml) と [uv.lock](../uv.lock) を更新し、[setup.iss](../installer/setup.iss) の単独ビルド時の既定値も `0.4.0` に揃える。`uv lock --check` と `uv run --locked python -c "from importlib.metadata import version; assert version('rename-date') == '0.4.0'"` で確認する。既存の `AppId` は維持する。
- [ ] Windowsの検証環境で、最小ウィンドウサイズ `700x450` でも年月用の操作とプレビューが可能なことを確認する。年月パターンを登録し、単日・期間・年月の混在プレビューから実行・Undoまで行う。年月テンプレートの保存・取込と、再起動後の設定保持も確認する。
- [ ] Inno Setup が使える検証用作業コピーで `pwsh -File .\scripts\build-release.ps1`（PowerShell 7 が無い環境では `powershell -File .\scripts\build-release.ps1`）を実行し、`installer\Output\rename-date-0.4.0-setup.exe` の生成を確認する。検証用プロファイルで v0.3.0 から上書きインストールし、既存の内部設定3ファイルが年月項目を登録する前には変更されず、v0.4.0 で新機能が使えることを確認する。

## スコープ外

- `2026.11` 単独のように年月が拡張子と区別できない名前の変換や、拡張子の判定ルールの変更。
- 年月の期間（`YYYY.MM〜YYYY.MM`）、年だけの変換、単日・期間テンプレートの仕様変更。
- 新旧バージョン間の設定共用、設定の自動移行、Gitタグ作成、GitHub Releaseへの公開。
