# TPV - Tema y marca blanca (AL) (`al_pos_theme`)

> Tema integral y marca blanca del Punto de Venta de Odoo 19: el cajero y el
> cliente no ven ninguna marca, logo, color ni icono del sistema base. La
> lógica de negocio (cálculos, impuestos, sincronización, modo offline, pagos,
> comprobantes electrónicos) no se modifica.
>
> Adaptación a la suite AL del tema `mblz_pos_theme` de Mobilize: **marca
> neutra por defecto** (nombre y logo de la compañía, paleta azul/pizarra,
> icono propio) y compatibilidad con los módulos TPV de la suite.

| Información | |
|---|---|
| **Versión** | ver `__manifest__.py` (convención `N.AAAAMMDD`) |
| **Categoría** | ol-pos/Apps |
| **Licencia** | OPL-1 (fuentes Inter y Manrope: SIL OFL 1.1, `static/src/fonts/OFL.txt`) |
| **Autor** | CRISTÓBAL OCH |
| **Dependencias** | `point_of_sale` (probado con `pos_enterprise`, `al_pos_product_view`, `al_pos_vendedor` y `al_l10n_pe_edi_pos`) |
| **Idioma** | Español (textos de origen) |

## 1. Instalación

1. El módulo vive en `ol_new_apps/pos/` (incluido en el `addons_path` de
   `cfg/my/pe.cfg`).
2. Actualizar la lista de aplicaciones e instalar **TPV - Tema y marca blanca
   (AL)**, o por consola:

   ```bash
   odoo-bin -c <cfg> -d <db> -i al_pos_theme --stop-after-init
   ```

3. **Reiniciar el servidor** (los bundles del PdV se cachean por proceso).
4. Abrir cada caja **desde el backend** (*Punto de venta → Continuar
   vendiendo*): instalar/desinstalar el tema invalida la caché local de las
   cajas (`pos.config.last_data_change`) y así se recargan los datos.

**Desinstalar:** desde Aplicaciones. Se eliminan los campos `al_theme_*`,
las vistas y los assets; el PdV vuelve al aspecto estándar sin rastros.

## 2. Personalizar marca y colores (sin tocar código)

*Punto de venta ▸ Configuración ▸ Ajustes ▸ elegir la caja (arriba) ▸
sección **Apariencia***. Cada caja (`TPV 1`, `TPV 2`…) tiene su propia marca.

| Campo | Efecto |
|---|---|
| **Nombre** | Título de la pestaña (`<Nombre> · <Caja>`), app instalada (PWA) y mensajes del sistema ("Error de servidor de `<Nombre>`") |
| **Logo** | Barra superior y pantalla de reposo. Vacío → logo de la compañía → nombre en texto. Recomendado: PNG horizontal con fondo transparente, ~400×120px |
| **Icono de pestaña** | Favicon. Vacío → icono del módulo |
| **Primario** | Botones principales, precios, selección, enlaces |
| **Secundario** | Inicio del degradado del login (conviene un tono oscuro) |
| **Acento** | Descuentos y avisos |
| **Fondo** | Fondo general del PdV en modo claro |

- Los colores se ingresan como `#RRGGBB`; un valor inválido se rechaza.
- Los tonos de hover/activo/suave y el **color del texto sobre los botones
  se calculan solos** con contraste AA (un primario claro lleva texto oscuro).
- Los cambios se ven **al recargar el PdV**: no hace falta actualizar el
  módulo ni recompilar assets.
- **Pie del recibo:** campo estándar *Ajustes → Recibos → Pie de página*.
- **Modo oscuro:** cada cajero lo activa en ☰ → *Cambiar al modo oscuro*
  (queda recordado en ese navegador). Los colores de la caja se adaptan solos:
  si el primario no es legible sobre el fondo oscuro se aclara hasta cumplir AA.

## 3. Distribución de la pantalla de venta y pago en línea

