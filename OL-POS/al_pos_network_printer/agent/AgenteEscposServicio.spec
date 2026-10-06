# -*- mode: python ; coding: utf-8 -*-
# AgenteEscposServicio.spec — Configuración PyInstaller para empaquetar
# al_pos_local_agent.py (el agente SIN GUI) como .exe standalone, pensado
# para envolverlo con NSSM como Servicio de Windows — ver
# docs/GUIA_SERVICIO_WINDOWS.md. Con este .exe, la PC del local no necesita
# tener Python instalado (a diferencia de correr `python al_pos_local_agent.py`
# directo dentro de un venv).
#
# Mismo patrón que AgenteEscpos.spec (la GUI) pero:
# - Entry point al_pos_local_agent.py en vez de al_pos_local_agent_gui.py
#   — no hay GUI que envolver, así que no hace falta el hiddenimport del
#   propio 'al_pos_local_agent' (acá SÍ es el script de entrada) ni 'yaml'
#   (solo lo usa la GUI para persistir agent_gui_config.yaml — el CLI se
#   configura por variables de entorno, ver requirements.txt sin PyYAML).
# - console=True (a propósito, no es un descuido): el agente loguea por
#   stderr vía logging.basicConfig() sin stream= explícito — con
#   console=False (subsistema windowed) sys.stderr puede ser None en un
#   .exe empaquetado (mismo problema que _setup_logging() de
#   al_pos_local_agent_gui.py workarounds explícitamente), y NSSM
#   necesita un stderr real para poder redirigirlo a un archivo de log
#   (AppStderr, ver la guía). Un proceso console=True corriendo como
#   Servicio de Windows NO muestra ninguna ventana (los servicios corren en
#   la sesión 0, sin escritorio interactivo) — este flag es sobre el
#   subsistema del binario, no sobre si se ve una ventana.
# - Sin 'PIL._tkinter_finder' (no hay Tkinter acá) ni 'tkinter' (excluido
#   explícitamente, ver excludes) — reduce el tamaño del build.
#
# Ejecutar con:  pyinstaller AgenteEscposServicio.spec

block_cipher = None

a = Analysis(
    ['al_pos_local_agent.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Camino A (siempre activo)
        'escpos.printer',
        # Camino B (opcional en tiempo de ejecución — el agente arranca
        # igual sin esto, ver los try/except ImportError en
        # al_pos_local_agent.py — pero si no se empaquetan, ese camino
        # queda inutilizable en el .exe aunque se configuren las variables
        # MBLZ_AGENT_ODOO_URL/_ODOO_DB/_BUS_CHANNEL).
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
        # excluir módulos no usados para reducir tamaño — sin GUI, sin
        # ventanas, así que tkinter tampoco hace falta acá (a diferencia de
        # AgenteEscpos.spec).
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'unittest',
        'tkinter',
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
    name='AgenteEscposServicio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,            # con consola a propósito, ver docstring arriba
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
    name='AgenteEscposServicio',
)
