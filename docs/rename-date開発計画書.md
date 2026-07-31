# **ファイル名一括変換 GUI アプリ (Rename Date) 開発計画書**

## **1\. アプリケーション概要**

### **1.1 目的**

指定されたフォルダ配下を再帰的に走査し、正規表現パターン（例: (YYYY.M.D) 形式）にマッチするファイル名を ISO8601 簡易表現（YYYYMMDD）へ一括変更する GUI アプリケーションを開発する。

### **1.2 主な特徴**

- **再帰的検索**: サブフォルダ内のファイルも対象（隠しフォルダ・VCS 管理フォルダ等は除外）。
- **安心の事前プレビュー**: 変更を実行する前に一覧で差分と処理状態を確認可能。
- **安全設計**: 変更後ファイル名の衝突自動回避（`_1` 連番）、不正日付の実行対象外化、ログ出力。
- **Undo 機能**: 誤って実行した直前のリネーム操作を一括で取り消す（元に戻す）。
- **可変正規表現**: GUI 上で正規表現パターンを動的変更可能（年・月・日の 3 キャプチャグループ契約）。
- **UI 応答性**: 走査・実行・Undo はワーカースレッドで行い、進捗表示とキャンセルに対応。
- **多重起動抑止**: 同時に 2 つ以上のインスタンスが起動しないよう制御。
- **インストーラ配布**: PyInstaller で実行ファイル化し、Inno Setup でインストーラを生成。

### **1.3 主要な決定事項サマリ**

| 項目       | 決定内容                                                                                     |
| ---------- | -------------------------------------------------------------------------------------------- |
| 置換の契約 | 正規表現は年・月・日の 3 キャプチャグループ固定。ゼロ埋めして `YYYYMMDD` に連結する          |
| 括弧の扱い | 除去する（`Report (2024.1.5) final.pdf` → `Report 20240105 final.pdf`）                      |
| 複数マッチ | 1 ファイル名中のすべてのマッチを置換する                                                     |
| 拡張子     | 置換対象外。`Path.stem` のみを対象とする                                                     |
| 不正な日付 | `datetime.date` で検証し、`(2024.13.45)` 等はプレビューに「無効」表示のうえ実行対象外        |
| 名前の衝突 | 自動回避。`_1`, `_2` … の連番サフィックスを付与する                                          |
| 走査対象   | ファイルのみ（フォルダ名は変更しない）                                                       |
| 除外       | 隠しファイル・隠しフォルダ、既定の除外ディレクトリ、シンボリックリンクは辿らない             |
| プレビュー | 表示専用。個別チェックによる取捨選択は行わず全件一括実行                                     |
| Undo       | メモリ上の複数段 LIFO スタック。アプリ終了で履歴は破棄                                       |
| Python     | 3.12 以上                                                                                    |
| GUI        | 標準ライブラリの tkinter / ttk のみ（実行時の追加依存なし）                                  |
| ログ       | `%APPDATA%\rename-date\logs\rename_log.txt`（UTF-8 / サイズベースローテーション 最大 6 MiB） |
| 多重起動   | 抑止する（既存ウィンドウを前面化して新しいプロセスは終了）                                   |
| 配布       | PyInstaller（onedir・ウィンドウアプリ）→ Inno Setup インストーラ                             |

## **2\. 開発環境 & パッケージ管理 (uv)**

本プロジェクトでは Python のパッケージ・環境管理ツールとして **uv** を利用します。

### **2.1 前提条件**

| 項目             | 内容                                                 |
| ---------------- | ---------------------------------------------------- |
| Python           | 3.12 以上                                            |
| パッケージ管理   | uv                                                   |
| GUI ツールキット | 標準ライブラリ tkinter / ttk（実行時の追加依存なし） |
| 開発用依存       | pytest, pytest-cov, pyinstaller                      |
| 対象 OS          | Windows 10 / 11                                      |
| レイアウト       | src レイアウト（`src/rename_date/`）                 |

### **2.2 環境構築手順**

