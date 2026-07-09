@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=TeklifYonetim"
set "ISS_FILE=TeklifYonetim.iss"

REM ── Sürüm tek kaynaktan okunur (core/constants.py → APP_VERSION) ──
for /f %%v in ('python -c "from core.constants import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%v"
if not defined APP_VERSION (
    echo [HATA] Surum okunamadi ^(core/constants.py^).
    goto :fail
)
set "SETUP_FILE=installer_output\%APP_NAME%_Setup_%APP_VERSION%.exe"

REM ── Inno Setup: 7 yoksa 6'ya bak ──
set "ISCC=C:\Program Files\Inno Setup 7\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

echo ============================================================
echo   Teklif Yonetim Sistemi %APP_VERSION% - EXE ve Setup Derleme
echo ============================================================
echo.

echo [1/6] Derleme araclari kontrol ediliyor...
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller bulunamadi. Kuruluyor...
    python -m pip install pyinstaller
    if errorlevel 1 goto :fail
)
if not exist "%ISCC%" (
    echo [HATA] Inno Setup Compiler bulunamadi ^(6 veya 7^).
    goto :fail
)
echo [OK] PyInstaller ve Inno Setup hazir: %ISCC%
echo.

echo [2/6] Otomatik testler calistiriliyor ^(pytest — izole veriyle^)...
REM ONEMLI: Testler MUTLAKA pytest ile kosulmali. pytest, tests/conftest.py
REM sayesinde verileri gecici klasore yonlendirir. "unittest discover"
REM conftest'i KULLANMAZ ve testler GERCEK veritabanini/ayarlari siler!
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo pytest bulunamadi. Kuruluyor...
    python -m pip install pytest
    if errorlevel 1 goto :fail
)
set "QT_QPA_PLATFORM=offscreen"
python -m pytest tests -q
set "TEST_RC=%ERRORLEVEL%"
set "QT_QPA_PLATFORM="
if not "%TEST_RC%"=="0" goto :fail
echo [OK] Testler basarili.
echo.

echo [3/6] Eski derleme ciktilari temizleniyor...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "installer_output" rmdir /s /q "installer_output"
echo [OK] Temizlik tamamlandi.
echo.

echo [4/6] Tek dosya EXE derleniyor...
python -m PyInstaller --noconfirm --clean "%APP_NAME%.spec"
if errorlevel 1 goto :fail
if not exist "dist\%APP_NAME%.exe" (
    echo [HATA] EXE dosyasi olusmadi.
    goto :fail
)
echo [OK] EXE: dist\%APP_NAME%.exe
echo.

echo [5/6] Inno Setup paketi derleniyor...
"%ISCC%" "%ISS_FILE%"
if errorlevel 1 goto :fail
if not exist "%SETUP_FILE%" (
    echo [HATA] Setup dosyasi olusmadi: %SETUP_FILE%
    goto :fail
)
echo [OK] Setup: %SETUP_FILE%
echo.

echo [6/6] Dosyalar dogrulaniyor...
for %%F in ("dist\%APP_NAME%.exe") do echo EXE   : %%~fF  [%%~zF bayt]
for %%F in ("%SETUP_FILE%") do echo SETUP : %%~fF  [%%~zF bayt]
echo.
echo ============================================================
echo   DERLEME BASARILI  ^(%APP_VERSION%^)
echo ============================================================
goto :end

:fail
echo.
echo ============================================================
echo   DERLEME BASARISIZ
echo ============================================================
if /I not "%~1"=="--no-pause" pause
exit /b 1

:end
if /I not "%~1"=="--no-pause" pause
exit /b 0
