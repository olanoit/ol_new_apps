# Correr el agente como Servicio de Windows (sin GUI, sin sesión de usuario)

Guía técnica para instalar `al_pos_local_agent.py` (el script, **no** la GUI) como un Servicio de
Windows real — mismo objetivo que [`GUIA_INSTALACION_TECNICO.md`](GUIA_INSTALACION_TECNICO.md)
(systemd) pero en Windows en vez de Raspberry Pi/Linux.

## Cuándo usar esta guía en vez de la GUI

[`GUIA_INSTALACION_WINDOWS.md`](GUIA_INSTALACION_WINDOWS.md) (el instalador `.exe` +
`al_pos_local_agent_gui.py`) alcanza para la mayoría de los locales y es más simple de instalar.
Esta guía es para cuando hace falta algo más robusto que eso:

| | GUI (`.exe` + inicio con Windows) | Servicio de Windows (esta guía) |
|---|---|---|
| Necesita una sesión de usuario con la sesión iniciada | Sí — si nadie inició sesión en Windows, el agente no arranca | No — arranca antes del login, y sigue corriendo si se cierra la sesión |
| Reinicio automático si el proceso se cae | No (hay que reabrir la ventana a mano) | Sí, configurable (equivalente a `Restart=always` de systemd) |
| Ventana visible en la PC | Sí (la GUI) | No — corre en segundo plano, se administra por consola/`services.msc` |
| Requiere instalar algo además del `.exe` propio | No | [NSSM](https://nssm.cc/) (herramienta externa, gratis, sin instalador — ver §3). Python **no** hace falta en la PC del local si se usa el `.exe` del servicio, ver §1. |
| Pensado para | Un técnico sin conocimientos de programación, PC con un usuario fijo que la deja siempre con sesión iniciada | Un kiosco/caja sin sesión interactiva permanente, o cuando se quiere el mismo nivel de confiabilidad que systemd en Linux |

Requiere: acceso de **administrador** en la PC Windows, y los mismos 3 datos que pide la guía GUI
(URL de Odoo, base de datos, canal del agente) si se va a usar el Camino B — ver
[`GUIA_INSTALACION_WINDOWS.md` §1](GUIA_INSTALACION_WINDOWS.md#1-qué-llevar--conseguir-antes-de-ir-al-local).

## 1. Conseguir el agente para esa PC

Dos formas — la primera es la recomendada, no necesita Python en la PC del local:

**Opción A (recomendada): el `.exe` ya armado**

Alguien con el código del proyecto lo genera una sola vez, de antemano, en una PC Windows de
desarrollo (**no** en la PC del local) — no hace falta saber Python para este paso, solo seguirlo
tal cual:

### Cómo generar el `.exe` con `build_service_exe.bat`

1. Tener **Python 3.11+ instalado** en esa PC de desarrollo (no en la del local) — si no lo tiene,
   descargarlo de [python.org/downloads](https://www.python.org/downloads/) y, en la primera
   pantalla del instalador, **tildar "Add python.exe to PATH"**.
2. Copiar la carpeta `agent/` completa del proyecto a esa PC (o tener el repo clonado ahí).
3. Doble clic en **`build_service_exe.bat`** (está dentro de `agent/`, al lado de
   `al_pos_local_agent.py`).
4. Se abre una ventana de consola sola y va mostrando el progreso:
   - Detecta el Python instalado.
   - Instala las dependencias del agente (`requirements.txt`) y PyInstaller, si hace falta.
   - Limpia una build anterior, si había.
   - Empaqueta el `.exe` con PyInstaller.
5. Al terminar, dice **"BUILD COMPLETADO"** y muestra la ruta exacta de la carpeta a copiar —
   siempre `agent\dist\AgenteEscposServicio\` (con `AgenteEscposServicio.exe`
   adentro, junto a sus dependencias empaquetadas).
6. Apretar una tecla para cerrar la ventana cuando termine.

Si algo falla en el medio (Python no encontrado, error instalando dependencias, error de
PyInstaller), la ventana lo dice en rojo/`[ERROR]` y queda abierta con `pause` — no hace falta
saber qué significa el error para reportarlo, alcanza con copiar el texto tal cual aparece.

Con el `.exe` ya generado: copiar la carpeta **completa** `AgenteEscposServicio\`
(no solo el `.exe` suelto — necesita los archivos que la acompañan) a la PC del local, por ejemplo
a `C:\al-pos-local-agent\AgenteEscposServicio\`.

Probar que arranca antes de seguir (`Ctrl+C` para cortar, es solo para confirmar que no tira un
error de entrada):

```powershell
cd C:\al-pos-local-agent\AgenteEscposServicio
$env:AL_AGENT_ALLOWED_PRINTERS = "192.168.0.252:9100"
.\AgenteEscposServicio.exe
```

Tiene que loguear una línea `Agente v<versión> escuchando en http://0.0.0.0:8765 — ...`. Si en vez
de eso tira un traceback, resolver eso antes de instalarlo como servicio — instalado como servicio
el error queda mucho más escondido.

**Opción B: correr el script directo con Python instalado en la PC del local**

Sirve igual de bien, pero requiere instalar Python ahí — útil si se prefiere no depender de un
`.exe` pre-armado, o para diagnosticar algo puntual editando el script directo sin tener que volver
a compilar.

```powershell
mkdir C:\al-pos-local-agent
cd C:\al-pos-local-agent
```

Copiar acá adentro `al_pos_local_agent.py` y `requirements.txt` (no hace falta nada más de la
carpeta `agent/`). Si la PC no tiene Python: descargar el instalador oficial desde
[python.org/downloads](https://www.python.org/downloads/) (3.11 o superior) y, en la primera
pantalla del instalador, **tildar "Add python.exe to PATH"** — sin eso, los comandos de abajo no
van a encontrar `python`.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:AL_AGENT_ALLOWED_PRINTERS = "192.168.0.252:9100"
.venv\Scripts\python.exe al_pos_local_agent.py
```

El resto de la guía usa los paths de la **Opción A** — con la Opción B, reemplazar
`AgenteEscposServicio.exe` por `.venv\Scripts\python.exe` (Path) + `al_pos_local_agent.py`
(Arguments) en el paso 3.

## 2. Descargar e instalar NSSM

Windows no tiene una forma nativa simple de correr un ejecutable/script propio como servicio real
que reaccione bien a "Detener" (a diferencia de systemd) — `sc.exe create` lo arranca, pero no
entiende el protocolo de control que espera el Administrador de Servicios de Windows. **NSSM**
(Non-Sucking Service Manager, [nssm.cc](https://nssm.cc/), gratis, sin instalador) resuelve justo
eso: envuelve cualquier ejecutable (acá, `AgenteEscposServicio.exe`, o `python.exe` si se
usó la Opción B) como un servicio real — es la herramienta estándar de facto para este caso, no
algo específico de este proyecto.

1. Descargar el `.zip` desde [nssm.cc/download](https://nssm.cc/download).
2. Extraerlo, y copiar `nssm.exe` de la carpeta `win64\` (o `win32\` si la PC es de 32 bits — poco
   común) a `C:\al-pos-local-agent\nssm.exe`, para tenerlo a mano.

## 3. Registrar el servicio

Desde PowerShell **como administrador**, dentro de `C:\al-pos-local-agent`:

```powershell
.\nssm.exe install AlPosLocalAgent
```

Esto abre una ventana de configuración (no hace falta más que esto para el resto de la guía; existe
también una forma 100% por línea de comandos con `nssm set`, pero para la primera instalación esta
ventana es más confiable que transcribir parámetros a mano). Completar:

**Pestaña "Application"** (Opción A, el `.exe` — para la Opción B ver la nota al final del §1):
- Path: `C:\al-pos-local-agent\AgenteEscposServicio\AgenteEscposServicio.exe`
- Startup directory: `C:\al-pos-local-agent\AgenteEscposServicio` (se completa solo al
  elegir el Path de arriba)
- Arguments: (vacío)

**Pestaña "Details"**:
- Display name: `Agente local ESC/POS`
- Startup type: `Automatic` (arranca solo al bootear, sin necesitar login)

**Pestaña "Environment"** (caja de texto multilínea, una variable `CLAVE=valor` por línea — mismo
contenido que [`al-pos-local-agent.service.example`](../al-pos-local-agent.service.example),
ver la tabla completa de variables en [`README.md`](../README.md#configuración-variables-de-entorno)):

```
AL_AGENT_ALLOWED_PRINTERS=192.168.0.252:9100
AL_AGENT_TOKEN=<generar uno largo, ver abajo>
```

Agregar, si Odoo está detrás de HTTPS (Odoo.sh u otro hosting con TLS — si no, omitir estas 2):

```
AL_AGENT_TLS_ENABLED=1
AL_AGENT_TLS_HOSTNAME=<hostname o IP de esta PC>
```

Y si el local usa el Camino B (comprobantes en PDF que imprime el backend de Odoo, publicados por
el bus — si no, omitir estas 3):

```
AL_AGENT_ODOO_URL=https://mi-instancia.odoo.com
AL_AGENT_ODOO_DB=mi_base
AL_AGENT_BUS_CHANNEL=<pos.config.escpos_agent_channel del TPV>
```

Para generar el token de la primera línea, en otra ventana de PowerShell:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

**Pestaña "I/O"** — para tener dónde mirar los logs, ya que no hay ventana de GUI que los muestre
(ver §6):
- Output (stdout): `C:\al-pos-local-agent\logs\agent-stdout.log`
- Error (stderr): `C:\al-pos-local-agent\logs\agent-stderr.log` (acá es donde realmente van a
  aparecer las líneas de log — el agente loguea por `stderr`, no por `stdout`)

**Pestaña "Exit actions"** — dejar el default ("Restart application") tal cual: es el equivalente a
`Restart=always` de systemd, reinicia solo el proceso si se cae.

Apretar **"Install service"**.

> Si en algún momento hay que cambiar algo de esto (agregar una variable, cambiar el token), no
> hace falta borrar y recrear el servicio — correr `.\nssm.exe edit AlPosLocalAgent` reabre la
> misma ventana con los valores actuales cargados.

## 4. Permitir el agente en el Firewall de Windows

Igual que con la GUI — la primera vez que el servicio arranca y empieza a escuchar en el puerto
8765, Windows puede mostrar el aviso **"Windows Defender Firewall bloqueó algunas características
de esta app"**, o directamente no mostrarlo (los servicios no siempre disparan el aviso interactivo
como una app de escritorio). Para no depender de que aparezca:

```powershell
New-NetFirewallRule -DisplayName "Agente ESC/POS" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
```

(Ejecutar también como administrador. Ajustar `8765` si se usó otro `AL_AGENT_LISTEN_PORT`.)

## 5. Arrancar el servicio y verificar

```powershell
Start-Service AlPosLocalAgent
Get-Service AlPosLocalAgent
```

Tiene que decir **Status: Running**. Confirmar que responde:

```powershell
curl http://localhost:8765/health
```

(o `Invoke-RestMethod http://localhost:8765/health` si `curl` no está disponible en esa PC —
Windows 10 desde la build 1803 en adelante ya trae `curl.exe`). Tiene que devolver algo como:

```json
{"status": "ok", "version": "1.0.0", "escpos_available": true, "allowed_printers": ["192.168.0.252:9100"]}
```

Si `escpos_available` dice `false`, revisar que el build (§1, Opción A) o el `pip install -r
requirements.txt` (§1, Opción B) hayan terminado sin errores.

## 6. Ver los logs

Como no hay ventana con log en vivo, tirar del archivo configurado en la pestaña "I/O" (§3):

```powershell
Get-Content C:\al-pos-local-agent\logs\agent-stderr.log -Wait -Tail 50
```

(`-Wait` es el equivalente a `tail -f`; `Ctrl+C` para cortar.) Buscar ahí la línea `Camino B
activo` o `Camino B inactivo` para confirmar si esa parte quedó bien conectada.

## 7. Prueba de punta a punta

Misma prueba que en la guía GUI — configurar `pos.config.escpos_agent_url`/`escpos_agent_token` en
Odoo apuntando a esta PC (ver
[`GUIA_INSTALACION_WINDOWS.md` §6](GUIA_INSTALACION_WINDOWS.md#6-habilitar-el-agente-en-odoo-para-que-el-ticket-normal-lo-use)),
recargar el POS, y hacer una venta de prueba confirmando que el ticket sale por la impresora física.

## 8. Actualizar el agente más adelante

```powershell
Stop-Service AlPosLocalAgent
```

Opción A (`.exe`): reemplazar la carpeta completa
`C:\al-pos-local-agent\AgenteEscposServicio\` por la carpeta `dist\AgenteEscposServicio\`
nueva (generada de nuevo con `build_service_exe.bat`). Opción B (script): reemplazar
`C:\al-pos-local-agent\al_pos_local_agent.py` por el archivo nuevo.

```powershell
Start-Service AlPosLocalAgent
curl http://localhost:8765/health   # confirmar que "version" cambió
```

## 9. Desinstalar

```powershell
Stop-Service AlPosLocalAgent
.\nssm.exe remove AlPosLocalAgent confirm
```

## 10. Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| `nssm.exe install` da "Access is denied" | La consola de PowerShell no está corriendo como administrador — cerrarla y volver a abrirla con "Ejecutar como administrador". |
| El servicio queda en estado "Stopped" apenas se arranca | Revisar `logs\agent-stderr.log` (§6) — casi siempre es una variable obligatoria faltante (`AL_AGENT_ALLOWED_PRINTERS`) o mal escrita en la pestaña Environment. |
| `Get-Service` no encuentra `AlPosLocalAgent` | El nombre del servicio en `nssm install` no coincidió, o el registro falló antes de terminar — repetir el paso 3. |
| `/health` no responde desde el navegador del cajero, pero sí desde la misma PC con `curl localhost` | Falta la regla de Firewall (§4) — es la causa más común. |
| `escpos_available: false` (Opción A, `.exe`) | El `.exe` se generó sin haber corrido `pip install -r requirements.txt` antes del build — volver a correr `build_service_exe.bat` (instala dependencias antes de empaquetar). |
| `escpos_available: false` (Opción B, script) | `pip install -r requirements.txt` no se corrió dentro del mismo `.venv` que usa el servicio — confirmar que el Path de la pestaña Application (§3) apunta a `.venv\Scripts\python.exe`, no a un Python del sistema. |
| Después de una actualización de Windows el servicio sigue "Automatic" pero no arrancó | Poco común, pero puede pasar si Windows Update reinició la PC antes de que la red estuviera lista — el servicio ya tiene `Restart on failure`, pero si nunca llegó a arrancar por falta de red, esperar 1-2 minutos y revisar `Get-Service` de nuevo; si sigue sin arrancar, `Start-Service AlPosLocalAgent` a mano. |

## Enlaces relacionados

- [`README.md`](../README.md#configuración-variables-de-entorno) — tabla completa de variables de
  entorno, con el detalle de cada una.
- [`GUIA_INSTALACION_TECNICO.md`](GUIA_INSTALACION_TECNICO.md) — el mismo enfoque (proceso headless,
  sin GUI, reinicio automático) pero en Raspberry Pi/Linux con systemd — mismo patrón, distinta
  herramienta de sistema operativo.
- [`GUIA_INSTALACION_WINDOWS.md`](GUIA_INSTALACION_WINDOWS.md) — la alternativa con GUI de
  escritorio, más simple de instalar pero que necesita una sesión de Windows con login iniciado.
