# Instalar el agente local en el negocio — guía para el técnico

Esta guía es para la persona que va a viajar al local a dejar el agente instalado y funcionando —
**no hace falta saber programar ni Python**. Si algo de acá no queda claro o el resultado no
coincide con lo esperado, mejor frenar y consultar antes de seguir, que forzar el paso siguiente.

Si en cambio ya sabés Python/Linux y solo necesitás la referencia rápida de variables y comandos,
ver [`README.md`](../README.md) en la carpeta superior (`agent/`) — esta guía es la versión larga, paso a paso.

## ¿Cuándo hace falta esto?

Solo si el servidor de Odoo **no está en la misma red que la impresora** del local (por ejemplo,
Odoo corriendo en Odoo.sh, en la nube). Si el servidor de Odoo está en una máquina dentro del mismo
local (como en la mayoría de las instalaciones actuales), **no hace falta nada de esto** — la
impresora ya funciona directo, sin este agente.

## 1. Qué llevar / conseguir antes de ir al local

- Una **Raspberry Pi** (cualquier modelo con Ethernet o Wi-Fi alcanza — un Raspberry Pi 3 o 4 anda
  bien) con su fuente de alimentación, o cualquier mini PC/notebook viejo que se pueda dejar
  siempre prendido en el local. No hace falta que sea potente — el agente usa muy pocos recursos.
- Una tarjeta microSD (8GB o más) si es Raspberry Pi.
- Cable de red (recomendado, más estable que Wi-Fi) o los datos del Wi-Fi del local.
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

## 2. Preparar la Raspberry Pi

