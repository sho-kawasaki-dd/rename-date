# **ファイル名一括変換 GUI アプリ (Rename Date) 開発計画書**

## **1\. アプリケーション概要**

### **1.1 目的**

指定されたフォルダ配下を再帰的に走査し、正規表現パターン（例: (YYYY.M.D) 形式）にマッチするファイル名を ISO8601 簡易表現（YYYYMMDD）へ一括変更する GUI アプリケーションを開発する。

### **1.2 主な特徴**

- **再帰的検索**: サブフォルダ内のファイルも対象。
- **安心の事前プレビュー**: 変更を実行する前に一覧で差分を確認可能。
- **安全設計**: 変更後ファイル名の衝突自動回避・ログ出力。
- **Undo 機能**: 誤って実行した直前のリネーム操作を一括で取り消す（元に戻す）。
- **可変正規表現**: GUI 上で正規表現パターンを動的変更可能。

## **2\. 開発環境 & パッケージ管理 (uv)**

本プロジェクトでは Python のパッケージ・環境管理ツールとして **uv** を利用します。

### **2.1 環境構築手順**

\# プロジェクトの初期化  
uv init bulk_renamer \--app  
cd bulk_renamer

\# 依存パッケージの追加 (例: pytest 等の開発用ツール)  
uv add \--dev pytest pytest-cov

\# 仮想環境の有効化と実行  
uv run main.py

## **3\. ソフトウェアアーキテクチャ & モジュール構成**

責務の分離（Separation of Concerns）を徹底し、将来的なロジック追加やテスト容易性を担保するレイヤード構成とします。

### **3.1 アーキテクチャ構成**

\+-------------------------------------------------------+  
| UI Layer (Views) |  
| \- MainFrame, SettingsPanel, PreviewTree, ActionPanel |  
\+-------------------------------------------------------+  
 | (ユーザー操作 / 描画)  
 v  
\+-------------------------------------------------------+  
| Controller / Presenter |  
| \- AppController (UIイベント受付、状態管理) |  
\+-------------------------------------------------------+  
 | (ビジネスロジック呼び出し)  
 v  
\+-------------------------------------------------------+  
| Services Layer |  
| \- ScannerService : フォルダ走査 & パターン判定 |  
| \- RenameService : 実行 & リネーム処理 |  
| \- UndoService : 実行履歴管理 & 元に戻す処理 |  
| \- LogService : 処理結果のファイル出力 |  
\+-------------------------------------------------------+  
 | (データ共有)  
 v  
\+-------------------------------------------------------+  
| Models Layer |  
| \- RenameItem : 個別の変更情報モデル |  
| \- ExecutionHistory : 実行履歴データモデル |  
\+-------------------------------------------------------+

### **3.2 プロジェクト階層構造**

bulk_renamer/  
├── pyproject.toml \# uv / プロジェクト設定ファイル  
├── uv.lock \# ロックファイル  
├── README.md  
├── main.py \# アプリ起動エントリポイント  
├── app/  
│ ├── models/ \# データ構造定義  
│ │ ├── \_\_init\_\_.py  
│ │ └── rename_item.py \# ファイルパス・変更前後の名称情報保持  
│ │  
│ ├── services/ \# コアビジネスロジック  
│ │ ├── \_\_init\_\_.py  
│ │ ├── scanner_service.py \# フォルダ走査と正規表現マッチング  
│ │ ├── rename_service.py \# リネーム実行ロジック  
│ │ ├── undo_service.py \# Undo（逆変換）ロジック・履歴管理  
│ │ └── log_service.py \# ログ出力管理  
│ │  
│ ├── controllers/ \# アプリケーション制御  
│ │ ├── \_\_init\_\_.py  
│ │ └── app_controller.py \# UIとServicesの橋渡し・状態保持  
│ │  
│ └── views/ \# Tkinter GUI コンポーネント  
│ ├── \_\_init\_\_.py  
│ ├── main_window.py \# メインウィンドウ  
│ ├── config_frame.py \# フォルダ・正規表現入力部  
│ ├── preview_frame.py \# Treeview表示部  
│ └── action_frame.py \# 実行/Undo/カウント表示部  
│  
└── tests/ \# ユニットテスト (pytest)  
 ├── test_scanner.py  
 ├── test_renamer.py  
 └── test_undo.py

