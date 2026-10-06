# Exponer el agente con un dominio real (Cloudflare Tunnel)

[← Volver a README.md](../README.md)

## Por qué esto, y no seguir con el certificado autofirmado

Todo lo que costó hacer andar el diálogo "Autorizar conexión con la impresora" contra un sandbox
público (`*.odoo.com`, `*.dev.odoo.com`) — advertencia de certificado, después Private Network
Access exigiendo un header en el preflight, después ese mismo bloqueo pero por
`Access-Control-Allow-Origin: *` — pasa **porque el agente vive en una IP de red privada** (LAN,
`192.168.x.x` u `och-pc`). Cada uno de esos mecanismos existe específicamente para frenar a una
página pública que intenta hablarle a algo de la red privada del usuario.

Si en cambio el agente tiene un **dominio público real, con certificado real** (no autofirmado),
el navegador deja de verlo como "red privada" — es un sitio HTTPS común y corriente, como
cualquier otro. Se acaban de un saque: la advertencia de certificado, Private Network Access, y el
ajuste de CORS que hicimos a mano. La forma más simple de conseguir esto sin abrir puertos en el
router del local ni depender de que la IP pública no cambie es un **túnel saliente** — el mismo
patrón que ya usa Odoo.sh/ngrok/Tailscale Funnel: el agente inicia la conexión hacia afuera, nunca
al revés, así que no hace falta tocar el firewall/router del local para nada.

**Cloudflare Tunnel** (`cloudflared`) es la opción gratuita más estándar para esto.

## Cuánto cuesta

- **Cloudflare Tunnel en sí: gratis.** No tiene límite de uso razonable para esto (son pedidos
  HTTP chicos — imagen de un ticket, JSON de estado — nada que se acerque a los límites de la capa
  gratuita).
- **Cuenta de Cloudflare: gratis.**
- **Lo único que puede salir plata es el dominio**, si no tenés uno ya:
  - Si ya tenés un dominio (p. ej. `ejemplo.com`) en Cloudflare, esto sale gratis: se agrega
    un subdominio nuevo (ej. `agente-tienda1.ejemplo.com`), sin comprar nada.
  - Si hace falta un dominio nuevo: cualquier registrador sirve (no hace falta comprarlo en
    Cloudflare) — los dominios de país se compran en el registro nacional correspondiente
    (Cloudflare Registrar no vende todos); un `.com`/`.app`/etc. se puede comprar donde sea, incluido el propio
    [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/) (vende al costo, sin
    markup — ej. un `.com` ronda los USD 9-10/año). Lo único que importa es poder cambiar los
    *nameservers* del dominio a los de Cloudflare (paso 2).

## 1. Cuenta de Cloudflare

1. Entrar a [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up) y crear una cuenta
   (gratis, no pide tarjeta para esto).
2. Confirmar el correo.

## 2. Agregar el dominio a Cloudflare

