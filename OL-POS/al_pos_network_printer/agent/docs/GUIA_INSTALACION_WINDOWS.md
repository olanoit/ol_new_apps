# Instalar el agente en una PC Windows del local — guía para el técnico

Esta guía es para la persona que va a dejar el agente instalado y funcionando en una PC Windows
del local — **no hace falta saber programar ni Python**, todo se hace con la GUI de escritorio. Si
algo de acá no queda claro o el resultado no coincide con lo esperado, mejor frenar y consultar
antes de seguir, que forzar el paso siguiente.

Si en cambio el local usa una Raspberry Pi/Linux sin pantalla (lo más común para un agente que
queda siempre encendido), ver [`GUIA_INSTALACION_TECNICO.md`](GUIA_INSTALACION_TECNICO.md) — esta
guía es específica para Windows con la GUI de escritorio.

Si la PC Windows es un kiosco/caja sin sesión de usuario permanente, o se necesita que el agente
arranque antes del login y se reinicie solo si se cae (sin depender de que alguien haya iniciado
sesión), ver en cambio [`GUIA_SERVICIO_WINDOWS.md`](GUIA_SERVICIO_WINDOWS.md) — instala
`al_pos_local_agent.py` como Servicio de Windows real, sin GUI.

## ¿Cuándo hace falta esto?

Solo si el servidor de Odoo **no está en la misma red que la impresora** del local (por ejemplo,
Odoo corriendo en Odoo.sh, en la nube). Si el servidor de Odoo está en una máquina dentro del mismo
local (como en la mayoría de las instalaciones actuales), **no hace falta nada de esto** — la
impresora ya funciona directo, sin agente.

## 1. Qué llevar / conseguir antes de ir al local

- El instalador **`AgenteEscpos_Setup_<versión>.exe`** — lo arma el equipo de desarrollo con
  `build_installer.bat` (ver más abajo si sos vos quien lo tiene que generar) y te lo pasa por USB
  o descarga. No hace falta Python ni nada más instalado de antemano en la PC del local: el `.exe`
  ya trae todo empaquetado.
- Una PC Windows 10 (64 bits) o superior del local que se pueda dejar **siempre prendida** —
  no hace falta que sea potente, el agente usa muy pocos recursos. Evitar una notebook que se
  suspenda/apague sola: mientras esté apagada o dormida, el ticket no va a salir por ningún lado.
- Acceso de **administrador** en esa PC (el instalador lo pide por Windows — ver paso 2).
- **3 datos que tiene que pasar el administrador de Odoo** (pedirlos ANTES de ir, por escrito, no
  a memoria):
  1. La **URL de la instancia de Odoo** (ej. `https://mi-farmacia.odoo.com`).
  2. El **nombre de la base de datos** (ej. `mi_farmacia`).
  3. El **canal del agente** — un texto largo de letras y números que el administrador copia desde
     **Ajustes → Punto de Venta → (el punto de venta) → sección "ePos Printer" → campo "Canal del
     agente local (bus, Camino B)"**. Tratarlo como una contraseña — no compartirlo por ningún
     medio inseguro.
  4. La **IP de la impresora** en la red del local (normalmente ya la tiene el que instaló la
     impresora — si no, ver el manual de la impresora para imprimir un "self-test"/"test de red",
     que suele mostrar la IP asignada).

### Cómo generar el instalador con `build_installer.bat`

Esto lo hace una sola vez, de antemano, quien tenga el código del proyecto, en una PC Windows de
desarrollo (**no** en la PC del local) — no hace falta saber Python para este paso, solo seguirlo
tal cual:

