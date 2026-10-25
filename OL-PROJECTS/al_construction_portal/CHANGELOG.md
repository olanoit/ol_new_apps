Historial de cambios — Portal de obra (AL)
==========================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_portal.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261025 — 25/10/2026

- Avance sobre el saldo más la tolerancia según la política del plan, como en el prototipo: con aprobación adicional se envía como exceso y lo aprueba la jefatura; con solo alerta se envía con aviso; con bloqueo no se guarda.

## 2.20261024 — 24/10/2026

- Pantallas según el prototipo «Portal de obra CREVAL»: ingreso con la marca de la empresa, mostrar la clave y «Mantener la sesión en este celular»; QR leído con la cámara; inicio con la semana de la obra y los contadores de avances por validar, pedidos en aprobación y entregas de hoy.
- Avance: el exceso sobre el saldo más la tolerancia del plan se avisa y no se guarda (Odoo no lo acepta); GPS dentro o fuera del radio de la obra; pantalla «Avance guardado» con los registros de hoy.
- Parte diario ya llenado con el personal propio que marcó hoy, cada contrata de la obra y los avances del día; cuadrilla en dos columnas en la tablet con Presente/Falta y total de 8 horas.
- Requerimientos con los materiales de las recetas de la cuadrilla; recepción con el estado de cada producto (completo, faltan, llegó de más); devolución eligiendo cada producto.
- Contrata: tarjeta de la orden (contratado, valorizado, fondo y deductivos), detalle con las partidas de más avance, el re-trabajo no pagado, el neto que descuenta el adelanto, los pagos y el PDF del valorizado y de la factura.

## 1.20261024 — 24/10/2026

- Primera versión: aplicación de obra instalable y sin señal con servicios JSON, ingreso por QR y PIN, parte diario, tareo por partida, catálogos con kits, recepción y devolución (requerimiento CREVAL v1.0, 4.11).