**Si ya hay un dominio en Cloudflare** (ej. `ejemplo.com`), saltar a la
[sección 3](#3-instalar-cloudflared-en-la-máquina-del-agente) directo — no hace falta agregar nada
nuevo, un subdominio se crea solo al configurar la ruta pública del túnel (paso 4).

**Si hace falta un dominio nuevo**:

1. Comprarlo en el registrador que sea (el registro nacional para un dominio de país, cualquiera
   para el resto).
2. En el dashboard de Cloudflare: **Agregar un dominio** → escribir el dominio → elegir el plan
   **Free**.
3. Cloudflare va a mostrar 2 *nameservers* propios (ej. `ana.ns.cloudflare.com`,
   `bob.ns.cloudflare.com`) — copiarlos.
4. Entrar al panel del registrador donde se compró el dominio, buscar la sección de
   **Nameservers/DNS** del dominio, y reemplazar los que trae por defecto por esos 2 de
   Cloudflare.
5. Esperar la propagación (Cloudflare avisa por correo cuando el dominio queda activo — puede
   tardar de minutos a un par de horas).

## 3. Instalar `cloudflared` en la máquina del agente

El resto de esta guía (pasos 4, 8, 9 y Notas de seguridad) es igual sin importar el sistema
operativo — solo este paso y el 5/6/7 cambian según dónde corra el agente.

### Ubuntu/Linux

Es el caso real de este proyecto — el agente corre en esta misma máquina (`och-pc`, Ubuntu),
no en una PC Windows separada. Instalar desde el repo oficial de Cloudflare (con paquete `.deb`
directo, sin agregar un repo APT, alcanza para esto):

```bash
curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb
```

Verificar:

```bash
cloudflared --version
```

### Windows

Si en algún momento el agente pasa a correr en una PC Windows del local (ver
[`README.md`](../README.md#instalación) para ese caso):

1. Descargar el instalador de Windows desde
   [pkg.cloudflare.com](https://pkg.cloudflare.com/) (o `winget install --id Cloudflare.cloudflared`
   desde una consola de Windows con `winget`).
2. Verificar que se instaló bien, en una consola (`cmd`/PowerShell):
   ```
   cloudflared --version
   ```

## 4. Crear el túnel

Desde una consola en esa misma PC:

```
cloudflared tunnel login
```

Abre el navegador y pide iniciar sesión en la cuenta de Cloudflare del paso 1, y elegir el
dominio del paso 2 — autoriza a `cloudflared` a crear túneles ahí. Queda un certificado guardado
localmente (`~/.cloudflared/cert.pem` en Linux/Mac, `%USERPROFILE%\.cloudflared\cert.pem` en
Windows) — no hace falta volver a loguearse cada vez.

Crear el túnel (el nombre es solo para identificarlo en el dashboard, usar algo reconocible por
local):

```
cloudflared tunnel create agente-tienda1
```

Esto genera un ID de túnel y un archivo de credenciales (`<ID>.json`) en la misma carpeta
`.cloudflared` — **ese archivo es un secreto**, tratarlo como una contraseña (no compartirlo, no
subirlo a ningún repo).

## 5. Configurar a qué apunta el túnel

Crear (o editar) el archivo de config — la ruta es lo único que cambia entre sistemas operativos,
el contenido es idéntico:

- **Ubuntu/Linux**: `~/.cloudflared/config.yml`
- **Windows**: `%USERPROFILE%\.cloudflared\config.yml`

```yaml
tunnel: agente-tienda1
credentials-file: /home/<usuario>/.cloudflared/<ID>.json  # Windows: C:\Users\<usuario>\.cloudflared\<ID>.json

ingress:
  - hostname: agente-tienda1.ejemplo.com
    service: http://localhost:8765
  - service: http_status:404
```

- `hostname`: el subdominio público que va a usar el agente — elegir algo que identifique el
  local (`agente-<nombre-del-local>.<dominio>`).
- `service`: **`http://localhost:8765`, no `https://`** — Cloudflare termina el HTTPS del lado
  público; hacia el agente le habla por HTTP plano dentro de la propia máquina (tráfico que nunca
  sale de ahí). Por eso conviene **desactivar `AL_AGENT_TLS_ENABLED`** en la configuración del
  agente (o dejarlo apagado si nunca se había activado) — ya no hace falta el certificado
  autofirmado para nada, Cloudflare provee uno real. Si se prefiere mantenerlo activo igual, usar
  `service: https://localhost:8765` y agregar `originServerName: <AL_AGENT_TLS_HOSTNAME>` bajo
  ese ingress — pero es un paso extra sin ningún beneficio real acá.
- La última línea (`service: http_status:404`) es obligatoria — regla de "todo lo demás, 404".

Conectar el hostname público al túnel:

```
cloudflared tunnel route dns agente-tienda1 agente-tienda1.ejemplo.com
```

## 6. Correr el túnel como servicio (para que sobreviva reinicios)

Igual criterio que el agente mismo (ver [`al-pos-local-agent.service.example`](../al-pos-local-agent.service.example)
para Linux, o "Inicio automático con Windows" en [`installer.iss`](../installer.iss) para Windows) —
el túnel tiene que quedar corriendo siempre, no solo mientras haya una consola abierta. El mismo
comando sirve en los dos sistemas — `cloudflared` detecta el sistema operativo solo:

```bash
sudo cloudflared service install   # Linux: pide sudo, crea un systemd unit. Windows: sin sudo, servicio de Windows.
```

Verificar que quedó corriendo:

**Ubuntu/Linux**:

```bash
sudo systemctl status cloudflared
```

tiene que decir **"active (running)"** en verde — si dice "failed", `journalctl -u cloudflared -n
50 --no-pager` tiene el detalle.

**Windows**: revisar en `services.msc` que "Cloudflared" esté "En ejecución".

En cualquiera de los dos, esto también confirma que el túnel conectó de verdad:

```
cloudflared tunnel info agente-tienda1
```

tiene que mostrar una conexión activa (`HEALTHY`).

## 7. Actualizar la configuración del agente

### Si corre con la GUI (`al_pos_local_agent_gui.py` / `AgenteEscpos.exe`)

Funciona igual en Ubuntu que en Windows (Tkinter es multiplataforma) — pestaña Configuración:

- **"Habilitar HTTPS"**: desactivar (Cloudflare ya lo resuelve — ver paso 5).
- El resto (impresoras permitidas, token) queda igual.

Guardar y reiniciar el agente.

### Si corre como servicio systemd (`al_pos_local_agent.py` directo, sin GUI — Ubuntu/Linux)

Editar el unit del agente (`/etc/systemd/system/al-pos-local-agent.service`, ver
[`al-pos-local-agent.service.example`](../al-pos-local-agent.service.example)):

- **Borrar** (o comentar) las 2 líneas de `AL_AGENT_TLS_ENABLED`/`AL_AGENT_TLS_HOSTNAME` — ya
  no hace falta el certificado autofirmado, Cloudflare provee uno real del lado público.
- El resto (`AL_AGENT_LISTEN_PORT`, `AL_AGENT_ALLOWED_PRINTERS`, `AL_AGENT_TOKEN`, y las de
  Camino B si se usan) queda igual.

Aplicar el cambio:

```bash
sudo systemctl daemon-reload
sudo systemctl restart al-pos-local-agent
sudo systemctl status al-pos-local-agent
```

tiene que decir **"active (running)"**.

## 8. Actualizar Odoo

**Ajustes → Punto de Venta → (el TPV) → Dispositivos conectados**:

- **"URL del agente local ESC/POS"**: `https://agente-tienda1.ejemplo.com` (el hostname del
  paso 5, **con `https://`** — eso lo maneja Cloudflare del lado público, aunque el agente esté
  escuchando por HTTP puertas adentro).

Guardar y recargar (F5) la pestaña del POS (ver nota de "Método de impresión" — el objeto
impresora del navegador se arma una sola vez al cargar la pestaña).

## 9. Probar

1. Abrir `https://agente-tienda1.ejemplo.com/health` directo en el navegador — tiene que
   responder el JSON de siempre, **sin ninguna advertencia de certificado** (es un certificado
   real de Cloudflare, no autofirmado).
2. Si `pos.config.escpos_require_agent_authorization` está activo (ver
   [`README.md`](../../README.md) del módulo): probar "Pagar" en el POS — el diálogo
   de autorización debería resolverse solo en el primer "Reintentar", sin necesitar el paso de
   "Abrir agente y aceptar advertencia" (ya no hay advertencia que aceptar). Si venía usándose con
   el toggle desactivado (para no bloquear mientras se resolvía todo esto), este es el momento de
   reactivarlo.
3. Hacer una venta de prueba y confirmar que imprime.

## Notas de seguridad

- El túnel expone el agente a **cualquiera que conozca la URL**, no solo a Odoo — las dos
  protecciones que ya tiene el agente siguen siendo la línea de defensa real acá:
  `AL_AGENT_TOKEN` (header `X-Agent-Token`, configurarlo si todavía no está) y
  `AL_AGENT_ALLOWED_PRINTERS` (nunca deja mandar trabajos a una IP:puerto fuera de esa lista).
- Para una capa extra opcional, **Cloudflare Access** (Zero Trust, también gratis hasta 50
  usuarios) puede exigir un login/token de Cloudflare antes de llegar siquiera al agente — probablemente
  innecesario para este caso (el POS necesita llegar sin fricción humana de por medio), pero
  queda como opción si en algún momento se quiere restringir por IP de origen o similar.
- El archivo de credenciales del túnel (`<ID>.json`, paso 4) y el `AL_AGENT_TOKEN` son los 2
  secretos reales de esta configuración — tratarlos como contraseñas.
