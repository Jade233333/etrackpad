# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['etrackpad.py'],
    pathex=[],
    binaries=[("/home/Jade/Developer/trackpad_emulator/.venv_3.10.16/lib/python3.10/site-packages/_libsuinput.cpython-310-x86_64-linux-gnu.so",".")],
    datas=[],
    hiddenimports=[],
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
    a.binaries,  # Ensure needed libraries are included
    a.zipfiles,
    a.datas,
    name='etrackpad',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    singlefile=True  # This ensures it's a single file
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='etrackpad',
)
