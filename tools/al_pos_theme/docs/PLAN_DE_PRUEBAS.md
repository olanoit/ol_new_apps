# Plan de pruebas — `al_pos_theme`

Objetivo: confirmar que el tema **no altera la lógica del PdV** (cálculos,
impuestos, sincronización, offline, pagos, comprobantes) y que **no queda ninguna
marca, logo, color ni icono del sistema base** a la vista del cajero o del
cliente.

- **Base de pruebas:** `ol_pe_v19` (cfg `cfg/my/pe.cfg`)
- **Cajas:** `TPV 1`, `TPV 2`
- **Navegadores:** Chrome escritorio (1920px), tablet vertical (~820px), teléfono (~390px, iPhone Safari real)
- **Antes de empezar:** reiniciar el servidor después de actualizar el módulo
  (fuera de `--dev` los bundles se cachean por proceso) y entrar al PdV desde
  el backend (*Punto de venta → Continuar vendiendo*) para forzar la recarga
  de datos.

> Las pruebas marcadas **(CPE)** emiten comprobantes electrónicos (boleta o
> factura con `al_l10n_pe_edi_pos`): hacerlas sólo en una base de pruebas o
> en el ambiente beta de la OSE/SUNAT.

## A. Pruebas automáticas

| # | Prueba | Cómo | Esperado |
|---|---|---|---|
| A1 | Tests del módulo | `odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_pos_theme --test-enable --test-tags /al_pos_theme --stop-after-init --http-port=18069` | `0 failed, 0 error(s) of 9 tests` |
| A2 | Instalación limpia | `-i al_pos_theme` en una base desechable con `point_of_sale` | Sin errores; campos `al_theme_*` creados |
| A3 | Desinstalación limpia | Desinstalar desde Aplicaciones en la base desechable | 0 campos, 0 vistas, 0 columnas `al_theme_*`; el PdV vuelve al aspecto original |

## B. Marca blanca (criterio de aceptación principal)

| # | Paso | Esperado |
|---|---|---|
| B1 | Abrir `/pos/ui/<id>` y mirar la pestaña del navegador | Título `<Marca> · <Caja>` y favicon de marca (no "Odoo POS") |
| B2 | Pantalla de carga | Fondo de marca y puntos en color primario (sin gris `#222`) |
| B3 | Login ("Abrir caja registradora") | Degradado de marca, sin burbujas de fondo del sistema base |
| B4 | Barra superior | Logo de la caja/compañía a la izquierda (o el nombre de marca en texto si no hay logo) |
| B5 | Menú ☰ → *Instalar aplicación* | Página "Instalar `<Marca> · <Caja>`"; ícono de marca; colores de la caja (no púrpura `#714B67`) |
| B6 | Pantalla del cliente (menú ☰ → ícono de pantalla) | Título/favicon de marca; sin "Powered by Odoo" ni logo Odoo |
| B7 | Recibo en pantalla y recibo impreso | Sin "Powered by Odoo"; el pie usa *Ajustes → Recibos → Pie de página* |
| B8 | Provocar un error de servidor (p.ej. validar sin conexión al servidor de impresión) | Título "Error de servidor de `<Marca>`" (no "Odoo") |
| B9 | Desconectar la red con el PdV abierto | Aviso "…`<Marca>` operará con funcionalidad limitada" |
| B10 | Modo oscuro (menú ☰ → *Cambiar al modo oscuro*) | Sigue el logo de la caja, **no** el logo oscuro del sistema base |

## C. Venta completa y pagos

| # | Paso | Esperado |
|---|---|---|
| C1 | Agregar 3 productos desde la cuadrícula y 1 desde la vista lista | Precio de la tarjeta = precio de la línea; contador del carrito en cada tarjeta |
| C2 | Cambiar cantidad (numpad *Cant.*), borrar una línea (⌫ ⌫) | Totales e impuestos se recalculan igual que sin el tema |
| C3 | Aplicar descuento (numpad *%*) a una línea | La línea muestra "% de descuento"; total correcto |
| C4 | Cambiar precio (numpad *Precio*) | Sólo con permisos; total correcto |
| C5 | Pago | En escritorio: el panel derecho pasa a "Pago" sin cambiar de pantalla; catálogo atenuado y bloqueado. En teléfono: pantalla de pago nativa |
| C5b | Con el panel de pago abierto, escanear un producto | No se agrega a la orden |
| C5c | *←* (volver) en el panel de pago | Vuelve a la orden; las líneas de pago ya ingresadas se conservan |
| C6 | Pagar en efectivo con +10/+20/+50 | "Cambio" en verde con el monto correcto |
| C7 | Pago múltiple: parte efectivo + parte Transbank/tarjeta | "Restante" en rojo hasta completar; luego se habilita *Validar* |
| C8 | **(CPE)** Validar | "Pago exitoso", recibo con la serie y número del comprobante y su QR; impresión ESC/POS en blanco y negro legible |
| C9 | Nueva orden | Vuelve a la pantalla de productos con la orden vacía ("La orden está vacía") |

