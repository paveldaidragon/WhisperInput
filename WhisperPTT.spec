# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for WhisperPTT system tray app."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Collect native libraries
ct2_datas = collect_data_files('ctranslate2')
ct2_binaries = collect_dynamic_libs('ctranslate2')
pyaudio_binaries = collect_dynamic_libs('pyaudio')
pystray_datas = collect_data_files('pystray')

a = Analysis(
    ['tools/tray_app.py'],
    pathex=['tools'],
    binaries=ct2_binaries + pyaudio_binaries,
    datas=ct2_datas + pystray_datas + [('.env.example', '.'), ('README.md', '.')],
    hiddenimports=[
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL._imaging',
        'pyaudio',
        'ctranslate2',
        'faster_whisper',
        'pyperclip',
        'numpy',
        'dotenv',
        'keyboard',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'appdirs',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WhisperPTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
