; installer.iss — Script Inno Setup para el Agente ESC/POS - Odoo 19
; Requiere Inno Setup 6: https://jrsoftware.org/isdownload.php
; Ejecutar con: ISCC.exe installer.iss

#define AppName      "Agente ESC/POS"
; Mantener en sync a mano con AGENT_VERSION en al_pos_local_agent.py —
; Inno Setup no puede leer una constante de Python. Actualizar ambos en el
; mismo commit.
#define AppVersion   "1.0.0"
#define AppPublisher "ALTA"
#define AppExeName   "AgenteEscpos.exe"

[Setup]
AppId={{8C902C77-AC51-4A37-8257-AE33D0E3ED50}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://www.altabpo.com
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=AgenteEscpos_Setup_{#AppVersion}
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=no
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=admin
; Cerrar la app si está corriendo antes de instalar
CloseApplications=yes
CloseApplicationsFilter=*{#AppExeName}*
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Crear acceso directo en el &Escritorio"; \
  GroupDescription: "Iconos adicionales:"; \
  Flags: checkedonce

Name: "startupicon"; \
  Description: "Iniciar automáticamente con &Windows"; \
  GroupDescription: "Inicio automático:"; \
  Flags: unchecked

[Files]
; Carpeta completa generada por PyInstaller (dist\AgenteEscpos\)
Source: "dist\AgenteEscpos\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Acceso directo en el menú inicio
Name: "{group}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Comment: "Agente ESC/POS para Odoo 19"

; Desinstalar desde el menú inicio
Name: "{group}\Desinstalar {#AppName}"; \
  Filename: "{uninstallexe}"

; Acceso directo en el escritorio (opcional)
Name: "{commondesktop}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon; \
  Comment: "Agente ESC/POS para Odoo 19"

; Inicio automático con Windows (opcional)
Name: "{userstartup}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Tasks: startupicon

[Run]
; Ofrecer iniciar la app al terminar la instalación
Filename: "{app}\{#AppExeName}"; \
  Description: "Iniciar {#AppName} ahora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpiar agent_gui_config.yaml al desinstalar (opcional — comentar para
; preservar la configuración entre reinstalaciones/actualizaciones)
; Type: files; Name: "{app}\agent_gui_config.yaml"

[Code]
// Verificar que Windows 10+ esté instalado
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsWin64 then
  begin
    MsgBox('Este programa requiere Windows 10 de 64 bits o superior.', mbError, MB_OK);
    Result := False;
  end;
end;