## D. Cliente, notas y acciones

| # | Paso | Esperado |
|---|---|---|
| D1 | Botón de cliente → buscar y elegir un cliente | Nombre del cliente en color primario en el panel y en la pantalla de pago |
| D2 | Crear cliente (*Crear*) | Formulario completo; se guarda y queda asignado |
| D3 | Nota de línea y nota de cliente | Se muestran en la línea (texto atenuado) y en el recibo |
| D4 | ⋮ → Lista de precios / Cancelar orden | Diálogos con estilo del tema; la acción se ejecuta igual |

## E. Devoluciones (reembolso)

| # | Paso | Esperado |
|---|---|---|
| E1 | Órdenes → filtro *Pagado* → elegir una orden | Fila seleccionada con fondo suave; detalle a la derecha con líneas y total |
| E2 | Seleccionar línea y cantidad a reembolsar → *Reembolso* | Crea la orden de devolución con cantidades negativas |
| E3 | **(CPE)** Pagar y validar la devolución | Nota de crédito correcta; recibo de devolución |

## F. Sesión de caja

| # | Paso | Esperado |
|---|---|---|
| F1 | Abrir una sesión nueva | Popup de apertura: monto inicial, botón de billetes, nota |
| F2 | ☰ → Entrada/salida de efectivo | Control segmentado Entrada/Salida; *Confirmar* gris hasta completar monto y motivo |
| F3 | ☰ → Cerrar caja registradora | Resumen por método; diferencia en rojo si no cuadra; *Descartar* no cierra nada |
| F4 | **(CPE)** Cerrar caja con conteo correcto | Sesión cerrada; asiento de cierre igual que sin el tema |

## G. Modo offline

| # | Paso | Esperado |
|---|---|---|
| G1 | Con el PdV abierto, cortar la red | Aviso de conexión perdida con la marca; ícono de estado en la barra |
| G2 | Vender 2 órdenes en efectivo sin red | Se guardan localmente; contador de órdenes sin sincronizar |
| G3 | Recargar la página sin red | El PdV carga desde caché; logo y colores se mantienen (van en el índice cacheado). La fuente puede verse como la del sistema (limitación conocida) |
| G4 | Restaurar la red | Las órdenes se sincronizan sin errores |

## H. Configuración por caja

| # | Paso | Esperado |
|---|---|---|
| H1 | Ajustes PdV → elegir `TPV 2` → Apariencia: cambiar nombre, logo y color primario | Se guarda; colores inválidos (`red`, `#12345`) muestran error |
| H2 | Recargar `/pos/ui/<id TPV 2>` | Nueva marca aplicada sin actualizar el módulo; `TPV 1` no cambia |
| H3 | Primario muy claro (p.ej. `#A7F3D0`) | Texto de los botones primarios pasa a oscuro automáticamente (contraste AA) |
| H4 | Modo oscuro con primario oscuro (p.ej. `#1E293B`) | El primario se aclara en oscuro hasta ser legible |

## I. Diseño responsivo y accesibilidad

| # | Paso | Esperado |
|---|---|---|
| I1 | Teléfono: catálogo, carrito, pago, recibo | 2 columnas de productos; Pagar/Carrito fijos abajo; nada se sale de la pantalla |
| I2 | Tablet vertical | Panel de orden + catálogo de 2 columnas legibles |
| I3 | Navegación con teclado (Tab) | Anillo de foco visible en botones y campos |
| I4 | Enfocar el buscador en iPhone | No hace zoom automático (campos de 16px) |

## Resumen

| Bloque | Pruebas | Resultado | Observaciones |
|---|---|---|---|
| A. Automáticas | 3 | | |
| B. Marca blanca | 10 | | |
| C. Venta y pagos | 9 | | |
| D. Cliente y acciones | 4 | | |
| E. Devoluciones | 3 | | |
| F. Sesión de caja | 4 | | |
| G. Offline | 4 | | |
| H. Configuración | 4 | | |
| I. Responsivo / accesibilidad | 4 | | |
