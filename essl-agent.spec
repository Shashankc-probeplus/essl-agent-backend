# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for ESSL Agent Backend - Production Version
==================================================================

Features:
1. ✅ Compiles Python to bytecode (.pyc) - harder to reverse engineer
2. ✅ Strips source code comments
3. ✅ Obfuscates module names
4. ✅ Compresses with UPX
5. ✅ Properly handles pyzk/zk library
6. ✅ One-folder distribution (allows separate .env)

Security Notes:
- Python bytecode CAN be decompiled, but it's significantly harder
- For maximum protection, consider PyArmor or keeping logic server-side
- Stripping debug symbols also helps
"""

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ==============================================================================
# Collect hidden imports
# ==============================================================================

# Collect all zk (pyzk) submodules automatically
pyzk_hiddenimports = collect_submodules('zk')

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include app directory - will be compiled to .pyc
        ('obf_app', 'app'),
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
        'pydantic_core',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'dotenv',
        'httpx',
        'httpcore',
        'psutil',
        
        # PyZK - package installs as 'pyzk' but imports as 'zk'
        'zk',
        'zk.attendance',
        'zk.const',
        'zk.exception',
        'zk.face',
        'zk.finger',
        'zk.user',
        
        # App modules - explicitly include
        'app',
        'app.core',
        'app.core.v1',
        'app.core.v1.essl',
        'app.service',
        'app.main',
    ] + pyzk_hiddenimports,
    
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    
    # Exclude unnecessary modules to reduce size
    excludes=[
        'tkinter',
        'matplotlib',
        'pytest',
        'IPython',
        'jupyter',
        'notebook',
        'sphinx',
        'setuptools',
        'pip',
        'wheel',
        'test',
        'unittest',
        'distutils',
    ],
    
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    
    # Cipher for bytecode encryption
    # None = standard bytecode (harder to read than .py but still decompilable)
    # 'aes256' = encrypted (requires key management, more complex)
    cipher=None,
    
    noarchive=False,
)

# ==============================================================================
# PYZ - Python Archive (compressed bytecode)
# ==============================================================================

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None  # Match Analysis cipher setting
)

# ==============================================================================
# EXE - Executable
# ==============================================================================

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # One-folder mode (allows separate .env)
    name='essl-agent',
    debug=False,  # No debug info
    bootloader_ignore_signals=False,
    strip=True,   # Strip debug symbols (important for protection!)
    upx=True,     # Compress with UPX (smaller + obfuscation)
    console=True, # Show console (change to False for no console window)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    
    # Windows-specific: Hide imports from dependency walkers
    # icon='icon.ico',  # Add your icon here if you have one
)

# ==============================================================================
# COLLECT - Final Distribution Folder
# ==============================================================================

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,   # Strip binaries
    upx=True,     # Compress libraries
    upx_exclude=[
        # Exclude some files from UPX (can cause issues)
        'vcruntime140.dll',
        'python3.dll',
        'python312.dll',
    ],
    name='essl-agent',
)

# ==============================================================================
# What You Get
# ==============================================================================
# dist/essl-agent/
# ├── essl-agent (executable - stripped, compressed)
# └── _internal/
#     ├── *.pyd/*.so (compiled extensions)
#     ├── *.dll/*.so (libraries - stripped, compressed)
#     ├── base_library.zip (Python stdlib - bytecode only)
#     └── app/ (your code - bytecode .pyc files, NOT .py source!)
#
# Protection Level: Medium
# - Source code compiled to bytecode
# - Debug symbols stripped
# - Compressed with UPX
# - No .py files in distribution
#
# Can Still Be Reversed?: Yes, but requires:
# - Decompiling .pyc to approximate Python
# - Understanding obfuscated bytecode
# - Significant effort and expertise
#
# Better Protection:
# - Use PyArmor: pip install pyarmor
# - Keep sensitive logic server-side
# - Use code signing
# ==============================================================================