1. Instalar **Raspberry Pi OS Lite** (sin escritorio, no hace falta) en la tarjeta SD — usar el
   [Raspberry Pi Imager](https://www.raspberrypi.com/software/) oficial desde otra computadora.
   Dentro del Imager, antes de grabar, ir a las opciones avanzadas (ícono de tuerca) y:
   - Activar SSH.
   - Poner un usuario y contraseña propios (no dejar el default).
   - Si se va a usar Wi-Fi, configurar la red ahí mismo.
2. Poner la tarjeta en la Raspberry, conectarla a la red del local (cable de red recomendado) y
   prenderla. Esperar 1-2 minutos a que arranque.
3. Conectarse por SSH desde otra computadora en la misma red:
   ```
   ssh usuario@<IP-de-la-raspberry>
   ```
   (La IP se puede ver en la pantalla del router, en una app como "Fing", o —si se dejó Ethernet—
   preguntándole al router qué dispositivos nuevos aparecieron.)

## 3. Instalar el agente

Una vez conectado por SSH a la Raspberry (todo lo que sigue se copia y pega tal cual, línea por
línea, esperando a que termine cada una antes de la siguiente):

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
mkdir -p /opt/al-pos-local-agent
cd /opt/al-pos-local-agent
```

Ahora hay que traer 2 archivos a esta carpeta (`al_pos_local_agent.py` y `requirements.txt`) —
la forma más simple es que quien tiene acceso al código del proyecto se los pase por USB, o los
suba a algún lugar accesible y se descarguen con `wget`/`scp`. **No hace falta traer nada más de
la carpeta `agent/`** — solo esos 2 archivos.

Con los 2 archivos ya copiados en `/opt/al-pos-local-agent/`, seguir:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Esto puede tardar 1-2 minutos — está instalando las librerías que necesita el agente.

## 4. Configurar el agente con los datos del local

Generar un token propio de este local (copiar el resultado, se va a necesitar en el paso
siguiente):

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Crear el archivo de configuración del servicio:

```bash
sudo nano /etc/systemd/system/al-pos-local-agent.service
```

(`nano` es un editor de texto simple — se escribe/pega directo, y se guarda con `Ctrl+O`, `Enter`,
y se sale con `Ctrl+X`.) Pegar esto, **reemplazando los 5 valores en mayúsculas** por los datos
reales del local (los 3 del paso 1, el token recién generado, y la IP:puerto de la impresora — el
puerto casi siempre es `9100`):

```ini
[Unit]
Description=Agente local ESC/POS para el TPV de Odoo
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/al-pos-local-agent
ExecStart=/opt/al-pos-local-agent/.venv/bin/python al_pos_local_agent.py
Restart=always
RestartSec=5

Environment=AL_AGENT_LISTEN_PORT=8765
Environment=AL_AGENT_ALLOWED_PRINTERS=IP_DE_LA_IMPRESORA:9100
Environment=AL_AGENT_TOKEN=EL_TOKEN_QUE_ACABAS_DE_GENERAR
Environment=AL_AGENT_ODOO_URL=URL_DE_ODOO_QUE_TE_PASARON
Environment=AL_AGENT_ODOO_DB=NOMBRE_DE_LA_BASE_QUE_TE_PASARON
Environment=AL_AGENT_BUS_CHANNEL=EL_CANAL_QUE_TE_PASARON

[Install]
WantedBy=multi-user.target
```

Si el usuario del sistema no se llama `pi` (depende de lo que se haya puesto al grabar la tarjeta),
cambiar esa línea también.

## 5. Arrancar el servicio

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now al-pos-local-agent
```

Verificar que arrancó bien:

```bash
sudo systemctl status al-pos-local-agent
```

Tiene que decir **"active (running)"** en verde. Si dice "failed" o "inactive", ver la sección de
problemas más abajo.

## 6. Probar que funciona de verdad

Desde la misma Raspberry:

```bash
curl http://localhost:8765/health
```

Tiene que devolver algo como:
```
{"status": "ok", "escpos_available": true, "allowed_printers": ["IP_DE_LA_IMPRESORA:9100"]}
```

Si `escpos_available` dice `false`, algo falló en el paso 3 (instalación de dependencias) —
volver a correr `.venv/bin/pip install -r requirements.txt` y revisar si tira algún error.

Para confirmar que también se conectó bien a Odoo (el "Camino B", usado por los comprobantes en PDF
que imprime el backend de Odoo):

```bash
sudo journalctl -u al-pos-local-agent -n 50 --no-pager
```

Buscar en esa salida una línea que diga algo como **"Camino B activo"**. Si en cambio dice
**"Camino B inactivo"**, revisar que las 3 variables `AL_AGENT_ODOO_URL`/`_ODOO_DB`/
`_BUS_CHANNEL` del paso 4 se hayan pegado bien (sin espacios de más, sin comillas de más).

**Prueba final, la que realmente importa**: desde el punto de venta, hacer una venta de prueba y
confirmar que el ticket sale impreso en la impresora física. Si el local usa el Camino B (algún
módulo de Odoo publica comprobantes en PDF por el bus), generar también uno de esos comprobantes y
confirmar que sale.

## 7. Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| `systemctl status` dice "failed" | `sudo journalctl -u al-pos-local-agent -n 50 --no-pager` y leer el error — casi siempre es un typo en el archivo del paso 4 (falta una variable obligatoria, o `AL_AGENT_ALLOWED_PRINTERS` mal escrito). |
| `escpos_available: false` en `/health` | Faltó instalar las dependencias (paso 3) o se instalaron en el lugar equivocado — confirmar que el `ExecStart` del servicio apunta al mismo `.venv` donde se corrió el `pip install`. |
| El ticket normal no sale pero el comprobante en PDF del Camino B sí (o viceversa) | Son 2 caminos independientes — revisar el log (`journalctl`) buscando errores específicos de cada uno, y confirmar que del lado de Ajustes de Odoo estén completos tanto la URL del agente (para el ticket) como el canal (para el Camino B). |
| Nada imprime y no hay ningún error visible | Verificar que la Raspberry puede alcanzar la impresora: `ping IP_DE_LA_IMPRESORA` desde la Raspberry. Si no responde, es un problema de red del local (impresora apagada, cable desconectado, IP cambió), no del agente. |
| Se cortó la luz/internet del local y volvió | No hace falta hacer nada — el agente se reconecta solo apenas vuelve la red (probado: reintenta cada 10 segundos indefinidamente). Si después de varios minutos sigue sin funcionar, recién ahí revisar `journalctl`. |

## 8. Actualizar el agente más adelante

Si en algún momento avisan que hay una versión nueva de `al_pos_local_agent.py`:

```bash
sudo systemctl stop al-pos-local-agent
# reemplazar /opt/al-pos-local-agent/al_pos_local_agent.py por el archivo nuevo
sudo systemctl start al-pos-local-agent
```
