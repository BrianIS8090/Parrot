# -*- mode: python; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_data_files,
    collect_submodules,
)

block_cipher = None

datas = [
    ('parrator/resources/icon.png', 'resources'),
    ('parrator/resources/icon.ico', 'resources'),
    ('parrator/resources/header_icon.jpg', 'resources'),
] + collect_data_files('onnx_asr')

binaries = collect_dynamic_libs('onnxruntime')

hiddenimports = [
    'onnxruntime.capi._pybind_state',
    'parrator',
    'parrator.__main__',
    'parrator.config',
    'parrator.gui_app',
    'parrator.tray_app',
    'parrator.audio_recorder',
    'parrator.transcriber',
    'parrator.hotkey_manager',
    'parrator.notifications',
    'parrator.startup',
    'parrator.wave_overlay',
    'parrator.text_postprocessor',
    'parrator.text_output',
    'parrator.win_utils',
    'parrator.model_presets',
] + collect_submodules('onnx_asr')

a = Analysis(
    ['parrator/__main__.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Parrator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    onefile=True,
    icon='parrator/resources/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='Parrator',
)

