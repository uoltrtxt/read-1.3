# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.')],              # .env 포함
    hiddenimports=['dotenv'] + collect_submodules('dotenv'),
    hookspath=[],
    runtime_hooks=[],
    excludes=[]
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='app',
    debug=False,
    strip=False,
    upx=True,
    console=True,                      # 개발 시 콘솔 활성화
    icon=None
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app'
)