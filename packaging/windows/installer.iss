; Instalador de Nihongo Desk (Inno Setup 6). Lo ejecuta build_windows.ps1:
;   ISCC /DAppVersion=0.2.0 /DSourceDir=...\NihongoDesk /DOutputDir=...\dist installer.iss
;
; · Instala para el usuario actual, sin permisos de administrador
;   (%LOCALAPPDATA%\Programs\Nihongo Desk).
; · Accesos directos en el menú Inicio y, si se marca, en el escritorio e inicio con Windows.
; · Al actualizar, reemplaza el programa pero NUNCA toca los datos del usuario
;   (%APPDATA%\NihongoDesk: progreso, ajustes, mascota). Tampoco el desinstalador.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\build\windows\pyi-dist\NihongoDesk"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{6B1E8C52-3F4A-4E7B-9C1D-2A5E7F9B0D31}
AppName=Nihongo Desk
AppVersion={#AppVersion}
AppVerName=Nihongo Desk {#AppVersion}
AppPublisher=Nihongo Desk
DefaultDirName={autopf}\Nihongo Desk
DefaultGroupName=Nihongo Desk
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutputDir}
OutputBaseFilename=NihongoDesk-{#AppVersion}-setup
SetupIconFile=..\..\nihongo_desk\assets\icons\daruma.ico
UninstallDisplayIcon={app}\NihongoDesk.exe
UninstallDisplayName=Nihongo Desk
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no
MinVersion=10.0

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
es.Autostart=Iniciar Nihongo Desk al encender el ordenador (oculto en la bandeja)
en.Autostart=Start Nihongo Desk with Windows (hidden in the tray)
es.Launch=Abrir Nihongo Desk
en.Launch=Launch Nihongo Desk

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:Autostart}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; limpia archivos de la versión anterior del programa (solo dentro de {app})
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Nihongo Desk"; Filename: "{app}\NihongoDesk.exe"
Name: "{group}\{cm:UninstallProgram,Nihongo Desk}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Nihongo Desk"; Filename: "{app}\NihongoDesk.exe"; Tasks: desktopicon
Name: "{userstartup}\Nihongo Desk"; Filename: "{app}\NihongoDesk.exe"; Parameters: "--hidden"; Tasks: autostart

[Run]
Filename: "{app}\NihongoDesk.exe"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\NihongoDesk.exe"; Parameters: "--quit"; Flags: runhidden; RunOnceId: "QuitApp"
