; ==========================================================
; Parrator — скрипт установщика для Inno Setup 6
; ==========================================================

#define MyAppName "Parrator"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "NullSense"
#define MyAppExeName "Parrator.exe"
#define MyAppDescription "Speech to text — распознавание речи"

[Setup]
AppId={{196A04F7-B35C-4FCC-9B86-468BD2B78EE8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=ParratorSetup-{#MyAppVersion}
SetupIconFile=..\parrator\resources\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Parrator\Parrator.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\Parrator\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлык на рабочем столе — GUI-режим (с окном)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Меню Пуск — GUI-режим (с окном)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; IconFilename: "{app}\{#MyAppExeName}"
; Меню Пуск — фоновый режим (только трей)
Name: "{group}\{#MyAppName} (Фоновый режим)"; Filename: "{app}\{#MyAppExeName}"
; Меню Пуск — удаление
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Завершить запущенный Parrator перед установкой/удалением
procedure KillRunningApp;
var
  ResultCode: Integer;
begin
  Exec('taskkill', '/f /im {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
end;

function InitializeSetup(): Boolean;
begin
  KillRunningApp;
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  KillRunningApp;
  Result := True;
end;
