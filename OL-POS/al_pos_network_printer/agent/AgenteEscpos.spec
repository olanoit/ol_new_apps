# -*- mode: python ; coding: utf-8 -*-
# AgenteEscpos.spec — Configuración PyInstaller para el Agente ESC/POS
# Ejecutar con:  pyinstaller AgenteEscpos.spec

block_cipher = None

a = Analysis(
    ['al_pos_local_agent_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # al_pos_local_agent.py no es un paquete instalado — vive en esta
        # misma carpeta y se importa por `sys.path.insert()` en el propio
        # script. El análisis estático de PyInstaller normalmente lo
        # detecta solo (mismo directorio que el script de entrada), pero
        # se deja explícito acá para que un futuro rename no lo pierda en
        # silencio.
        'al_pos_local_agent',
        'yaml',
        # Camino A (siempre activo)
        'escpos.printer',
        'PIL._tkinter_finder',
        # Camino B (opcional en tiempo de ejecución — el agente arranca
        # igual sin esto, ver los try/except ImportError en
        # al_pos_local_agent.py — pero si no se empaquetan, ese camino
        # queda inutilizable en el .exe aunque el usuario configure la
        # URL/DB/canal de Odoo).
        'requests',
        'websocket',
        'pymupdf',
        'fitz',
        # HTTPS del Camino A (opcional en tiempo de ejecución, mismo criterio
        # que el bloque de arriba — ver el import de `cryptography` en
        # al_pos_local_agent.py). `cryptography` trae un módulo en C
        # (`cryptography.hazmat.bindings._rust`) que el análisis estático de
        # PyInstaller no siempre detecta solo.
        'cryptography',
        'cryptography.hazmat.bindings._rust',
        'cryptography.hazmat.backends.openssl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # excluir módulos no usados para reducir tamaño
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AgenteEscpos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # sin ventana de consola (app GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # descomentar si se agrega un ícono .ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AgenteEscpos',
)
