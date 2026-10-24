Historial de cambios — PE - Base Inventario (AL)
================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_stock_base.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 5.20261024 — 24/10/2026

- Devolver una transferencia sin cantidades muestra el aviso de Odoo en lugar del error «Falta el valor requerido para el campo Ubicación de destino» (lo provocaba mrp_subcontracting con el asistente sin líneas); si otro módulo deja vacío el destino de la devolución, se usa el que calcula Odoo.

## 4.20261024 — 24/10/2026

- Paquete 1.11, M111-13: validar un despacho con una fracción de plancha da el error de planchas enteras aunque ninguna línea esté marcada «Recogido».
- Paquete 1.11, M111-19 A: Ajustes › Inventario › «Resumen de inventario» elige el estilo de las tarjetas (Estándar de Odoo o Compacta), su ancho y si llevan el gráfico; cada usuario puede elegir otro estilo en sus preferencias.
- Paquete 1.11, M111-19 D: casillas de alcance de las planchas enteras (despacho a producción, requerimiento de obra y compras).
- Paquete 1.11, M111-18: la compra de un tablero indivisible se redondea en planchas y luego pasa a la unidad de compra; la validación en lote ya no falla por la firma de _sanity_check.

## 3.20261023 — 23/10/2026

- Paquete 1.11, M111-12 (fase B): producto retazo del tablero («Producto retazo», «Es retazo», «Retazo de») y costo fijo de una salida de producción.

## 2.20261023 — 23/10/2026

- Paquete 1.11, M111-09: resumen de inventario compacto, con o sin el planificador de obra: tarjetas sin gráfico, más angostas, con botones pequeños y las etiquetas en español (Con demora, En espera, Órdenes parciales, Movimientos). Antes estaba en el puente de compras del planificador.
- Paquete 1.11, M111-12: regla de las planchas enteras: casilla «Pedir tableros en planchas enteras» y tolerancia en la compañía, unidad marcada «Plancha entera» con su área en m², «Plancha indivisible» en el producto, necesidad y redondeo en los movimientos y en la impresión de la transferencia, reserva en planchas enteras y error al validar fracción.

## 1.20261008 — 08/10/2026

- Página Logística PE en las transferencias, con grupos de guía de remisión, transporte, libros electrónicos y requerimiento de obra.