```powershell
# 既存リポジトリ直下でプロジェクトを初期化（src レイアウト）
uv init --app --package .

# 開発用依存の追加
uv add --dev pytest pytest-cov pyinstaller

# アプリの起動
uv run main.py

# テストの実行
uv run pytest --cov=src/rename_date
```

初期化後、`pyproject.toml` に以下を設定します。

- `requires-python = ">=3.12"`
- `[tool.pytest.ini_options]` の `pythonpath = ["src"]`

## **3\. ソフトウェアアーキテクチャ & モジュール構成**

責務の分離（Separation of Concerns）を徹底し、将来的なロジック追加やテスト容易性を担保するレイヤード構成とします。

### **3.1 アーキテクチャ構成**

```text
+-----------------------------------------------------------+
| Entry Point (main.py)                                     |
| - SingleInstanceGuard : 多重起動抑止                      |
+-----------------------------------------------------------+
                     |
                     v
+-----------------------------------------------------------+
| UI Layer (Views)                                          |
| - MainWindow, ConfigFrame, PreviewFrame, ActionFrame      |
+-----------------------------------------------------------+
                     | (ユーザー操作 / 描画)
                     v
+-----------------------------------------------------------+
| Controller / Presenter                                    |
| - AppController : UIイベント受付、状態管理、スレッド制御  |
+-----------------------------------------------------------+
                     | (ビジネスロジック呼び出し)
                     v
+-----------------------------------------------------------+
| Services Layer                                            |
| - ScannerService : 走査 & パターン判定 & 衝突解決         |
| - RenameService  : リネーム実行                           |
| - UndoService    : 実行履歴管理 & 元に戻す処理            |
| - LogService     : ログ出力（サイズベースローテーション） |
+-----------------------------------------------------------+
                     | (データ共有)
                     v
+-----------------------------------------------------------+
| Models Layer                                              |
| - RenameItem       : 個別の変更情報モデル + 処理状態      |
| - ExecutionHistory : 実行履歴データモデル                 |
+-----------------------------------------------------------+
```

**依存方向のルール**: 上位レイヤーは下位レイヤーにのみ依存します。Services 層は tkinter を import せず、UI から独立してテスト可能な状態を保ちます。

### **3.2 プロジェクト階層構造**

```text
rename-date/
├── pyproject.toml                    # uv / プロジェクト設定ファイル
├── uv.lock                           # ロックファイル
├── README.md
├── main.py                           # アプリ起動エントリポイント
├── docs/
│   └── rename-date開発計画書.md
├── src/
│   └── rename_date/
│       ├── __init__.py               # __version__
│       ├── __main__.py               # main(): 多重起動チェック → ウィンドウ起動
│       ├── config.py                 # 既定パターン / 除外リスト / ログ設定
│       ├── single_instance.py        # 多重起動抑止
│       │
│       ├── models/                   # データ構造定義
│       │   ├── __init__.py
│       │   ├── rename_item.py        # RenameItem, ItemStatus
│       │   └── execution_history.py  # ExecutionHistory
│       │
│       ├── services/                 # コアビジネスロジック
│       │   ├── __init__.py
│       │   ├── scanner_service.py    # 走査・正規表現マッチング・衝突解決
│       │   ├── rename_service.py     # リネーム実行ロジック
│       │   ├── undo_service.py       # Undo（逆変換）ロジック・履歴管理
│       │   └── log_service.py        # ログ出力・ローテーション
│       │
│       ├── controllers/              # アプリケーション制御
│       │   ├── __init__.py
│       │   └── app_controller.py     # UIとServicesの橋渡し・スレッド制御
│       │
│       └── views/                    # Tkinter GUI コンポーネント
│           ├── __init__.py
│           ├── main_window.py        # メインウィンドウ
│           ├── config_frame.py       # フォルダ・正規表現入力部
│           ├── preview_frame.py      # Treeview表示部
│           └── action_frame.py       # 実行/Undo/カウント/進捗表示部
│
├── tests/                            # ユニットテスト (pytest)
│   ├── conftest.py                   # ダミーフォルダ構造の fixture
│   ├── test_scanner.py
│   ├── test_renamer.py
│   ├── test_undo.py
│   └── test_log.py
│
└── installer/                        # 配布用
    ├── rename-date.spec              # PyInstaller 設定
    └── setup.iss                     # Inno Setup スクリプト
```

