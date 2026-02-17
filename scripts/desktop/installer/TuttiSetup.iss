#ifndef AppVersion
#define AppVersion "0.1.1"
#endif

#ifndef SourceExe
#define SourceExe "..\..\..\dist\Tutti Desktop.exe"
#endif

#ifndef OutputDir
#define OutputDir "..\..\..\dist\desktop-app"
#endif

#define AppName "TUTTI"
#define AppPublisher "ODINX Labs"
#define AppExeName "Tutti Desktop.exe"

[Setup]
AppId={{0AB94EDE-1F72-4B9C-BDAB-157A5A6B0F3E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\TUTTI
DefaultGroupName=TUTTI
LicenseFile={#SourcePath}\license_es.txt
OutputDir={#OutputDir}
OutputBaseFilename=TuttiSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Opciones adicionales:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\TUTTI"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\TUTTI"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

; Avoid launching immediately after install/update to prevent sporadic
; PyInstaller onefile startup race ("Failed to load Python DLL ... _MEI...").
; User starts TUTTI manually once setup completes.
