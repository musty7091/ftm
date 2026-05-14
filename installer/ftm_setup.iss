; FTM Finans Takip Merkezi - Inno Setup Installer Script
; ADIM 4.4B - Ev bilgisayarÄ± installer hazÄ±rlÄ±ÄŸÄ±
;
; Proje kÃ¶kÃ¼:
; D:\DEV\PROJECTS\FTM
;
; Beklenen klasÃ¶r yapÄ±sÄ±:
; D:\DEV\PROJECTS\FTM
; â”œâ”€ dist\FTM\FTM.exe
; â”œâ”€ dist\FTM\_internal\config\central_mail_settings.json
; â”œâ”€ ftm_branding_assets\ikon.ico
; â”œâ”€ installer\ftm_setup.iss
; â””â”€ release_packages\
;
; Ã–NEMLÄ°:
; - Installer iÃ§ine mÃ¼ÅŸteri veritabanÄ± koyma.
; - Installer iÃ§ine lisans dosyasÄ± koyma.
; - Installer iÃ§ine License Maker koyma.
; - Installer iÃ§ine private key koyma.
; - Installer iÃ§ine .env koyma.
; - central_mail_settings.json sadece EXE Ã§alÄ±ÅŸma klasÃ¶rÃ¼ndeki _internal\config altÄ±na dahil edilir.
; - Build sonrasÄ± release package safety checker Ã§alÄ±ÅŸtÄ±r.

#define ProjectRoot "C:\ftm"

#define MyAppName "FTM Finans Takip Merkezi"
#define MyAppShortName "FTM"
#define MyAppVersion "0.8.0"
#define MyAppPublisher "FTM Finans Takip Merkezi"
#define MyAppExeName "FTM.exe"

#define MyAppSourceDir ProjectRoot + "\dist\FTM"
#define MyAppExeFile MyAppSourceDir + "\" + MyAppExeName
#define MyCentralMailSettingsFile MyAppSourceDir + "\_internal\config\central_mail_settings.json"

#define MyAppIconFile ProjectRoot + "\ftm_branding_assets\ikon.ico"
#define MyOutputDir ProjectRoot + "\release_packages"

#ifnexist MyAppExeFile
  #error "Ana uygulama EXE dosyasi bulunamadi: D:\DEV\PROJECTS\FTM\dist\FTM\FTM.exe"
#endif

#ifnexist MyCentralMailSettingsFile
  #error "Merkezi mail ayar dosyasi bulunamadi: D:\DEV\PROJECTS\FTM\dist\FTM\_internal\config\central_mail_settings.json"
#endif

#ifnexist MyAppIconFile
  #error "Installer ikon dosyasi bulunamadi: D:\DEV\PROJECTS\FTM\ftm_branding_assets\ikon.ico"
#endif

[Setup]
AppId={{BFD2BCE7-1139-4E33-AD2D-7F4B9E65F7D7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename=FTM_Setup_{#MyAppVersion}
SetupIconFile={#MyAppIconFile}
UninstallDisplayIcon={app}\ikon.ico
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
MinVersion=10.0
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Kurulum SihirbazÄ±
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "MasaÃ¼stÃ¼ne FTM kÄ±sayolu oluÅŸtur"; GroupDescription: "Ek kÄ±sayollar:"; Flags: checkedonce

[Dirs]
Name: "{app}"; Permissions: users-readexec
Name: "{app}\_internal"; Permissions: users-readexec
Name: "{app}\_internal\config"; Permissions: users-readexec

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.db,*.sqlite,*.sqlite3,*.pem,*.key,*.p12,*.pfx,*.ftmlic,.env,license.json,license.json.bak,license_clock_state.json,device_identity.json,app_settings.json,app_setup.json,backup_mail_settings.json,central_mail_settings.json,tools\*,keys\*,logs\*,backups\*,exports\*,source\*,sources\*,.git\*,.github\*,__pycache__\*,.pytest_cache\*,.mypy_cache\*,.ruff_cache\*,venv\*,.venv\*"
Source: "{#MyCentralMailSettingsFile}"; DestDir: "{app}\_internal\config"; DestName: "central_mail_settings.json"; Flags: ignoreversion
Source: "{#MyAppIconFile}"; DestDir: "{app}"; DestName: "ikon.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "{#MyAppName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\ikon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "{#MyAppName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasÄ±nÄ± baÅŸlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\ikon.ico"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    Log('FTM kurulumu tamamlandi. Kullanici verileri Program Files altina yazilmaz. Runtime veriler LOCALAPPDATA\FTM altinda tutulur.');
    Log('Merkezi mail ayari su konuma dahil edildi: ' + ExpandConstant('{app}\_internal\config\central_mail_settings.json'));
  end;
end;