## **4\. 機能要件詳細**

### **4.1 画面機能 (Views)**

1. **設定エリア (ConfigFrame)**
   - 対象フォルダ選択（`filedialog.askdirectory`）
   - 正規表現パターン入力（デフォルト: `\((\d{4})\.(\d{1,2})\.(\d{1,2})\)`）
   - 「プレビュー更新」ボタン
2. **プレビューエリア (PreviewFrame)**
   - `ttk.Treeview` による一覧表示。列は **状態 / 変更前ファイル名 / 変更後ファイル名 / 相対パス**
   - 変更対象外ファイル（パターンに一致しない、または置換結果が元と同一）は非表示
   - 状態に応じた行の書式: 不正な日付はグレー表示、連番付与による衝突回避は強調表示
   - 表示専用。個別のチェックによる取捨選択は行わない
3. **操作エリア (ActionFrame)**
   - 対象件数表示（実行対象 / 無効の内訳を併記）
   - 「一括変換を実行」ボタン
   - 「直前の実行を取り消す (Undo)」ボタン（履歴がある場合のみ有効化）
   - ログ保存設定チェックボックス
   - 進捗バーとステータスラベル、処理中の「キャンセル」ボタン

### **4.2 サービスロジック要件 (Services)**

#### **A. 走査・置換ロジック (ScannerService)**

**パターンの検証**

- `re.compile()` に失敗した場合、およびキャプチャグループ数が 3 でない場合は `InvalidPatternError` を送出し、走査を行わずに GUI 側でエラーダイアログを表示する。
- 3 つのキャプチャグループはそれぞれ **年・月・日** に対応する。

**走査**

