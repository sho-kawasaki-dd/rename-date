import os
from pathlib import Path

import tkinterdnd2


project_root = Path(SPECPATH).resolve().parent
src_root = project_root / "src"
tkdnd_root = os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd")
icon_path = project_root / "installer" / "assets" / "app.ico"
icon = str(icon_path) if os.path.exists(icon_path) else None


a = Analysis(
	[str(project_root / "main.py")],
	pathex=[str(src_root)],
	binaries=[],
	datas=[(tkdnd_root, "tkinterdnd2/tkdnd")],
	hiddenimports=[],
	hookspath=[],
	hooksconfig={},
	runtime_hooks=[],
	excludes=[],
	noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
	pyz,
	a.scripts,
	exclude_binaries=True,
	name="rename-date",
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=True,
	console=False,
	icon=icon,
)
coll = COLLECT(
	exe,
	a.binaries,
	a.datas,
	strip=False,
	upx=True,
	upx_exclude=[],
	name="rename-date",
)