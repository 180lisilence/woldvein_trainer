; 平野孤鸿修改器 Woldvein Trainer 安装脚本
; 使用 Inno Setup 6 编译

#define MyAppName "Woldvein Trainer"
#define MyAppVersion "0.4.6"
#define MyAppPublisher "Woldvein"
#define MyAppExeName "woldvein_trainer.exe"

[Setup]
AppId={{B7E2F3A4-1234-4ABC-9DEF-567890ABCDEF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WoldveinTrainer
DefaultGroupName=Woldvein Trainer
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=WoldveinTrainer_v{#MyAppVersion}_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
AppCopyright=Copyright (C) 2026 Woldvein

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: unchecked

[Files]
Source: "dist\woldvein_trainer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\woldvein_trainer.dll"; DestDir: "{app}\dist"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "locales\*"; DestDir: "{app}\locales"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\backups"
Type: filesandordirs; Name: "{app}\crash_reports"
Type: filesandordirs; Name: "{app}\presets"