- `os.walk(root, topdown=True, followlinks=False)` を使用し、`dirnames` をその場で書き換えて除外フォルダの探索自体を打ち切る。
- 除外対象:
  - 隠しフォルダ・隠しファイル（名前が `.` で始まる、または Windows の `FILE_ATTRIBUTE_HIDDEN` が立っているもの）
  - 既定の除外ディレクトリ: `.git`, `.svn`, `.hg`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`
  - シンボリックリンク / ジャンクション（辿らない）
- 走査対象は**ファイルのみ**。フォルダ名は変更しない。
- 結果の再現性のため、ファイル名はソートして決定的な順序で処理する。
- `threading.Event` によるキャンセル要求を走査ループ内で定期的に確認する。

**置換**

- 置換対象は `Path.stem` のみ（拡張子は保持する）。
- ファイル名中の**すべてのマッチ**を置換する（`re.sub`）。
- 各マッチについて `datetime.date(年, 月, 日)` で妥当性を検証する。`ValueError` となった場合、そのファイルは `INVALID_DATE` として記録し実行対象から除外する。
- 妥当な場合は月・日をゼロ埋めして `YYYYMMDD` に連結する。括弧は結果に含めない。
- 置換後に連続空白を 1 つに畳み、前後の空白を除去する（`re.sub(r"\s{2,}", " ", stem).strip()`）。
- 置換後の stem が元と同一のファイルは、変更対象外として結果リストに含めない。

**衝突回避**

- 親ディレクトリごとに「予約済み名」の集合を保持する。初期値はそのディレクトリの実在エントリ（リネーム元自身は除く）とし、確定した変更後名を順次追加する。
- 候補名が予約済みの場合、`_1`, `_2` … と連番サフィックスを付与して空きを探す。この仕組みにより、**既存ファイルとの衝突**と**同一バッチ内での衝突**を同一ロジックで解決する。
- 連番を付与した項目は `RESOLVED_CONFLICT` として記録し、プレビューで判別できるようにする。
- 大文字小文字を区別しないファイルシステムを考慮し、予約済み名の比較は `casefold()` で行う。

#### **B. リネーム実行 (RenameService)**

- `INVALID_DATE` の項目はスキップする。
- リネームには `Path.rename()` を使用する。`os.replace()` は既存ファイルを黙って上書きするため**使用しない**。
- 例外処理:
  - `FileExistsError`（走査後に第三者がファイルを作成した場合など）→ `SKIPPED` として記録し継続
  - `PermissionError` / その他の `OSError`（他アプリで開かれている、パス長超過など）→ `ERROR` として記録し継続
- 成功した項目のみを `ExecutionHistory` に格納し、`UndoService` のスタックに積む。

#### **C. Undo ロジック (UndoService)**

- **履歴スタック構造**: 実行された一括リネーム操作（`ExecutionHistory`）をメモリ上のスタック（LIFO）構造で管理する。アプリ終了時に履歴は破棄される（永続化しない）。
- **取り消し処理**:
  1. 履歴スタックから最新のセッションを取得。
  2. 競合を防ぐため、**実行時とは逆順**（末尾から）にファイル名を元の original_path へ復元。
  3. 復元完了後、履歴スタックから該当セッションを削除。
  4. Undo の実行自体もログファイルに記録。
- **欠損・競合時の扱い**: 復元元のファイルが存在しない、または復元先に既にファイルが存在する場合はその項目を `SKIPPED` とし、他のファイルの復元を継続する。

#### **D. ログ出力 (LogService)**

第 8 章「ログ設計」を参照。

## **5\. データモデル設計 (Models)**

### **RenameItem**

```python
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ItemStatus(StrEnum):
    PENDING = "PENDING"                      # 実行待ち
    INVALID_DATE = "INVALID_DATE"            # 日付として不正（実行対象外）
    RESOLVED_CONFLICT = "RESOLVED_CONFLICT"  # 連番付与で衝突を回避（実行対象）
    SUCCESS = "SUCCESS"                      # 成功
    SKIPPED = "SKIPPED"                      # スキップ
    ERROR = "ERROR"                          # エラー


@dataclass
class RenameItem:
    original_path: Path
    target_path: Path
    status: ItemStatus = ItemStatus.PENDING
    message: str = ""

    @property
    def original_name(self) -> str:
        return self.original_path.name

    @property
    def target_name(self) -> str:
        return self.target_path.name

    @property
    def parent_dir(self) -> Path:
        return self.original_path.parent

    @property
    def is_executable(self) -> bool:
        return self.status in (ItemStatus.PENDING, ItemStatus.RESOLVED_CONFLICT)
```

### **ExecutionHistory**

```python
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from rename_date.models.rename_item import RenameItem