Desde tablet horizontal / escritorio (`lg`, ≥ 992px):

```
┌────────┬──────────────────────────┬──────────────┐
│ Filtros│ Catálogo                 │ Orden / Pago │
└────────┴──────────────────────────┴──────────────┘
```

- **Riel de categorías PdV** a la izquierda (sólo si hay categorías),
  **catálogo** al centro con los **chips de etiquetas** de
  `al_pos_product_view` encima (si está instalado), y **orden, totales, numpad y Pagar** a la derecha.
- La **barra superior sigue las mismas columnas**: logo, Registrar/Órdenes y
  pestañas sobre el catálogo; el **buscador**, escáner, cajero y menú sobre
  el panel de la orden, con su mismo ancho (400px en tablet, 450px desde
  1200px, igual que el core).
- **Pago sin cambiar de pantalla:** al tocar *Pago* el panel derecho se
  convierte en el panel de pago (total, métodos, líneas, cambio, cliente,
  vendedor y comprobante si sus módulos están instalados, numpad y
  *Validar*); el catálogo queda visible y bloqueado,
  y el escáner no agrega productos mientras se cobra. *←* vuelve a la orden
  (las líneas de pago se conservan, igual que en el nativo).
- La lógica es la nativa: el panel es una subclase de `PaymentScreen`
  (validación, terminales, comprobantes y parches de otros módulos incluidos)
  y se activa interceptando `PosStore.navigate("PaymentScreen")`, así que
  también lo usa `pos_settle_due`. Tras validar se pasa al recibo como
  siempre.
- En teléfono y tablet vertical se mantiene el flujo nativo por pantallas.

## 4. Personalización avanzada (desarrolladores)

- **Valores por defecto de marca:** `static/src/scss/_variables.scss` y
  `AL_THEME_DEFAULTS` en `models/pos_config.py` (mantener sincronizados).
- **Tokens de diseño:** `_variables.scss` (escala tipográfica, pesos, radios,
  sombras, alturas de control) → `_tokens.scss` (custom properties `--alpt-*`,
  claro y oscuro). Todo componente usa `var(--alpt-*)`, nunca colores fijos.
- **Paleta oscura:** bloque `:root[data-alpt-scheme="dark"]` en `_tokens.scss`.
- **Un componente nuevo:** agregar `static/src/scss/components/<nombre>.scss`
  (se incluye solo por el patrón del manifest) y, si hace falta estructura,
  una herencia en `static/src/xml/` registrada en el manifest.

## 5. Pruebas

- **Automáticas** (9 tests: validación de colores, CSS seguro, contraste AA
  en oscuro, payload, manifest PWA):

  ```bash
  .venv/bin/python odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_pos_theme \
      --test-enable --test-tags /al_pos_theme --stop-after-init \
      --workers=0 --http-port=18069 --gevent-port=18072
  ```

- **Funcionales:** [`docs/PLAN_DE_PRUEBAS.md`](docs/PLAN_DE_PRUEBAS.md)
  (marca blanca, venta completa, pagos múltiples, devoluciones, cliente,
  descuentos, cierre de caja, offline, impresión, configuración por caja,
  responsivo).

## 6. Cómo funciona

- **Tokens en 3 capas:** `_variables.scss` (SCSS) → `_tokens.scss` (`--alpt-*`
  en `:root`, claro/oscuro) → `<style>html[data-alpt-scheme]:root{…}` que el
  controller `/pos/ui` inyecta con los valores de la caja. `_base.scss`
  conecta los tokens con las variables de Bootstrap (`--primary`,
  `--btn-bg`…) sólo dentro de `.pos`: el backend no cambia.
- **El índice es la única fuente de la marca.** Con la sesión abierta el PdV
  arranca desde IndexedDB sin consultar `pos.config`
  (`data_service.js::loadInitialData`); por eso ningún campo del tema viaja en
  el payload: nombre (`<meta name="application-name">`), colores y logo (data
  URI, visible sin conexión) van en la página índice, que el servidor siempre
  renderiza.
