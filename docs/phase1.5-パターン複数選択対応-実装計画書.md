# Phase 1.5: パターン複数選択・出力テンプレート分離への改訂 実装計画書

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) 第6章 Phase 1.5、および要件変更に伴う第1.2〜1.3章・第3章・第4.1章-1・第4.2.A章・第4.2.E章・第5章・第11章の改訂。[phase1-コアロジック実装-実装計画書.md](./phase1-コアロジック実装-実装計画書.md) で完成済みの `PatternEntry` / `PatternService` / `ScannerService` を、要件変更（**置換対象パターンは複数選択可能、出力テンプレートは単一選択のみ**）に合わせて改訂する。

## 目的

Phase 1 完成時点では `PatternEntry`（`name` + `pattern` + `output_template`）が1組のプリセットとして扱われ、`ScannerService.scan()` は単一パターン・単一テンプレートを受け取る設計だった。要件変更により「置換対象となる年月日表現（パターン）は複数選択可能、置換後表現（出力テンプレート）は単一」となったため、パターンと出力テンプレートの結合を解消し、Phase 2（GUI実装）に着手する前に Models / Services 層を改訂する。本フェーズは Phase 2 の前提条件であり、Phase 2 のタスクに着手する前に完了させること。

## 要件

- `PatternEntry` は `name` / `pattern` のみを持つ（`output_template` を削除）。複数件を選択して使用できる。
- 新規 `OutputTemplateEntry`（`name` / `template`）を追加する。常に単一選択で使用する。
- `PatternService` は `patterns.json` にパターンプリセット（`name` + `pattern`）のみを永続化する。検証は `services.validation.compile_pattern` のみを用いる。
- 新規 `OutputTemplateService` は `output_templates.json` に出力テンプレートプリセット（`name` + `template`）を永続化する。検証は `services.validation.validate_output_template` のみを用いる。両サービスとも、既存 `PatternService` と同様の契約（最低1件維持・同名一意・一時ファイル+`os.replace()`によるアトミック保存・破損時は既定1件で再生成）を満たすこと。
- `ScannerService.scan()` のシグネチャを `scan(targets, patterns: list[str], output_template: str, cancel_event=None) -> list[RenameItem]` に変更する。`patterns` が空リストの場合は `InvalidPatternError` を送出する。
- 複数パターンは**リスト順に逐次適用**する（パイプライン方式）。各パターンは直前のパターンの置換結果（working stem）に対して適用する。
- あるパターンがマッチした場合、そのマッチすべてについて `datetime.date` で日付妥当性を検証し、いずれか1つでも不正なら、そのファイル全体を `INVALID_DATE` として記録し、以降のパターン適用を打ち切る。
- どのパターンも一度もマッチしなかったファイルは、従来どおり変更対象外として結果から除外する。
- 連続空白の畳み込み・トリムは、全パターン適用後の最終結果に対して1回のみ行う（各パターン適用の都度は行わない）。
- 衝突回避（`_1`, `_2`…連番付与）・`RESOLVED_CONFLICT` の扱いなど、パターン数に関係しない既存仕様は変更しない。
- `config.py` に出力テンプレートの既定値名定数（`DEFAULT_TEMPLATE_NAME`）を追加する。`DEFAULT_PATTERN_REGEX` / `DEFAULT_OUTPUT_TEMPLATE` は既存のものを流用する。
- 既存テスト（`test_scanner.py` / `test_pattern_service.py` / `conftest.py`）を新シグネチャ・新スキーマに合わせて改修し、新規 `test_output_template_service.py` を作成する。Services 層カバレッジ目標 85% 以上を維持すること。

## タスク

### 1. Models 層

- [ ] `models/pattern_entry.py`: `PatternEntry` から `output_template` フィールドを削除し、`to_dict()` / `from_dict()` を `name`/`pattern` のみに更新する。
- [ ] `models/output_template_entry.py`（新規作成）: `OutputTemplateEntry` dataclass（`name`, `template`）と `to_dict()` / `from_dict(cls, data: dict)` を実装する。

### 2. `config.py`

- [ ] `DEFAULT_TEMPLATE_NAME` 定数を追加する（例: `"既定 (YYYYMMDD)"`）。既存の `DEFAULT_PATTERN_NAME` / `DEFAULT_PATTERN_REGEX` / `DEFAULT_OUTPUT_TEMPLATE` は流用する。

### 3. `PatternService` の改訂

