; Inno Setup скрипт установщика NetPulse для Windows 10/11 (x64)
; Сборка: iscc windows\installer.iss  (сначала соберите exe через build.bat)

#define AppName      "NetPulse"
#define AppVersion   "1.1.0"
#define AppPublisher "NetPulse"
#define AppURL       "https://github.com/Escapist27/Net-Pulse---Lightweight-Network-Monitor"
#define AppExe       "NetPulse.exe"

[Setup]
AppId={{7B3E2A91-4C5D-4F8E-9A1B-2C6D8E0F3A57}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=NetPulse-Setup-{#AppVersion}
SetupIconFile=..\assets\netpulse.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Ставим в Program Files (Windows один раз спросит разрешение) — обновляет уже установленную версию
PrivilegesRequired=admin
CloseApplications=yes
; Установка без лишних окон: язык берётся из Windows, сразу ставим и показываем «Готово»
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage
DisableWelcomePage=yes
DisableDirPage=yes
DisableReadyPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\NetPulse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