- **Puntos de marca del sistema base cubiertos:** título y favicon (PdV y
  pantalla del cliente), logo de la barra y del reposo (incluido el logo
  oscuro que agrega `pos_enterprise` en modo oscuro), "Powered by" del recibo
  y de la pantalla del cliente, PWA "Instalar aplicación" (ícono, nombre,
  colores), diálogos del sistema ("Server Error", aviso offline, errores del
  servidor), fondo del login/reposo, pantalla de carga, íconos de métodos de
  pago, color de acción turquesa (`.text-action`, `btn-info`…).

## 7. Componentes modificados

| Componente | Tipo de cambio |
|---|---|
| `point_of_sale.index`, `point_of_sale.customer_display_index` | Herencia QWeb (servidor): título, favicon, `<meta>` de marca, tokens |
| `PosController.pos_web`, `WebManifest` | Override de controller |
| `dialogService`, `Navbar.appUrl`, `ProductCard` (precio), `PaymentScreen.paymentMethodImage`, `PaymentScreenStatus.amountText` (cambio sin signo) | `patch()` JS |
| `point_of_sale.Navbar` | Herencia OWL (logo siempre visible a la izquierda) + SCSS |
| `point_of_sale.ProductScreen`, `CategorySelector`, `ProductCard` | Herencia OWL (`bg-secondary` → `alpt-catalog`, `aria-pressed`, imagen `contain`, precio) + SCSS |
| `point_of_sale.OrderSummary` | Herencia OWL (slot `emptyCart`: orden vacía) |
| `PosStore.navigate`, `ProductScreen` (barcode), `AlptInlinePayment` (subclase de `PaymentScreen`) | `patch()` JS + herencia OWL de `ProductScreen`: pago en el panel derecho |
| Distribución de 3 columnas | Sólo SCSS (`layout.scss`): `row-reverse` + CSS grid sobre los hijos existentes |
| `Orderline`, `OrderDisplay`, `ControlButtons`, `Numpad`, `ActionpadWidget` | SCSS acotado a `.leftpane` de ProductScreen/TicketScreen (el recibo usa los mismos componentes y queda monocromo) |
| `point_of_sale.PaymentScreen`, `PaymentScreenDue` | Herencia OWL (quita `bg-100` y el `font-size: 125px` inline; etiqueta "Total a pagar") + SCSS |
| `point_of_sale.ReceiptScreen` | Herencia OWL (quita `bg-100`/`bg-200`) + SCSS; `OrderReceipt` no se estiliza |
| `point_of_sale.OrderReceipt`, `point_of_sale.CustomerDisplay` | Herencia OWL: se quita "Powered by"; en el ticket, el cambio sin signo menos |
| `point_of_sale.TicketScreen` | Herencia OWL (quita `bg-100`, estado vacío, clase `alpt-order-total`) + SCSS |
| `PartnerList`, `web.Dialog` y popups (Selection, Number, TextInput, Acciones) | Sólo SCSS: estilo común de modales bajo `.pos` |
| `OpeningControlPopup`, `ClosePosPopup`, `MoneyDetailsPopup`, `CashMovePopup` | Sólo SCSS (`session.scss`) |
| Bootstrap `btn-/alert-/text-bg-{success,danger,warning,info}`, `.text-action`, `fw-bold/fw-bolder` | Sólo SCSS (`_base.scss`) |
| `al_pos_product_view` (conmutador cuadrícula/lista, botón «i», chips de etiquetas) | Sólo SCSS (`compat_al.scss`), sin dependencia |

## 8. Criterios visuales

