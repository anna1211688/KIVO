; SPST 安装脚本 (Inno Setup 6) —— Jane 2026-11-25 定案: 提供安装版, 与单文件版并行发布。
; 构建: iscc /DAppVersion=x.y.z SPST.iss (GitHub Actions 自动执行, 本地也可跑)
; 设计要点: 按用户安装 (不弹管理员)、固定 AppId 实现原地升级覆盖、用户数据 %APPDATA%\SPST 永不触碰。
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef ExePath
  #define ExePath "dist\SPST.exe"
#endif

[Setup]
AppId={{3D397937-AD46-4899-9712-DDFB0B2CC28C}
AppName=SPST
AppVersion={#AppVersion}
AppVerName=SPST v{#AppVersion}
AppPublisher=SPST
DefaultDirName={autopf}\SPST
DefaultGroupName=SPST
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=SPST-Setup-{#AppVersion}
SetupIconFile=SPST.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AppMutex=SPST_SingleInstance_Mutex
CloseApplications=yes
UninstallDisplayName=SPST
UninstallDisplayIcon={app}\SPST.exe
VersionInfoVersion={#AppVersion}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "{#ExePath}"; DestDir: "{app}"; DestName: "SPST.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\SPST"; Filename: "{app}\SPST.exe"
Name: "{autodesktop}\SPST"; Filename: "{app}\SPST.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SPST.exe"; Description: "{cm:LaunchProgram,SPST}"; Flags: nowait postinstall skipifsilent
