# rename-date

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
