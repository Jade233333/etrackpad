# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['trackpad_emulator.py'],
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
    [],
    exclude_binaries=True,
    name='trackpad_emulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='trackpad_emulator',
)
