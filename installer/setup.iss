#define MyAppName "rename-date"
#ifndef MyAppVersion
	#define MyAppVersion "0.1.0"
#endif

[Setup]
AppId={{A6F1E9C2-4B8D-4E1A-9F3C-2D7B5E8A1C40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=rename-date
DefaultDirName={autopf}\rename-date
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=rename-date-{#MyAppVersion}-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
#if FileExists("assets\app.ico")
SetupIconFile=assets\app.ico
#endif

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"

[Files]
Source: "..\dist\rename-date\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\rename-date.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\rename-date.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\rename-date.exe"; Description: "rename-dateを起動"; Flags: nowait postinstall skipifsilent