1. Tener **Python 3.11+ instalado** en esa PC de desarrollo — si no lo tiene, descargarlo de
   [python.org/downloads](https://www.python.org/downloads/) y, en la primera pantalla del
   instalador, **tildar "Add python.exe to PATH"**.
2. (Opcional, pero recomendado) Instalar **Inno Setup 6** desde
   [jrsoftware.org/isdownload.php](https://jrsoftware.org/isdownload.php) — es lo que arma el
   instalador final (`_Setup_<versión>.exe`) con el asistente en español, accesos directos e
   inicio automático. Sin esto el script igual genera un `.exe` standalone funcional (ver paso 5),
   solo que sin ese asistente de instalación.
3. Copiar la carpeta `agent/` completa del proyecto a esa PC (o tener el repo clonado ahí).
4. Doble clic en **`build_installer.bat`** (está dentro de `agent/`, al lado de
   `al_pos_local_agent_gui.py`).
5. Se abre una ventana de consola sola y va mostrando el progreso:
   - Detecta el Python instalado.
   - Instala las dependencias del agente y de la GUI (`requirements.txt` +
     `requirements-gui.txt`) y PyInstaller, si hace falta.
   - Limpia una build anterior, si había.
   - Empaqueta el `.exe` con PyInstaller.
   - Busca Inno Setup y, si lo encuentra, compila el instalador final; si no lo encuentra, avisa
     con `[WARN]` y sigue — el `.exe` standalone queda igual disponible, solo falta el instalador.
6. Al terminar, muestra las 2 rutas posibles:
   - Instalador: `agent\Output\AgenteEscpos_Setup_<versión>.exe` — **este es el archivo
     que hay que llevar al local** (paso 1 de esta guía).
   - Standalone: `agent\dist\AgenteEscpos\AgenteEscpos.exe` — sirve para probar
     rápido en la misma PC de desarrollo, pero no instala accesos directos ni inicio automático.
7. Apretar una tecla para cerrar la ventana cuando termine.

Si algo falla en el medio (Python no encontrado, error instalando dependencias, error de
PyInstaller o de Inno Setup), la ventana lo dice en rojo/`[ERROR]` y queda abierta con `pause` —
no hace falta saber qué significa el error para reportarlo, alcanza con copiar el texto tal cual
aparece.

## 2. Instalar el agente

1. Copiar `AgenteEscpos_Setup_<versión>.exe` a la PC Windows (USB, descarga, etc.).
2. Doble clic en el instalador. Windows puede mostrar **"El editor no se pudo verificar" / Windows
   protegió su PC** (SmartScreen — normal para un instalador interno, sin firma de código
   comprada): hacer clic en **"Más información"** y después **"Ejecutar de todas formas"**.
3. Windows va a pedir permiso de administrador (UAC) — aceptar. El instalador lo necesita para
   instalar en `Archivos de programa` y crear el servicio de inicio automático.
4. Seguir el asistente:
   - Idioma: viene en español por defecto.
   - Tareas opcionales: marcar **"Crear acceso directo en el Escritorio"** si se quiere, y
     **"Iniciar automáticamente con Windows"** — esta segunda es la importante: sin ella, si la PC
     se reinicia (corte de luz, Windows Update), el agente no vuelve a arrancar solo y hay que
     abrirlo a mano.
   - Instalar. Al terminar, deja tildado **"Iniciar Agente ESC/POS ahora"** — dejarlo así.
5. Se abre la ventana **"Agente ESC/POS — Odoo 19"** (el número de versión aparece en el
   encabezado, ej. `v1.0.0` — sirve para confirmar más adelante qué build quedó instalada, ver
   §7).

## 3. Permitir el agente en el Firewall de Windows

La primera vez que se aprieta **"▶ Iniciar"** (paso 5), Windows casi siempre muestra un aviso
**"Windows Defender Firewall bloqueó algunas características de esta app"**. Es esperado — el
agente necesita escuchar conexiones de red (del navegador del cajero) para poder imprimir.

- Tildar **"Redes privadas"** (la red del local debería estar marcada como tal; si el local usa
  una red "Pública" en Windows, marcar esa también).
- Apretar **"Permitir acceso"**.

Si este aviso se cerró sin querer o no apareció, y más adelante el agente no recibe nada desde el
POS aunque diga "Activo": revisar manualmente en **Configuración de Windows → Privacidad y
seguridad → Firewall de Windows Defender → Permitir una app a través del firewall** que
`AgenteEscpos.exe` esté permitido para redes privadas.

## 4. Completar la pestaña ⚙ Configuración

En la ventana del agente, pestaña **⚙ Configuración**:

| Sección | Campo | Qué poner |
|---|---|---|
| 🖨 Servidor del agente | Impresoras permitidas | `IP_DE_LA_IMPRESORA:9100` (el puerto casi siempre es `9100`; separar con coma si hay más de una) |
| | Interfaz de escucha | `0.0.0.0` (default, no tocar) |
| | Puerto del agente | `8765` (default, no tocar salvo que ese puerto ya esté ocupado en esa PC) |
| | Token compartido | Apretar **"Generar"** y copiar el valor — se va a pegar en Odoo en el paso 6 |
| | CORS origin | `*` (default, alcanza salvo que se quiera acotar al dominio exacto de Odoo) |
| 🔒 Seguridad (HTTPS) | Habilitar HTTPS | Marcar **solo si** Odoo está detrás de HTTPS (Odoo.sh u otro hosting con TLS) — ver aviso abajo |
| | Hostname / IP del certificado | El mismo host que se va a poner en "URL del agente local" en Odoo (sin `https://` ni puerto) |
| 🔄 Conexión con Odoo | URL de Odoo | La URL que pasó el administrador (paso 1) |
| | Base de datos | El nombre de base que pasó el administrador |
| | Canal del agente | El canal que pasó el administrador — **pegar tal cual, no apretar "Generar" acá** (ese botón es solo para el Token de arriba) |
| | Ruta del ACK | Dejar vacía (ACK desactivado), salvo que el módulo de Odoo que publique los comprobantes indique una ruta |
| 📋 Registro | Nivel de log | `INFO` (default — usar `DEBUG` solo si hay que diagnosticar algo puntual) |

> **¿Cuándo hace falta HTTPS?** Si Odoo es `https://...` (Odoo.sh siempre lo es), el navegador del
> cajero bloquea el ticket con "Mixed Content" al intentar hablarle a un agente por HTTP plano —
> no es un error de configuración, es el navegador cortando la petición antes de que salga. Con
> "Habilitar HTTPS" marcado, la primera vez hay que abrir `https://<host>:<puerto>/health` en el
> navegador del cajero y aceptar la advertencia de seguridad del certificado autofirmado (una sola
> vez por navegador). Si esto da problemas persistentes, ver
> [`GUIA_CLOUDFLARE_TUNNEL.md`](GUIA_CLOUDFLARE_TUNNEL.md) — evita el certificado autofirmado de
> raíz con un dominio público real.

Apretar **"Guardar configuración"**.

## 5. Iniciar el agente y probar la conexión

1. Volver a la pestaña **🖨 Agente** y apretar **"▶ Iniciar"**.
2. El indicador del encabezado (círculo de color, arriba a la derecha) tiene que pasar de
   "Detenido" (rojo) a activo. El log de la pestaña Agente tiene que decir algo como "Agente
   iniciado...".
3. Si se completó la sección "Conexión con Odoo" (paso 4), en unos segundos el indicador **"Camino
   B"** del encabezado se pone verde ("Camino B: conectado"). Si se queda en "Camino B: inactivo"
   más de medio minuto, revisar que URL de Odoo/Base de datos/Canal estén bien copiados (sin
   espacios de más).
4. Usar **"Test de conexión"** para confirmar que tanto la impresora configurada como el servidor
   de Odoo responden, sin necesitar una venta real todavía.

## 6. Habilitar el agente en Odoo (para que el ticket normal lo use)

El campo **"Método de impresión"** (`pos.config.escpos_printer_mode`) es el único que decide si el
ticket pasa por el agente o va directo al backend — con "Backend de Odoo (por defecto)" el resto de
los campos de abajo pueden estar completos sin que cambie nada, así que conviene dejarlos cargados
siempre y usar este selector nada más para alternar.

1. En Odoo: **Ajustes → Punto de Venta → (el punto de venta) → Dispositivos conectados**.
2. **"URL del agente local ESC/POS (opcional)"**: `http://<IP-de-la-PC-Windows>:8765` (o
   `https://<hostname>:8765` si se activó HTTPS en el paso 4) — la IP de la PC donde se instaló el
   agente. Para verla en esa PC: `ipconfig` en una consola, o **Configuración → Red e Internet →
   Wi-Fi/Ethernet → Propiedades**.
3. **"Token del agente local ESC/POS"**: pegar el mismo token generado en el paso 4.
4. **"Método de impresión"**: cambiar a **"Agente local"**.
5. Guardar.
6. **Recargar (F5) la pestaña del POS**, si ya estaba abierta desde antes — ver aviso abajo.

> **⚠️ Ojo con esto**: el objeto impresora del navegador se arma una sola vez al cargar la pestaña
> del POS. Si se cambia "Método de impresión" con una pestaña del POS ya abierta desde antes, esa
> pestaña sigue usando el modo viejo hasta que se recargue — el síntoma es que **el ticket no sale
> por ningún lado y el agente no muestra ningún movimiento en su log**, como si el cambio no
> hubiera hecho nada. No es que no funcionó: hace falta F5 (o cerrar la pestaña y volver a entrar)
> después de guardar el cambio.

**Para volver al comportamiento normal** alcanza con volver "Método de impresión" a "Backend de
Odoo (por defecto)" y guardar — no hace falta tocar ni vaciar la URL/token/canal, pero igual hay
que recargar la pestaña del POS para que el cambio se aplique ahí.

## 7. Prueba de punta a punta

1. Abrir el POS en el navegador, hacer una venta de prueba y confirmar boleta — el ticket tiene que
   salir por la impresora física, y el log de la pestaña Agente tiene que mostrar el trabajo
   procesado.
2. Si el local usa el Camino B (algún módulo de Odoo publica comprobantes en PDF por el bus):
   generar uno de esos comprobantes y confirmar que también sale — llega por el bus, no por el
   mismo camino que el ticket.
3. Revisar la pestaña **📋 Registros** si algo no salió — tiene el detalle completo de ambos
   caminos.
4. Confirmar la versión instalada si hace falta reportar un problema: aparece en el encabezado de
   la ventana, o corriendo `AgenteEscpos.exe --version` desde una consola en la carpeta de
   instalación (por defecto `C:\Program Files\Agente ESC/POS\`).

## 8. Qué pasa si se reinicia la PC o se corta la luz

- Si se marcó **"Iniciar automáticamente con Windows"** en la instalación (paso 2): el agente
  vuelve a abrirse solo al iniciar sesión en Windows, pero **la GUI abre con el agente detenido**
  — hay que apretar "▶ Iniciar" a mano cada vez, salvo que se haya guardado la configuración con
  todo completo (ahí queda listo para apretar Iniciar de nuevo, no hace falta recompletar nada).
- Si no se marcó esa opción: después de un reinicio el agente no vuelve a arrancar hasta que
  alguien abra "Agente ESC/POS" a mano desde el escritorio o el menú inicio.
- La reconexión a Odoo (Camino B) es automática una vez que el agente está iniciado — no hace
  falta tocar nada si se cortó la luz/internet y volvió, el agente reintenta solo.

## 9. Actualizar el agente más adelante

1. Cerrar la GUI si está abierta (o dejarla — el instalador la cierra solo, ver
   `CloseApplicationsFilter` en `installer.iss`).
2. Correr el `Setup.exe` de la versión nueva — reinstala encima, sin pedir desinstalar antes.
3. Abrir el agente y confirmar en el encabezado que la versión cambió antes de dar por terminada la
   actualización.

La configuración guardada (`agent_gui_config.yaml`, dentro de la carpeta de instalación) **no se
borra** al actualizar — solo se pierde si se marca esa opción explícitamente al desinstalar (ver
`installer.iss`).

## 10. Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| Windows bloqueó el instalador ("El editor no se pudo verificar") | Normal para un instalador interno sin firma comprada — "Más información" → "Ejecutar de todas formas". Si el antivirus del local lo pone en cuarentena, agregar una excepción para `AgenteEscpos.exe` (pedirle esto al administrador de IT del local si no se tiene permiso). |
| El agente dice "Activo" pero el ticket nunca sale | Revisar el Firewall de Windows (paso 3) — es la causa más común: el agente escucha bien en la PC, pero Windows bloquea la conexión entrante desde el navegador del cajero. |
| "Camino B: inactivo" después de un rato | Revisar que URL de Odoo / Base de datos / Canal del agente (pestaña Configuración) estén bien copiados, sin espacios de más ni comillas. |
| El ticket normal no sale pero el comprobante en PDF del Camino B sí (o viceversa) | Son 2 caminos independientes — revisar la pestaña Registros buscando errores específicos de cada uno. |
| "Mixed Content" en la consola del navegador del cajero | Odoo está en HTTPS y "Habilitar HTTPS" no está marcado en el agente (paso 4) — o sí está marcado pero el navegador todavía no aceptó el certificado autofirmado (abrir `https://<host>:<puerto>/health` una vez y aceptar la advertencia). |
| Dejó de funcionar después de unos días sin que nadie tocara nada | La IP de la PC Windows puede haber cambiado (DHCP) — si Odoo tiene guardada la IP vieja en "URL del agente local", hay que actualizarla. Recomendado: pedirle al administrador de red del local una **IP fija/reservada** para esta PC, igual que se recomienda para la Raspberry Pi en la guía Linux. |
| Nada imprime y no hay ningún error visible | Verificar que la PC puede alcanzar la impresora: `ping IP_DE_LA_IMPRESORA` desde una consola de Windows en esa PC. Si no responde, es un problema de red del local (impresora apagada, cable desconectado, IP cambió), no del agente. |

## Enlaces relacionados

- [`README.md`](../README.md) — referencia rápida de variables/campos para quien ya conoce el
  agente.
- [`GUIA_SERVICIO_WINDOWS.md`](GUIA_SERVICIO_WINDOWS.md) — la alternativa sin GUI, como Servicio
  de Windows.
- [`GUIA_CLOUDFLARE_TUNNEL.md`](GUIA_CLOUDFLARE_TUNNEL.md) —
  si el certificado autofirmado (HTTPS, paso 4) da problemas persistentes con el navegador del
  cajero.
