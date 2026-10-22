# Cobranza: análisis y plan

Fecha: 21/10/2026. Mismo patrón que el análisis de pagos (`docs/pagos/`): primero lo que ya
dan Odoo 19 y la suite, luego lo que tenía Inveragro, y solo se desarrolla lo que falta.

## 1. Lo que ya existe

| Necesidad | Odoo 19 (Enterprise) | Suite | Inveragro (v16) |
|---|---|---|---|
| Niveles de seguimiento (recordatorios por días de atraso, también antes del vencimiento) | `account_followup`: niveles con correo, SMS, WhatsApp, carta y actividad; cron automático | — | `om_account_followup` estándar, sin personalizar |
| Responsable de cobranza por cliente | `followup_responsible_id` (por compañía) | — | `sectorist_id` (`type_contact_partner`) |
| Antigüedad de saldos | Informe «Cuentas por cobrar vencidas» (`account_reports`) | — | `accounting_pdf_reports` sin sectorista |
| Estado de cuenta | Informe de seguimiento (formato genérico) | — | `wizard.report.to.collect` (PDF por cliente, con letras y mora) |
| Límite de crédito | `credit_limit` del contacto y aviso en ventas | — | `credit.assign` con aprobaciones (agrícola) |
| Proyección de cobranza | — | `al_l10n_pe_cash_forecast` (flujo de caja de toda la empresa) | `payment_projection`: proyección mensual por sucursal y sectorista, XLSX; sin cron ni avisos; código duplicado y dependencias ocultas |
| Gestiones (llamadas, visitas) y su resultado | Solo actividades sueltas | — | — |
| Compromisos / promesas de pago | — | — | — (solo la nota «payment promise» del followup) |
| Metas de cobranza | — | — | Solo metas de **venta** |
| Indicadores (DSO, cumplimiento) | — | — | — |
| Notificaciones propias de cobranza | Las de los niveles | — | — |
| Letras, detracciones, factoring | — | Letras, detracciones, factoring (P9: no se cobran directo si las tiene un tercero) | Letras y negociables |

## 2. Qué se desarrolla: app **Cobranza** (`al_l10n_pe_collection`)

Sobre `account_followup` (instalado en todas las bases): el gestor es su
`followup_responsible_id` y los niveles siguen siendo los nativos.

1. **Cartera** (vista SQL): cuotas abiertas por cobrar con gestor, zona, vencimiento, días de
   atraso, tramo de antigüedad y compromiso vigente. Excluye anticipos (122) y detracciones
   por cobrar (van al Banco de la Nación). Pivote y gráfico por gestor, zona y tramo.
2. **Zonas** y **gestor** en el contacto.
3. **Gestiones de cobranza**: canal (llamada, visita, correo, WhatsApp, SMS, carta), resultado
   configurable, nota, documentos y próxima acción (actividad del gestor). Un resultado
   «promesa» crea el compromiso.
4. **Compromisos de pago**: fecha, importe y documentos. Un cron los evalúa al vencer
   (con tolerancia): **cumplido**, **parcial** o **incumplido** según lo cobrado de esos
   documentos desde que se pactó. Incumplido: actividad al gestor y aviso.
5. **Proyección de cobranza** por semanas o meses: fecha esperada de cada cuota = compromiso
   vigente, o vencimiento + atraso promedio del cliente (historial de 12 meses), o
   vencimiento; importe esperado = saldo × probabilidad del tramo de antigüedad
   (configurable). Por gestor y cliente; proyectado frente a lo cobrado en periodos
   terminados; pivote y Excel.
6. **Metas de cobranza** por gestor y mes: cobrado y porcentaje de avance.
7. **Tablero**: cartera, vencida y % vencido, por vencer en 7 días, compromisos de hoy e
   incumplidos, DSO de 90 días y cobrado del mes frente a la meta.
8. **Estado de cuenta** en PDF con el formato común de la suite (documento, emisión,
   vencimiento, días de atraso, total, saldo; totales vencido y por vencer) y envío por
   correo.
9. **Notificaciones**:
   - recordatorio al cliente N días antes de la fecha del compromiso;
   - alerta al gestor de compromiso incumplido;
   - resumen diario por correo a cada gestor (compromisos del día, próximas gestiones,
     documentos que vencen en 3 días, nuevos vencidos);
   - niveles de seguimiento en español listos para cargar (preventivo y escalonado).
10. **Ajustes**: tolerancia de compromisos, días de recordatorio, resumen diario, tramos y
    probabilidades.

Seguridad: grupos **Cobranza / Gestor** (ve su cartera) y **Cobranza / Administrador**;
reglas multicompañía; el gestor solo ve sus clientes salvo el administrador.

## 3. Fuera de este alcance (siguientes pasos)

> 22/10/2026: v3 cubre bloqueo de ventas, centrales de riesgo, reclamos, intereses,
> provisión y castigo; ver [INVESTIGACION_Y_MEJORAS_V3.md](INVESTIGACION_Y_MEJORAS_V3.md).

- Bloqueo de pedidos por mora (puente con `sale`).
- Reporte a centrales de riesgo (Infocorp/Equifax) y cobranza judicial.
- Comisiones de cobranza.
- Archivos de recaudación bancaria (especificación de cada banco; ver P11).