## **4\. 機能要件詳細**

### **4.1 画面機能 (Views)**

1. **設定エリア (ConfigFrame)**
   - 対象フォルダ選択（filedialog）
   - 正規表現パターン入力（デフォルト: \\((\\d{4})\\.(\\d{1,2})\\.(\\d{1,2})\\)）
   - 再プレビューボタン
2. **プレビューエリア (PreviewFrame)**
   - 対象ファイルの一覧表示（変更前ファイル名、変更後ファイル名、相対パス）
   - 変更対象外ファイルは非表示
3. **操作エリア (ActionFrame)**
   - 対象件数表示
   - 「一括変換を実行」ボタン
   - 「直前の実行を取り消す (Undo)」ボタン（履歴がある場合のみ有効化）
   - ログ保存設定チェックボックス

### **4.2 サービスロジック要件 (Services)**

#### **A. 走査・置換ロジック (ScannerService)**

- os.walk を使用したサブフォルダ走査。
- 指定された正規表現パターンでマッチング。
- YYYY.M.D 形式を YYYYMMDD 形式へ整形（1桁の月・日はゼロ埋め）。

#### **B. リネーム＆ログ出力 (RenameService, LogService)**

- リネーム実行前にファイルの存在チェック（同名ファイル衝突防止）。
- 実行結果（成功 / スキップ / エラー）を記録し、ログファイル (rename_log.txt) に追記。

#### **C. Undo ロジック (UndoService)**

- **履歴スタック構造**: 実行された一括リネーム操作のリスト（original_path と target_path のペア）をメモリ上のスタック（LIFO）構造で管理。
- **取り消し処理**:
  1. 履歴スタックから最新のセッションを取得。
  2. 競合を防ぐため、**実行時とは逆順**（末尾から）にファイル名を元の original_path へ復元。
  3. 復元完了後、履歴スタックから該当セッションを削除。
  4. Undo の実行自体もログファイルに記録。

## **5\. データモデル設計 (Models)**

### **RenameItem**

from dataclasses import dataclass  
from pathlib import Path

@dataclass  
class RenameItem:  
 original_path: Path  
 target_path: Path

    @property
    def original\_name(self) \-\> str:
        return self.original\_path.name

    @property
    def target\_name(self) \-\> str:
        return self.target\_path.name

    @property
    def parent\_dir(self) \-\> Path:
        return self.original\_path.parent

### **ExecutionHistory**

from dataclasses import dataclass, field  
from datetime import datetime  
from typing import List  
from app.models.rename_item import RenameItem

@dataclass  
class ExecutionHistory:  
 timestamp: datetime  
 items: List\[RenameItem\] \= field(default_factory=list)

## **6\. 開発ロードマップ (フェーズ別)**

### **Phase 1: プロジェクト初期化 & コアロジック実装**

1. uv init による環境構築およびディレクトリ構造のセットアップ
2. RenameItem モデルの実装
3. ScannerService (走査・置換) の作成 & pytest でのテスト
4. RenameService (ファイル変更) 及び UndoService (逆変換) の作成 & テスト

### **Phase 2: GUI コンポーネントのモジュール化**

1. 各 View コンポーネント (ConfigFrame, PreviewFrame, ActionFrame) の作成
2. コンポーネント配置とレイアウト調整

### **Phase 3: Controller による統合と動作検証**

1. AppController による Event Handling の接続
2. Undo ボタンの状態管理（実行後のみ活性化）
3. 統合テスト（ダミーフォルダ構造に対する実行と Undo 検証）

## **7\. 例外処理・安全対策方針**

1. **同名ファイルの競合**: 変更先に既存ファイルが存在する場合、リネームを行わず SKIP として処理を継続。
2. **権限エラー (PermissionError)**: ファイルが他アプリで開かれている等の理由でリネーム失敗時、エラーログを記録して処理を継続。
3. **Undo時の欠損対策**: Undo 実行時、リネーム後のファイルが手動で削除・移動されていた場合はスキップし、他のファイルの復元を継続。
