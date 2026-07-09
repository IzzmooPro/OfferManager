#define MyAppName "Teklif Yönetim"
#define MyAppVersion "v3.0"
#define MyAppPublisher "IzzmooPro"
#define MyAppExeName "TeklifYonetim.exe"

[Setup]
AppId={{F40CDF0C-EE45-4C08-B6C8-ACF9B7A233D2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} sürümü
AppPublisher={#MyAppPublisher}
AppPublisherURL=mailto:IzzmooPro@gmail.com
AppSupportURL=https://github.com/IzzmooPro/offer_management_system
AppUpdatesURL=https://github.com/IzzmooPro/offer_management_system/releases
DefaultDirName={autopf}\Teklif Yönetim
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=installer_output
OutputBaseFilename=TeklifYonetim_Setup_{#MyAppVersion}
SetupIconFile=assets\ico.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=TeklifYonetim.exe
RestartApplications=no
AppMutex=TeklifYonetimSistemi_AppMutex
SetupMutex=TeklifYonetimSistemi_SetupMutex
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=3.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Kurulumu
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=3.0.0.0

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent
