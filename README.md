# rename-date

ファイル名の日付表現を一括変換する Windows 向け GUI アプリです。メイン画面の「ログ」タブから、変換と Undo の処理ログを新しい順に確認できます。

## 開発

依存関係を同期してアプリを起動します。

```powershell
uv sync
uv run main.py
```

## ビルドと配布

Windows 用の実行ファイルと Inno Setup インストーラーは、次の1コマンドで生成できます。

```powershell
uv sync
pwsh scripts/build-release.ps1
```

PyInstaller の onedir 出力は `dist/rename-date/`、インストーラーは
`installer/Output/` に生成されます。インストーラーの作成には `iscc.exe` が PATH に必要です。
