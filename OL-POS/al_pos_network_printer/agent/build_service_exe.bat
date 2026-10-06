@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: Re-lanzar en ventana persistente si se ejecuto con doble-click
if /i "%~1"=="--run" goto :run
start "Build Agente ESC/POS - Servicio" cmd /k ""%~f0" --run"
exit /b 0

:run
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo.
echo  ================================================
echo   Build - Agente ESC/POS (Servicio, sin GUI)
echo  ================================================
echo.
echo  Genera AgenteEscposServicio.exe a partir de al_pos_local_agent.py
echo  (sin la GUI) - pensado para envolver con NSSM como Servicio de Windows.
echo  Ver docs\GUIA_SERVICIO_WINDOWS.md para instalarlo una vez generado.
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
:: Solo requirements.txt (el CLI no usa PyYAML - eso es exclusivo de la GUI,
:: ver requirements-gui.txt).
echo.
echo  Instalando dependencias (requirements.txt)...
"%PYTHON%" -m pip install -r requirements.txt --quiet
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
if exist "dist\AgenteEscposServicio"  rmdir /s /q "dist\AgenteEscposServicio"
if exist "build\AgenteEscposServicio" rmdir /s /q "build\AgenteEscposServicio"

:: ── 4. Empaquetar con PyInstaller ───────────────────────────
echo.
echo  Empaquetando con PyInstaller...
echo.
"%PYTHON%" -m PyInstaller AgenteEscposServicio.spec
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller fallo. Revisa los mensajes arriba.
    pause & exit /b 1
)

if not exist "dist\AgenteEscposServicio\AgenteEscposServicio.exe" (
    echo [ERROR] El .exe no se genero en dist\AgenteEscposServicio\
    pause & exit /b 1
)

:: ── 5. Resultado ─────────────────────────────────────────────
echo.
echo  ================================================
echo   BUILD COMPLETADO
echo  ================================================
echo.
echo  Carpeta a copiar a la PC del local (completa, no solo el .exe):
echo    %SCRIPT_DIR%dist\AgenteEscposServicio\
echo.
echo  En esa PC, seguir desde el paso 3 de docs\GUIA_SERVICIO_WINDOWS.md
echo  (registrar el servicio con NSSM apuntando a AgenteEscposServicio.exe)
echo  - no hace falta instalar Python ahi.
echo.
echo  Puedes cerrar esta ventana.

endlocal
