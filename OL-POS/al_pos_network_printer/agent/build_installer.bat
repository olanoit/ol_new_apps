@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: Re-lanzar en ventana persistente si se ejecuto con doble-click
if /i "%~1"=="--run" goto :run
start "Build Agente ESC/POS" cmd /k ""%~f0" --run"
exit /b 0

:run
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo.
echo  ================================================
echo   Build — Agente ESC/POS Installer
echo  ================================================
echo.

:: ── 1. Verificar Python ─────────────────────────────────────
set "PYTHON="
for /f "usebackq delims=" %%P in (`where python 2^>nul`) do (
    if not defined PYTHON (
        echo "%%P" | findstr /i "WindowsApps" >nul 2>&1
        if !ERRORLEVEL! neq 0 set "PYTHON=%%P"
    )
)
if not defined PYTHON (
    echo [ERROR] Python no encontrado en PATH.
    pause & exit /b 1
)
echo  [OK] Python: %PYTHON%

:: ── 2. Instalar dependencias del agente + PyInstaller ───────
echo.
echo  Instalando dependencias (requirements.txt + requirements-gui.txt)...
"%PYTHON%" -m pip install -r requirements.txt -r requirements-gui.txt --quiet
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se pudieron instalar las dependencias del agente.
    pause & exit /b 1
)
"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  Instalando PyInstaller...
    "%PYTHON%" -m pip install pyinstaller --quiet
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo instalar PyInstaller.
        pause & exit /b 1
    )
)
echo  [OK] Dependencias y PyInstaller disponibles.

:: ── 3. Limpiar builds anteriores ────────────────────────────
echo.
echo  Limpiando builds anteriores...
if exist dist   rmdir /s /q dist
if exist build  rmdir /s /q build
if exist Output rmdir /s /q Output

:: ── 4. Empaquetar con PyInstaller ───────────────────────────
echo.
echo  [1/2] Empaquetando con PyInstaller...
echo.
"%PYTHON%" -m PyInstaller AgenteEscpos.spec
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller fallo. Revisa los mensajes arriba.
    pause & exit /b 1
)

if not exist "dist\AgenteEscpos\AgenteEscpos.exe" (
    echo [ERROR] El .exe no se genero en dist\AgenteEscpos\
    pause & exit /b 1
)
echo.
echo  [OK] .exe generado en dist\AgenteEscpos\AgenteEscpos.exe

:: ── 5. Compilar instalador con Inno Setup ───────────────────
echo.
echo  [2/2] Compilando instalador con Inno Setup...
echo.

set "ISCC="
for %%I in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
) do (
    if not defined ISCC (
        if exist %%I set "ISCC=%%~I"
    )
)

if not defined ISCC (
    echo [WARN] Inno Setup no encontrado. Solo se genero el .exe en dist\
    echo.
    echo  Para crear el instalador descarga Inno Setup 6 desde:
    echo    https://jrsoftware.org/isdownload.php
    echo  Luego ejecuta:
    echo    ISCC.exe "%SCRIPT_DIR%installer.iss"
    echo.
    echo  El .exe standalone esta disponible en:
    echo    %SCRIPT_DIR%dist\AgenteEscpos\AgenteEscpos.exe
    pause & exit /b 0
)

echo  [OK] Inno Setup encontrado: %ISCC%
"%ISCC%" installer.iss
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Inno Setup fallo. Revisa los mensajes arriba.
    pause & exit /b 1
)

:: ── 6. Resultado ─────────────────────────────────────────────
echo.
echo  ================================================
echo   BUILD COMPLETADO
echo  ================================================
echo.
echo  Instalador: %SCRIPT_DIR%Output\AgenteEscpos_Setup_1.0.0.exe
echo  Standalone: %SCRIPT_DIR%dist\AgenteEscpos\AgenteEscpos.exe
echo.
echo  Puedes cerrar esta ventana.

endlocal
