[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

Push-Location $repositoryRoot
try {
    $pyprojectPath = Join-Path $repositoryRoot 'pyproject.toml'
    $pyprojectContent = Get-Content -Path $pyprojectPath -Raw
    $versionMatch = [regex]::Match($pyprojectContent, 'version\s*=\s*"([^"]+)"')
    if (-not $versionMatch.Success) {
        throw "pyproject.toml からプロジェクトバージョンを取得できません。"
    }
    $version = $versionMatch.Groups[1].Value

    foreach ($path in @('build', 'dist', 'installer\Output')) {
        Remove-Item -Path (Join-Path $repositoryRoot $path) -Recurse -Force -ErrorAction SilentlyContinue
    }

    & uv run pyinstaller installer\rename-date.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller のビルドに失敗しました (終了コード: $LASTEXITCODE)。"
    }

    $executablePath = Join-Path $repositoryRoot 'dist\rename-date\rename-date.exe'
    if (-not (Test-Path -Path $executablePath -PathType Leaf)) {
        throw "PyInstaller の出力が見つかりません: $executablePath"
    }

    $iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($null -eq $iscc) {
        throw "Inno Setup をインストールし、iscc.exe を PATH に追加してください。"
    }

    & $iscc.Source "/DMyAppVersion=$version" installer\setup.iss
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup のパッケージングに失敗しました (終了コード: $LASTEXITCODE)。"
    }

    $installer = Get-ChildItem -Path (Join-Path $repositoryRoot 'installer\Output') -Filter '*.exe' -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $installer) {
        throw "インストーラーが生成されませんでした。"
    }

    Write-Host "インストーラーを生成しました: $($installer.FullName)"
}
catch {
    Write-Error $_
    throw
}
finally {
    Pop-Location
}