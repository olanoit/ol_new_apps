Historial de cambios — Portal de obra (AL)
==========================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_portal.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 12.20261027 — 07/11/2026

- Paquete 6, CR-57: avisos al celular con la aplicación cerrada (envío web nativo de Odoo): pedido urgente por aprobar, entrega en camino a la obra (acción programada cada 15 minutos), avance reportado fuera del radio de la obra y avance validado o rechazado a quien lo reportó. Qué aviso recibe cada papel se configura en «Avisos al celular»; la persona los activa en la aplicación. Tocar el aviso abre la pantalla del registro.
- Paquete 6, CR-55: acceso «Gasto con mi fondo» en «Mi día» cuando está instalado el puente con la caja chica (al_construction_portal_cash_fund).

## 11.20261027 — 07/11/2026

- Paquete 6, CR-58: pestaña «Obra» del residente. Resumen con el avance físico real (el mismo del tablero de obra del escritorio) frente al programado a hoy, partidas atrasadas, avances por validar, pedidos abiertos y personal de hoy, curva de avance y avance por especialidad; montos solo si la compañía lo permite (Ajustes). Semana: partidas que inician y terminan esta semana y las que inician la siguiente, con aviso de las que inician sin contrata ni cuadrilla y de las que terminan en riesgo (umbral en Ajustes). Tareas: partidas en columnas que calcula Odoo (solo lectura); tocar una abre el registro de su avance.
- Paquete 6, CR-54: Gantt liviano para celular y tablet, de solo lectura, con el avance validado como relleno, las partidas atrasadas, los hitos y la línea de hoy; zoom de semana y mes. Las cuatro vistas funcionan sin señal con los datos de la última sincronización.

## 10.20261027 — 07/11/2026

- Paquete 6, CR-56: un parte diario por persona y día (también lo envía la contrata). El residente ve los partes del día y quién no envió, y con «Cerrar el día» arma el parte diario de obra (personal, avances, restricciones, ocurrencias, fotos y su comentario) y lo envía en PDF al «Contacto del cliente en obra»; sin contacto, queda en la obra. Los partes quedan «Revisado por el residente».
- Paquete 6, CR-51: deductivo de contrata con foto desde el portal (por monto o por cantidad al precio de la partida en la orden); queda «Pendiente» y entra en la siguiente valorización.
- Paquete 6, CR-52: solicitud de contrata o de cuadrilla adicional como actividad en la partida para el jefe de la obra, con su estado (Pedida, Asignada, Cancelada).
- Accesos a un toque en «Mi día» (cambio del cliente, deductivo, pedir cuadrilla o contrata).

## 9.20261027 — 07/11/2026

- Paquete 6, CR-48: rol «Residente de obra» en el portal, sin usuario interno (puede ser un locador sin ficha de empleado). Ve lo del capataz y la oficina técnica, más «Mi día» (contadores y agenda de hoy por urgencia) y su barra Inicio, Bandejas, Obra y Por enviar. Con el QR y el PIN no tiene el rol Residente. «Aprobador por defecto de la obra» en el personal del portal.
- Paquete 6, CR-49: bandeja «Por validar» con orden por corte de valorización, avisos (saldo, exceso que espera a la jefatura, GPS, semana valorizada), fotos ampliables y la última validada; validar corrigiendo a la baja, rechazar y re-trabajo con motivos configurables; validar en lote solo lo que no tiene aviso. Quien reportó recibe el aviso.
- Paquete 6, CR-50: bandeja «Por aprobar» con saldo del plan y exceso por línea; aprobar lo pedido, el saldo u otra cantidad menor, o rechazar con motivo; con validación por niveles y con Aprobaciones. Revisor por campo «Residente de la obra» y opción «Pasar al residente de la obra» para los requerimientos sin regla.
- Paquete 6, regla «Sin señal»: validar, rechazar y aprobar entran a la cola; Odoo vuelve a comprobar el registro al recibirlos y rechaza la decisión con el motivo si cambió.
- Tablet: lista y detalle lado a lado en las bandejas.

## 8.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 7.20261025 — 27/10/2026

- CR-16, criterio 5: «En buen estado» crea la devolución nativa del despacho recibido (stock.return.picking, con el movimiento de origen, el requerimiento y la partida), lista para que el almacén la valide; al validarse baja «Despachado».
- CR-16, criterio 6 (D5): «Dañado» ya no desecha: crea el traslado de la obra a su sububicación «Dañados», con la foto y el motivo (obligatorio), listo para validar; «Despachado» no cambia. Se retira el ajuste «Devolución de lo dañado» (Bajas).
- Lo que está en «Dañados» ya no aparece para devolver; después de una recepción o una devolución, la pantalla Devolución se actualiza sola (sin «Actualizar»).

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
