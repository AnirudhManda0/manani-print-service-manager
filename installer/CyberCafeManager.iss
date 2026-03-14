; Inno Setup script for installed mode deployment

#define MyAppName "CyberCafe Print & Service Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "CyberCafe Systems"
#define MyAppExeName "CyberCafeManager.exe"

[Setup]
AppId={{F26F2F49-3C93-4E85-B346-4D6C48C89391}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\CyberCafeManager
DefaultGroupName=CyberCafe Manager
OutputDir=dist
OutputBaseFilename=CyberCafeManagerInstaller
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\CyberCafeManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config\settings.json"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "..\database\schema.sql"; DestDir: "{app}\database"; Flags: ignoreversion

[Icons]
Name: "{group}\CyberCafe Manager"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\CyberCafe Manager"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CyberCafe Manager"; Flags: nowait postinstall skipifsilent
