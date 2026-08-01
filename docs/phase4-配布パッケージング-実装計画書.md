# Phase 4: 配布パッケージング 実装計画書

対象: [rename-date開発計画書.md](./rename-date開発計画書.md) 第6章 Phase 4、第10章（配布・インストーラ）。

## 目的

Phase 1〜3 で実装済みのアプリケーションを PyInstaller で実行ファイル化し、Inno Setup で
Windows 用インストーラーとして配布できる状態にする。あわせて、実行ファイル化とインストーラー化を
1 コマンドで実行できる PowerShell スクリプトを用意し、以後のリリース作業を再現可能にする。

## 決定事項（本計画に先立ちユーザーと合意済み）

1. **アイコン**: `.ico` ファイルは現時点で未用意。`installer/assets/app.ico` を参照パスとして
   用意しておき、存在しない場合は `.spec` / `.iss` の双方でアイコン指定を自動的に省略する
   フォールバックを実装する。
2. **Inno Setup Compiler の場所**: `iscc.exe` が PATH に通っている前提でそのまま呼び出す。
   既定インストール先へのフォールバック探索は行わない。見つからない場合は分かりやすいエラー
   メッセージでビルドスクリプトを停止する。
3. **AppId (GUID)**: 新規生成した固定 GUID `{A6F1E9C2-4B8D-4E1A-9F3C-2D7B5E8A1C40}` を使用する
   （必要であれば後日 Inno Setup の GUID 生成ツールで差し替え可能）。
4. **デスクトップショートカット**: インストーラーの `[Tasks]` で既定 ON（チェック済み状態）とする。
5. **PowerShell ビルドスクリプトの配置**: `scripts/build-release.ps1` に配置する。
6. **バージョン管理**: `pyproject.toml` の `version` を正とし、ビルドスクリプトがそこから読み取って
   Inno Setup へ注入する。`src/rename_date/__init__.py` の `__version__` と不一致の場合はビルドを
   止めずに警告のみ表示する。
7. **スコープ外**: LICENSE ファイルの作成、アイコン画像自体のデザイン、
   `single_instance.py` への frozen 判定追加は行わない。

## 要件

- `installer/rename-date.spec` は onedir 形式・ウィンドウアプリ（`console=False`）としてビルドされ、
  `dist/rename-date/rename-date.exe` が生成されること。
- `tkinterdnd2` の `tkdnd` アセット（Tcl 拡張）がビルド後の実行ファイルに同梱され、
  ドラッグ&ドロップが動作すること。
- `installer/setup.iss` は `PrivilegesRequired=lowest`、インストール先 `{autopf}\rename-date` で
  ビルドされ、アンインストール時に `%APPDATA%\rename-date`（ログ・設定）を削除しないこと。
- `scripts/build-release.ps1` を実行するだけで、クリーン → PyInstaller ビルド → Inno Setup
  パッケージングまでが 1 コマンドで完了し、失敗時は分かりやすいエラーで停止すること。
- README にビルド・配布手順が記載されていること。

## タスク

### 1. PyInstaller spec の実装（`installer/rename-date.spec`）

- [ ] `main.py` を起点に `Analysis` → `PYZ` → `EXE(exclude_binaries=True)` → `COLLECT` の onedir
      構成とし、`name="rename-date"`, `console=False` を設定する。
- [ ] `tkinterdnd2` の `tkdnd` フォルダを `datas` に追加する。
      `import tkinterdnd2; os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd")` で
      解決したパスを `("tkinterdnd2/tkdnd")` 宛先で同梱する。
- [ ] `installer/assets/app.ico` の存在を `os.path.exists` で確認し、存在すれば `EXE` の `icon=` に
      指定、存在しなければ `icon=None` とする（ディレクトリ自体は作成し参照パスを確保する）。
- [ ] `uv run pyinstaller installer/rename-date.spec --noconfirm --clean` で
      `dist/rename-date/rename-date.exe` が生成されることを確認する。

### 2. Inno Setup スクリプトの実装（`installer/setup.iss`）

- [ ] `#define MyAppName "rename-date"` と `AppId={{A6F1E9C2-4B8D-4E1A-9F3C-2D7B5E8A1C40}}` を
      固定値として設定する。
- [ ] `MyAppVersion` はビルドスクリプトから `/DMyAppVersion=x.y.z` として注入される前提とし、
      `AppVersion={#MyAppVersion}` に反映する。未指定時のデフォルト値も用意し、`iscc` 単体実行でも
      壊れないようにする。