@dataclass
class ExecutionHistory:
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    items: list[RenameItem] = field(default_factory=list)
```

`session_id` は 1 回の一括実行を識別する ID で、ログの全行に付与する。ログローテーションによって 1 セッションの記録が複数ファイルに分割された場合でも、`session_id` を手掛かりに再構成できる。

## **6\. 開発ロードマップ (フェーズ別)**

### **Phase 0: プロジェクト初期化**

1. `uv init --app --package .` によるプロジェクト初期化（src レイアウト）
2. `pyproject.toml` の調整（`requires-python = ">=3.12"`、`[tool.pytest.ini_options]` の `pythonpath = ["src"]`）
3. `uv add --dev pytest pytest-cov pyinstaller`
4. パッケージ骨組みと `.gitignore`（`dist/`, `build/`, `.venv/`, `__pycache__/`, `installer/Output/`）の作成

### **Phase 1: コアロジック実装 (Models / Services)**

1. `RenameItem` / `ItemStatus` / `ExecutionHistory` モデルの実装
2. `config.py`（既定パターン、除外リスト、ログ設定）の実装
3. ScannerService (走査・置換・日付検証・衝突回避) の作成 & pytest でのテスト
4. RenameService (ファイル変更) 及び UndoService (逆変換) の作成 & テスト
5. LogService（ローテーション付きログ出力）の作成 & テスト

### **Phase 2: GUI コンポーネントのモジュール化**

1. 各 View コンポーネント (ConfigFrame, PreviewFrame, ActionFrame) の作成
2. MainWindow へのコンポーネント配置とレイアウト調整（プレビュー領域のみ伸縮させる）
3. ダミーデータを流し込んだ表示確認

### **Phase 3: Controller による統合と動作検証**

1. AppController による Event Handling の接続
2. ワーカースレッド化（走査 / 実行 / Undo）と進捗表示・キャンセル処理の実装
3. Undo ボタンの状態管理（履歴がある場合のみ活性化）
4. 多重起動抑止の実装
5. 統合テスト（ダミーフォルダ構造に対する実行と Undo 検証）

### **Phase 4: 配布パッケージング**

1. PyInstaller 設定 (`installer/rename-date.spec`) の作成と実行ファイルの動作確認
2. Inno Setup スクリプト (`installer/setup.iss`) の作成
3. インストール → 起動 → アンインストールの一連の検証
4. README へのビルド手順の記載

## **7\. 例外処理・安全対策方針**

1. **同名ファイルの競合**: 変更後の名前が既存ファイルまたは同一バッチ内の他の変更後名と衝突する場合、`_1`, `_2` … の連番サフィックスを付与して自動回避する（プレビュー段階で解決済みの名前を表示する）。
2. **走査後に発生した競合**: プレビュー後・実行前に第三者がファイルを作成した場合、`Path.rename()` が `FileExistsError` を送出するため SKIP として記録し処理を継続する。既存ファイルの上書きは行わない。
3. **不正な日付**: `(2024.13.45)` のようにパターンには一致するが日付として成立しない場合、プレビューに「無効」として表示し実行対象から除外する。
4. **権限エラー (PermissionError)**: ファイルが他アプリで開かれている等の理由でリネーム失敗時、エラーログを記録して処理を継続。
5. **パス長の超過**: 連番付与等により Windows のパス長上限を超えた場合、`OSError` を捕捉して ERROR として記録し継続する。
6. **不正な正規表現**: コンパイル不能、またはキャプチャグループ数が 3 でない場合、走査を実行せずエラーダイアログで通知する。
7. **Undo時の欠損対策**: Undo 実行時、リネーム後のファイルが手動で削除・移動されていた場合、または復元先に既にファイルが存在する場合はスキップし、他のファイルの復元を継続。
8. **UI のフリーズ回避**: 走査・実行・Undo はワーカースレッドで行い、UI 更新は `widget.after(0, ...)` を経由してメインスレッドで実施する。処理中は操作ボタンを無効化する。
9. **ReDoS への配慮**: ユーザーが入力した正規表現によっては走査が終わらない可能性があるため、キャンセルボタンを常に提供する。
10. **ログ出力の失敗**: ログ出力に失敗してもリネーム処理本体は中断しない（`logging` はハンドラ内の例外を呼び出し元に送出しない）。GUI 上はステータス表示に留める。

## **8\. ログ設計**

### **8.1 出力先**

| 項目               | 内容                                                                             |
| ------------------ | -------------------------------------------------------------------------------- |
| 出力先ディレクトリ | `%APPDATA%\rename-date\logs\`                                                    |
| ファイル名         | `rename_log.txt`                                                                 |
| エンコーディング   | UTF-8（既定の cp932 では日本語ファイル名で `UnicodeEncodeError` となるため必須） |
| 出力タイミング     | 一括実行 / Undo の完了時に追記（ログ保存チェックボックスが ON の場合）           |

### **8.2 ログ書式**

1 行 1 項目のタブ区切り (TSV) とする。

```text
<ISO8601 日時>\t<session_id>\t<action>\t<status>\t<変更前パス>\t<変更後パス>\t<メッセージ>
```

- `action`: `RENAME` または `UNDO`
- `status`: `SUCCESS` / `SKIPPED` / `ERROR` / `INVALID_DATE` / `RESOLVED_CONFLICT`
- ファイル名に含まれるタブ・改行はエスケープしてから書き込み、ログの行構造が壊れることを防ぐ。

### **8.3 ローテーション方針**

標準ライブラリの `logging.handlers.RotatingFileHandler` による**サイズベース**のローテーションを採用する。断続的にしか起動しないデスクトップアプリでは、時刻ベース (`TimedRotatingFileHandler`) よりも「ディスク使用量に上限を設ける」というサイズベースの目的が要件に合致するため。

| 設定          | 値      | 意図                                                           |
| ------------- | ------- | -------------------------------------------------------------- |
| `maxBytes`    | 1 MiB   | 1 行あたり 150〜300 バイト程度のため、およそ 4,000〜7,000 件分 |
| `backupCount` | 5       | 世代を含めた最大サイズを **6 MiB** に固定                      |
| `encoding`    | `utf-8` | 日本語ファイル名への対応                                       |
| `delay`       | `True`  | ログ保存を使用しない場合に空ファイルを作らない                 |

- 世代ファイル名は `rename_log.1.txt` … `rename_log.5.txt` とする（`handler.namer` を差し替え、拡張子を末尾に保つことで関連付けから開けるようにする）。
- ロールオーバーはレコード単位で行われるため、1 行が複数ファイルに分断されることはない。ただし 1 回の一括実行が 2 ファイルにまたがる可能性はあるため、全行に `session_id` を付与して再構成可能にする。
- 名前付きロガー (`rename_date.audit`) を使用し、`propagate = False` としてルートロガーへの二重出力を防ぐ。ハンドラの二重登録も防止する。
- アプリ終了時に `logging.shutdown()` を呼び、ファイルハンドルを確実に解放する。
- アンインストール時にもログディレクトリは削除しない。

## **9\. 多重起動抑止**

Undo 履歴をプロセス内メモリで保持する設計であるため、複数インスタンスが同時に同じフォルダを操作すると履歴の整合性が失われる。また、複数プロセスが同じログファイルのハンドルを保持するとローテーション時のリネームが失敗する。これらを避けるため多重起動を抑止する。

### **9.1 方式**

- 起動時に名前付きミューテックス（`ctypes` 経由の `CreateMutexW`）を取得する。`GetLastError()` が `ERROR_ALREADY_EXISTS` の場合は既に起動中と判断する。
- ミューテックス名はユーザーセッション内で一意になる固定文字列（例: `Local\rename-date-single-instance`）とする。
- 実装は `src/rename_date/single_instance.py` に隔離し、コンテキストマネージャとして提供する。

### **9.2 二重起動時の挙動**

1. 既存ウィンドウを検索して前面に表示する（`FindWindowW` + `SetForegroundWindow`）。
2. 新しいプロセスはメッセージを表示せずに終了する。
3. 既存ウィンドウの検出に失敗した場合のみ、「既に起動しています」というメッセージボックスを表示して終了する。

### **9.3 異常終了時の考慮**

名前付きミューテックスはプロセス終了時に OS が自動的に解放するため、アプリがクラッシュしてもロックが残留しない。ロックファイル方式に対する明確な利点であり、本方式を採用する理由の 1 つである。

## **10\. 配布・インストーラ**

### **10.1 実行ファイル化 (PyInstaller)**

- `installer/rename-date.spec` を用いてビルドする。
- **onedir** 形式（`console=False`）を採用する。onefile と比較して起動が速く、インストーラ形式での配布と相性が良いため。
- ビルドコマンド: `uv run pyinstaller installer/rename-date.spec`

### **10.2 インストーラ生成 (Inno Setup)**

- `installer/setup.iss` を用いてインストーラを生成する。

| 設定                 | 内容                                                                         |
| -------------------- | ---------------------------------------------------------------------------- |
| `AppId`              | 固定 GUID（アップグレード時の同一性判定に使用）                              |
| `AppVersion`         | `pyproject.toml` の `version` と同期させる                                   |
| `PrivilegesRequired` | `lowest`（ユーザー単位インストール。管理者権限を要求しない）                 |
| インストール先       | `{autopf}\rename-date`                                                       |
| ショートカット       | スタートメニュー（必須）、デスクトップ（任意選択）                           |
| アンインストール     | アンインストーラを生成。`%APPDATA%\rename-date` は**削除しない**（ログ保持） |

- 生成コマンド: `iscc installer\setup.iss`

## **11\. テスト方針**

### **11.1 ユニットテスト (pytest)**

Services 層は tkinter に依存しないため、GUI なしで完結してテストできる。ファイル操作は `tmp_path` フィクスチャ上の実 I/O で検証する。

| テストファイル    | 主な観点                                                                                                                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_scanner.py` | 基本変換 / ゼロ埋め / 1 ファイル内の複数マッチ / 拡張子の非対象 / 不正日付 / 隠しファイル・除外フォルダ / シンボリックリンク / 既存ファイルとの衝突 / 同一バッチ内の衝突 / 不正な正規表現とグループ数不一致 / 変更なしファイルの除外 |
| `test_renamer.py` | 成功時の履歴生成 / 実行直前に発生した衝突の SKIP / 権限エラー時の処理継続（`monkeypatch` で例外を注入）/ 無効項目のスキップ                                                                                                          |
| `test_undo.py`    | 逆順での復元 / ファイル欠損時のスキップ / 復元先が埋まっている場合のスキップ / 多段スタック / 空スタック                                                                                                                             |
| `test_log.py`     | ディレクトリの自動作成 / 追記 / タブ・改行のエスケープ / ローテーション（`maxBytes` を極小にして世代ファイルの生成と世代数の上限を検証）                                                                                             |

