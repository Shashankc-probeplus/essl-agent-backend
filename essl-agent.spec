# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for ESSL Agent Backend
Updated to properly handle pyzk library
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all pyzk submodules
pyzk_hiddenimports = collect_submodules('zk')

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app', 'app'),
        ('data.json', '.'),
        ('.env.template', '.'),
    ],
    hiddenimports=[
        # Uvicorn imports
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # FastAPI and dependencies
        'fastapi',
        'pydantic',
        'starlette',
        'dotenv',
        'httpx',
        'httpcore',
        'psutil',
        # PyZK - the package is imported as 'zk' not 'pyzk'
        'zk',
        'zk.attendance',
        'zk.const',
        'zk.exception',
        'zk.face',
        'zk.finger',
        'zk.user',
        # App modules
        'app.core',
        'app.core.v1',
        'app.core.v1.essl',
        'app.service',
    ] + pyzk_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pytest',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='essl-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='essl-agent',
)