- **Casi sin negrita.** 400 (textos, nombres), 500 (etiquetas, botones,
  precios, estados) y 600 sólo para los montos que deciden la venta: total de
  la orden, total a pagar, cambio/restante, monto cobrado, total del cierre y
  diferencia de caja. Nada en 700. `fw-bold`/`fw-bolder`, `<b>`, `<strong>`,
  `<th>` y encabezados del core se normalizan a 500 dentro de `.pos`; el
  ticket impreso (`.pos-receipt`) se excluye.
- **Bordes suaves.** 1px en `#E6EBE9`; la selección se marca con fondo suave;
  la elevación la da la sombra.
- **Densidad compacta.** Raíz del PdV en 15px (el core mide en
  `rem`, así todo baja parejo) y texto base ~13px; escala 11/13/14/16/20px.
  Controles 36px, fila Cliente/Cotizar/Nota y barra 32px, teclas 42px,
  botones principales 44px; tarjetas de la cuadrícula ~120px de ancho.
  Radios: 8px controles, 12px tarjetas, 14px modales.
- **Modales ajustados.** Anchos nativos de Bootstrap. Sin líneas separadoras, paddings
  compactos, botones del pie con su ancho natural a la derecha (a lo ancho en
  teléfono).
- **Deshabilitado neutro:** un botón primario deshabilitado se ve gris.
- **Accesibilidad:** contraste AA en los pares de color (claro y oscuro),
  áreas táctiles ≥ 44px, anillo de foco visible, campos de 16px (sin zoom en
  iOS).

## 9. Uso de `!important`

Sólo para reemplazar utilidades de Bootstrap que el core declara con
`!important` (`bg-view`, `rounded-3`, `gap-*`, `p-*`, `border-*`,
`fw-bold`…), estilos inline de otros módulos o reglas `!important` de otros
módulos TPV; cada caso lleva un comentario con lo que reemplaza. Cuando un
cambio estructural lo permite se quita la clase vía herencia (`remove=`) o el
atributo (`<attribute>` vacío), como `bg-secondary` o el `font-size: 125px`.

## 10. Desarrollo

- Fuera del modo `--dev`, Odoo cachea los bundles por proceso: tras editar
  SCSS/JS/XML hay que **reiniciar el servidor**.
- No abrir dos instancias del PdV a la vez (pestañas o iframes) para probar:
  el servicio multipestaña del core expulsa a la primera al backend.
- `_base.scss` normaliza la negrita con especificidad 0,3,0 + `!important`:
  una regla de componente que deba ser más liviana o más fuerte sobre un
  elemento con `fw-bold`/`fw-bolder` necesita especificidad ≥ 0,3,0.
- Toda `var(--alpt-*)` usada debe existir (una variable indefinida anula la
  declaración en silencio, p.ej. radio 0):

  ```bash
  comm -23 <(grep -rhoE 'var\(--alpt-[a-z0-9-]+' static/src | sed 's/var(//' | sort -u) \
           <( (grep -rhoE '^\s*--alpt-[a-z0-9-]+:' static/src/scss/_tokens.scss; \
               grep -oE '"--alpt-[a-z0-9-]+"' models/pos_config.py | tr -d '"') | tr -d ' :' | sort -u)
  ```

## 11. Limitaciones conocidas

- La fuente Inter no está en la lista de caché del service worker del core:
  si se recarga el PdV **sin internet** se usa la fuente del sistema (logo y
  colores sí se mantienen).
- La URL (`/pos/ui`, `/web/login`) y el backend siguen siendo los del
  sistema base; usar la PWA instalada o modo kiosco para ocultar la barra de
  direcciones.
- Los mensajes de error que genere el servidor con el nombre del sistema base
  en el texto se reescriben en el diálogo, pero no en logs ni correos.
- Cerrar la lista de clientes con Escape/"Descartar" quita el cliente de la
  orden: es comportamiento del core, no del tema.
- En v19 `order.change` es negativo cuando se paga de más; el tema sólo
  corrige su **presentación** ("Cambio $50" en pantalla y en el ticket), el
  valor del modelo (`amount_return`) no se modifica.
