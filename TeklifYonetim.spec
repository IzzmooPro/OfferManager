# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('database/schema.sql', 'database')],
    # keyring: Windows Credential Manager arka ucu dinamik yüklenir —
    # açıkça belirtilmezse paketlenmiş EXE'de SMTP şifresi kaydedilemez
    hiddenimports=['PySide6.QtPdf', 'PySide6.QtPdfWidgets',
                   'keyring.backends.Windows'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TeklifYonetim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\ico.ico'],
    version='version_info.txt',
)
