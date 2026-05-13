; FTM Finans Takip Merkezi - Inno Setup Installer Script
; ADIM 4.2
;
; Bu script, PyInstaller ile üretilmiş FTM klasörünü tek EXE kurulum dosyasına dönüştürür.
;
; Beklenen klasör yapısı:
; C:\ftm
; ├─ dist\FTM\FTM.exe
; ├─ ftm_branding_assets\ikon.ico
; └─ installer\ftm_setup.iss
;
; ÖNEMLİ:
; - Installer içine müşteri veritabanı koyma.
; - Installer içine lisans dosyası koyma.
; - Installer içine Licence Maker koyma.
; - Installer içine private key koyma.
; - Build sonrası safety checker çalıştır.

#define MyAppName "FTM Finans Takip Merkezi"
#define MyAppShortName "FTM"
#define MyAppVersion "0.8.0"
#define MyAppPublisher "FTM Finans Takip Merkezi"
#define MyAppExeName "FTM.exe"
#define MyAppSourceDir "..\dist\FTM"
#define MyAppExeFile MyAppSourceDir + "\" + MyAppExeName
#define MyAppIconFile "..\ftm_branding_assets\ikon.ico"
#define MyOutputDir "..\release_packages"

#ifnexist MyAppSourceDir
  #error "PyInstaller cikti klasoru bulunamadi: ..\dist\FTM"
#endif

#ifnexist MyAppExeFile
  #error "Ana uygulama EXE dosyasi bulunamadi: ..\dist\FTM\FTM.exe"
#endif

#ifnexist MyAppIconFile
  #error "Installer ikon dosyasi bulunamadi: ..\ftm_branding_assets\ikon.ico"
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
VersionInfoDescription={#MyAppName} Kurulum Sihirbazı
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne FTM kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Flags: checkedonce

[Dirs]
Name: "{app}"; Permissions: users-readexec

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.db,*.sqlite,*.sqlite3,*.pem,*.key,*.p12,*.pfx,*.ftmlic,.env,license.json,license.json.bak,license_clock_state.json,device_identity.json,app_settings.json,app_setup.json,backup_mail_settings.json,tools\*,keys\*,logs\*,backups\*,exports\*,source\*,sources\*,.git\*,.github\*,__pycache__\*,.pytest_cache\*,.mypy_cache\*,.ruff_cache\*,venv\*,.venv\*"
Source: "{#MyAppIconFile}"; DestDir: "{app}"; DestName: "ikon.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "{#MyAppName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\ikon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "{#MyAppName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

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
  end;
end;
