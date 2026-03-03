# -*- mode: python; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import (
        collect_dynamic_libs,
        collect_data_files,
)

block_cipher = None

# Data files: (source, destination_folder)
datas = [
    ('vocab.txt', '.'),
    ('decoder_joint-model.onnx', '.'),
    ('encoder-model.onnx', '.'),
    ('parrator/resources/icon.png', 'resources'),
    ('parrator/resources/icon.ico', 'resources'),
] + collect_data_files('onnx_asr')

# Binaries: dynamic libs from onnxruntime
binaries = collect_dynamic_libs('onnxruntime')

a = Analysis(
    ['parrator/__main__.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=['onnxruntime.capi._pybind_state'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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