- カバレッジ目標: Services 層 85% 以上（`uv run pytest --cov=src/rename_date`）

### **11.2 手動統合テスト**

以下のダミーフォルダ構造に対してプレビュー → 実行 → Undo を検証する。

```text
sample/
├── テスト (2024.1.5).txt              → テスト 20240105.txt
├── メモ (2024.12.31) v2.txt           → メモ 20241231 v2.txt
├── 二重 (2023.1.1) と (2023.2.2).txt  → 二重 20230101 と 20230202.txt
├── 不正 (2024.13.45).txt              → 無効（実行対象外）
├── 既存 20240105.txt                  → 変更対象外（非表示）
├── 既存 (2024.1.5).txt                → 既存 20240105_1.txt（衝突回避）
├── .hidden/
│   └── 隠し (2024.1.1).txt            → 走査対象外
├── .git/
│   └── x (2024.1.1).txt               → 走査対象外
└── sub/
    └── 報告 (2025.3.7).pdf            → 報告 20250307.pdf
```

検証項目:

1. プレビューの内容が上表のとおりであること
2. 実行後にエクスプローラー上でファイル名が変更されていること
3. Undo により完全に元の状態へ復元されること
4. `%APPDATA%\rename-date\logs\rename_log.txt` に `RENAME` と `UNDO` の行が追記されていること
5. 数千ファイル規模のフォルダで走査中も UI が応答し、進捗が更新されキャンセルが機能すること
6. アプリを二重起動しようとすると既存ウィンドウが前面化されること
7. インストーラ経由でインストールしたアプリが起動し、アンインストール後もログが残ること

## **12\. スコープ外 / 将来の拡張候補**

本バージョンでは以下を実装しない。

- プレビュー画面でのチェックボックスによる対象の個別選択
- Redo（Undo の取り消し）
- フォルダ名のリネーム
- Undo 履歴の永続化（アプリ終了時に破棄する）
- 正規表現以外の変換ルール（連番付与、大文字小文字変換など）
- 除外パターンの GUI 上での編集（`config.py` の定数で管理する）
- 設定の永続化（前回選択フォルダ・正規表現の入力履歴）
- 多言語対応（UI は日本語のみ）
