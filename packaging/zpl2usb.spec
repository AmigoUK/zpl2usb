# PyInstaller spec dla zpl2usb — buduje samodzielną binarkę GUI.
#
# Użycie (z katalogu głównego repo, w aktywnym venv z zainstalowanym pyinstaller):
#   pyinstaller packaging/zpl2usb.spec
#
# Wynik: dist/zpl2usb (Linux/macOS) lub dist/zpl2usb.exe (Windows).

import sys

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# python-barcode dostarcza plik fontu jako dane pakietu — trzeba go dołączyć.
for pkg in ("barcode", "pystray", "PIL", "qrcode", "psutil"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

block_cipher = None

a = Analysis(
    ["../main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name="zpl2usb",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # aplikacja GUI — bez okna konsoli
    disable_windowed_traceback=False,
)

# Na macOS pakujemy dodatkowo w .app (klikalne w Finderze, przyjazne Gatekeeperowi).
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="zpl2usb.app",
        icon=None,
        bundle_identifier="com.zpl2usb",
        info_plist={"LSUIElement": True},  # aplikacja w tle (tray), bez ikony w Docku
    )
