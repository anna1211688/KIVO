; KIVO 安装脚本 (Inno Setup 6, 原 SPST.iss) —— 2026-11-27 品牌升级 SPST→KIVO 启沃: 显示名/图标/安装包名全换 KIVO, 但 AppId GUID 与安装目录 {autopf}\SPST 故意保留 (原地升级身份与老快捷方式兼容的根基, 改了会双份安装/升级断链)。
; 构建: iscc /DAppVersion=x.y.z SPST.iss (GitHub Actions 自动执行, 本地也可跑)
; 设计要点: 按用户安装 (不弹管理员)、固定 AppId 实现原地升级覆盖、用户数据 %APPDATA%\SPST 永不触碰。
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef ExePath
  #define ExePath "dist\KIVO.exe"
#endif

[Setup]
AppId={{3D397937-AD46-4899-9712-DDFB0B2CC28C}
AppName=KIVO
AppVersion={#AppVersion}
AppVerName=KIVO v{#AppVersion}
AppPublisher=KIVO
DefaultDirName={autopf}\SPST
DefaultGroupName=KIVO
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=KIVO-Setup-{#AppVersion}
SetupIconFile=KIVO.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AppMutex=SPST_SingleInstance_Mutex
CloseApplications=yes
UninstallDisplayName=KIVO 启沃智能工作台
UninstallDisplayIcon={app}\KIVO.exe
VersionInfoVersion={#AppVersion}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[InstallDelete]
Type: files; Name: "{autodesktop}\SPST.lnk"
Type: files; Name: "{group}\SPST.lnk"
Type: files; Name: "{app}\SPST.exe"

[Files]
Source: "{#ExePath}"; DestDir: "{app}"; DestName: "KIVO.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\KIVO"; Filename: "{app}\KIVO.exe"
Name: "{autodesktop}\KIVO"; Filename: "{app}\KIVO.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KIVO.exe"; Description: "{cm:LaunchProgram,KIVO}"; Flags: nowait postinstall skipifsilent
