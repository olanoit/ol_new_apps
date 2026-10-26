Historial de cambios — Portal de obra (AL)
==========================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_portal.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261025 — 26/10/2026

- CR-16, criterio 5: ajuste «Devolución de lo dañado»: lo que la obra devuelve como dañado vuelve en su propia transferencia a esa ubicación (Bajas del almacén); vacío, se desecha en la obra como antes.

## 5.20261025 — 26/10/2026

- CR-17: el rol no repite el tipo cuando la actividad ya lo dice («Drywall (contrata)»).

## 4.20261025 — 26/10/2026

- CR-17: Avance, Requerimientos y Cuadrilla y tareo muestran el código y el nombre de la partida, con su nivel superior y el rol; ya no la ruta interna. El servicio agrega task_code, task_name, parent_label y role_label sin quitar los campos anteriores; lo guardado sin señal se envía igual.
- CR-17: el catálogo de Requerimientos busca por producto y por código o nombre de la partida.
- 7.1: el parte diario lista los avances reportados y validados del día con su estado. 7.2: el tareo dice partida y rol en cada columna y agrupa por partida. 7.3: el requerimiento interno pedido desde el portal queda en la obra.
- Tareo: la marcación de la cuadrilla registra las horas del tareo completas; la salida se corre lo que dura el almuerzo del horario del empleado (Odoo lo descuenta de las horas trabajadas).

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
