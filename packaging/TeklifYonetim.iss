#define MyAppName "Teklif Yönetim"
#define MyAppVersion "v4.4"
#define MyAppPublisher "IzzmooPro"
#define MyAppExeName "TeklifYonetim.exe"

[Setup]
AppId={{F40CDF0C-EE45-4C08-B6C8-ACF9B7A233D2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} sürümü
AppPublisher={#MyAppPublisher}
AppPublisherURL=mailto:IzzmooPro@gmail.com
AppSupportURL=https://github.com/IzzmooPro/OfferManager
AppUpdatesURL=https://github.com/IzzmooPro/OfferManager/releases
DefaultDirName={autopf}\Teklif Yönetim
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=..\installer_output
OutputBaseFilename=TeklifYonetim_Setup_{#MyAppVersion}
SetupIconFile=..\assets\ico.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; AppMutex BİLEREK YOK: varsa Inno başlangıçta "uygulamayı kapatın" manuel
; uyarısı gösteriyordu (otomatik güncellemede program henüz kapanmadan). Onun
; yerine CloseApplications=yes (Restart Manager) çalışan uygulamayı kurulum
; sırasında kendisi nazikçe kapatır — kullanıcıya uyarı çıkmaz.
CloseApplications=yes
CloseApplicationsFilter=TeklifYonetim.exe
RestartApplications=no
SetupMutex=TeklifYonetimSistemi_SetupMutex
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=4.4.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Kurulumu
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=4.4.0.0

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
; Varsayılan İŞARETLİ (unchecked bayrağı yok) — kullanıcı istemezse kaldırır
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"

[InstallDelete]
; Önceki Python/PyInstaller tabanından kalan, yeni pakette artık bulunmayan
; DLL'leri yerinde yükseltmede temizle. api-ms-win jokeri yalnız uygulamanın
; yönettiği _internal içindeki bu kesin ad ailesine uzanır; [Files] sonradan
; yeni dist'te bulunan aynı adlı dosyaları yeniden yazar. Klasör veya kullanıcı
; verisi silinmez.
Type: files; Name: "{app}\_internal\libcrypto-3-x64.dll"
Type: files; Name: "{app}\_internal\libssl-3-x64.dll"
Type: files; Name: "{app}\_internal\api-ms-win-*.dll"
Type: files; Name: "{app}\_internal\ucrtbase.dll"

[Files]
; onedir: PyInstaller çıktısı klasör halinde (exe + _internal\) — tamamı kurulur
Source: "..\dist\TeklifYonetim\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

[Code]
// Inno Setup 7 (önizleme) BUG ATLATMASI — SİLME!
// [Code] bölümü OLMAYAN kurulumlarda kaldırıcı "PathRedir: Not initialized"
// iç hatası veriyor (7.0.1 sürüm notlarında düzeltildiği yazan bug).
// Bu zararsız fonksiyon [Code] bölümünün var olmasını garanti eder.
function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

// Kurulumdan HEMEN ÖNCE çalışan uygulamayı KESİN kapat. Otomatik güncellemede
// eski program bazen düzgün kapanmayıp asılı kalıyor; Restart Manager onu
// kapatamayınca "uygulamayı kapatın" döngüsüne giriyordu. taskkill /F asılı
// süreci de sonlandırır — güncellemeyi hangi eski sürüm başlatırsa başlatsın çalışır.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM TeklifYonetim.exe',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