- [ ] `PrivilegesRequired=lowest`、`DefaultDirName={autopf}\rename-date` を設定する。
- [ ] `[Files]` セクションで `Source: "..\dist\rename-date\*"; DestDir: "{app}"; Flags: recursesubdirs
      createallsubdirs ignoreversion` を指定する。
- [ ] `[Icons]` にスタートメニュー用ショートカットを必須作成し、`[Tasks]` に `desktopicon` タスク
      （既定 ON、`unchecked` フラグなし）を追加してデスクトップショートカットを条件付き作成する。
- [ ] `%APPDATA%\rename-date` を削除する処理を一切入れない（アンインストール後もログ・設定が
      残ることを保証する）。
- [ ] `#if FileExists("assets\app.ico")` ガードで `SetupIconFile` を条件付き設定する。
- [ ] `[Run]` に「インストール後にアプリを起動する」チェック付きの起動エントリを追加する。

### 3. PowerShell 一括ビルドスクリプトの実装（`scripts/build-release.ps1`）

- [ ] `$ErrorActionPreference = 'Stop'` を設定し、`$PSScriptRoot\..` をリポジトリルートとして
      `Push-Location` する（`finally` で `Pop-Location`）。
- [ ] `pyproject.toml` を読み込み、正規表現 `version\s*=\s*"([^"]+)"` でバージョン文字列を抽出する。
- [ ] `src/rename_date/__init__.py` の `__version__` と比較し、不一致であれば `Write-Warning` で
      警告を表示する（ビルドは継続する）。
- [ ] `build/`, `dist/`, `installer/Output/` を `Remove-Item -Recurse -Force -ErrorAction
      SilentlyContinue` で事前クリーンする。
- [ ] `uv run pyinstaller installer/rename-date.spec --noconfirm --clean` を実行し、
      `$LASTEXITCODE` を確認、非ゼロなら例外を投げて停止する。
- [ ] `dist/rename-date/rename-date.exe` の存在を確認し、存在しなければ明示的なエラーで停止する。
- [ ] `Get-Command iscc.exe -ErrorAction SilentlyContinue` で存在確認し、見つからなければ
      「Inno Setup をインストールし iscc.exe を PATH に追加してください」という趣旨のエラーで
      停止する。
- [ ] `iscc.exe /DMyAppVersion=$version installer\setup.iss` を実行し、終了コードを確認する。
- [ ] 成功時、生成されたインストーラー（`installer/Output/*.exe`）のパスをコンソールに出力する。

### 4. ドキュメント整備

- [ ] `README.md` に、`uv sync` → `pwsh scripts/build-release.ps1` の 1 コマンドで実行ファイル化と
      インストーラー生成が完了する旨、生成物の場所（`dist/rename-date/`, `installer/Output/`）を
      追記する。

### 5. 動作確認

- [ ] `pwsh -File scripts/build-release.ps1` を実行し、エラーなく `installer/Output/` に
      インストーラーが生成されることを確認する。
- [ ] 生成されたインストーラーで インストール → 起動 → ドラッグ&ドロップ動作確認
      （tkdnd 資産同梱の確認）→ 簡単なリネーム実行 → アンインストールの一連を手動検証する。
- [ ] アンインストール後も `%APPDATA%\rename-date` のログ・設定が残っていることを確認する。
- [ ] `installer/assets/app.ico` が存在しない状態でもビルド・インストールが正常に完了することを
      確認する（アイコン未設定時のフォールバック動作確認）。
- [ ] `src/rename_date/__init__.py` の `__version__` を意図的にずらし、ビルドスクリプトが警告を
      出しつつも処理を継続することを確認する。
- [ ] `iscc.exe` が PATH にない状態を再現し、分かりやすいエラーでスクリプトが停止することを
      確認する。

## スコープ外（本フェーズで実装しないこと）

- LICENSE ファイルの作成。
- アイコン画像 (`installer/assets/app.ico`) 自体のデザイン・作成。
- `single_instance.py` への PyInstaller frozen 判定の追加（現状のままで動作するため不要）。
- `scripts/build-release.ps1` への追加オプション引数（`-SkipInstaller` 等）の実装。常に
  クリーン → ビルド → パッケージングを一括実行する単一の使い方のみをサポートする。
- Redo、フォルダ名リネーム、Undo 履歴の永続化など、開発計画書 12 章記載のスコープ外事項。
