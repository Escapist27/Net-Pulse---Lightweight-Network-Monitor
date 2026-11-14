# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec для NetPulse (Windows). Запуск: pyinstaller windows\netpulse.spec
import os
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(ROOT, "assets", "netpulse.ico")

a = Analysis(
    [os.path.join(ROOT, "netpulse.py")],
    pathex=[ROOT],
    datas=collect_data_files("customtkinter") + [(ICON, ".")],
    hiddenimports=[],
    excludes=["numpy", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NetPulse",
    icon=ICON,
    version=os.path.join(SPECPATH, "version_info.txt"),
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="NetPulse", upx=False)