- [ ] `services/pattern_service.py`: `_default_entry()` から `output_template` を除去する。
- [ ] `_entries_from_json` / `_validate_entries` のスキーマチェックを `{"name", "pattern"}` に変更する。
- [ ] `validate_output_template` の呼び出しを削除し、`compile_pattern` のみで検証する。

### 4. `OutputTemplateService`（新規）

- [ ] `services/output_template_service.py`（新規作成）: `PatternService` と同様の構造（`__init__(base_dir: Path | None = None)`, `load() -> list[OutputTemplateEntry]`, `save(entries) -> None`, `upsert(entry) -> list[OutputTemplateEntry]`, `delete(name) -> list[OutputTemplateEntry]`）で `OutputTemplateEntry` を `output_templates.json` に永続化する。
- [ ] 検証は `services.validation.validate_output_template` のみを用いる。最低1件維持・同名一意・アトミック保存（一時ファイル+`os.replace()`）・破損時フォールバックの契約は `PatternService` と同じくする。
- [ ] 既定エントリは `config.DEFAULT_TEMPLATE_NAME` / `config.DEFAULT_OUTPUT_TEMPLATE` から生成する。

### 5. `ScannerService` の改訂

- [ ] `services/scanner_service.py`: `scan(targets, patterns: list[str], output_template: str, cancel_event=None)` にシグネチャ変更する。`patterns` が空なら `InvalidPatternError` を送出する。
- [ ] 各パターンを事前にすべて `compile_pattern` で検証し、`output_template` を `validate_output_template` で検証する。
- [ ] ファイルごとに working stem を保持し、`patterns` をリスト順に逐次適用する。各パターンの `finditer` 結果すべてについて日付妥当性を検証し、不正なら `INVALID_DATE` としてそのファイルの処理を打ち切る。妥当なら共通の `output_template` で `re.sub` して working stem を更新し、次のパターンへ進む。
- [ ] どのパターンにも一度もマッチしなかったファイルは結果から除外する。
- [ ] 全パターン適用後の working stem に対して、連続空白畳み込み・トリムを1回行い、元の stem と同一なら除外する。
- [ ] 衝突回避ロジック（親ディレクトリごとの予約済み名・`_1,_2...`連番・`RESOLVED_CONFLICT`）は変更しない。

### 6. テスト改修

- [ ] `tests/conftest.py`: `default_pattern` fixture を `PatternEntry(name, pattern)`（`output_template` なし）に変更し、`default_output_template` fixture（`OutputTemplateEntry`）を追加する。
- [ ] `tests/test_scanner.py`: 既存テストの `scan()` 呼び出しを `patterns: list[str]` + `output_template: str` に更新する。以下のケースを追加する。
  - 複数パターンの逐次適用（例: 括弧型パターンとハイフン型パターンを両方選択し、1ファイル内の異なる箇所をそれぞれ変換する）
  - どのパターンにもマッチしないファイルの除外
  - パイプライン2番目以降のパターンで不正日付を検出した場合の `INVALID_DATE` 判定
  - 空の `patterns` リストを渡した場合に `InvalidPatternError` を送出すること
- [ ] `tests/test_pattern_service.py`: `PatternEntry` から `output_template` を除いたアサーションに更新する。
- [ ] `tests/test_output_template_service.py`（新規作成）: JSON読込/保存、初回起動時の既定プリセット生成、不正テンプレート（プレースホルダ欠落・禁止文字）の保存拒否、壊れたJSONからのフォールバック、最後の1件削除拒否を検証する。

### 7. 動作確認

- [ ] `uv run pytest --cov=src/rename_date --cov-report=term-missing` を実行し、全テストが green であり Services 層カバレッジ85%以上であることを確認する。
- [ ] 手動で `ScannerService.scan()` を複数パターン指定で実行し、逐次適用（パイプライン）の結果が意図どおりであることを確認する。
- [ ] Pylance等の静的検査でエラーが出ていないことを確認する。

## スコープ外（本フェーズで実装しないこと）

- View / Controller の実装（Phase 2, Phase 3）
- 複数パターンのマッチ箇所を1ファイル内でマージして同時処理する方式（不採用。リスト順の逐次適用のみをサポートする）
- パターンの適用順序をユーザーのクリック順など表示順以外の基準で決定する機能
- `patterns.json` の旧スキーマ（`output_template` を含む形式）からの自動マイグレーション（未リリースのため対応しない）
- Redo、フォルダ名リネーム、Undo履歴の永続化など、開発計画書12章記載のスコープ外事項
