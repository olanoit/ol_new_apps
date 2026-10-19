# Farmacia: convenios con EPS y empresas (AL)

Convenios con aseguradoras y empresas: cobertura por producto o categoría, copago, topes por venta y por mes, afiliados, cobro de la parte cubierta en la caja y liquidación mensual a la aseguradora.

Plan: [docs/farmacia/](../../docs/farmacia/MEJORAS_PROCESOS.md) (mejora E10).

## Decisión contable

Informe SUNAT 029-2013 (deja sin efecto el 061-2008): lo que la aseguradora paga por su asegurado se factura a nombre de la aseguradora; el paciente recibe comprobante solo por su parte.

- **Caja:** la venta con convenio reparte lo cubierto por línea, en base e IGV ya redondeados. La boleta o factura del paciente (o, si no pide comprobante, la venta del cierre de caja) lleva solo la parte del paciente con su IGV, usando esos montos tal cual (impuestos manuales del motor de impuestos de Odoo). El método «Convenio» (cuenta de cliente) no deja cuenta por cobrar en la caja: la parte cubierta no se registra allí.
- **Liquidación:** crea la factura de cliente a la aseguradora en el diario de ventas del convenio, una línea por producto vendido con su base e IGV cubiertos. Esa factura es el ingreso y la cuenta por cobrar de la parte cubierta.
- **Resultado por venta:** ingreso del paciente + ingreso de la aseguradora = ingreso de la venta; IGV del paciente + IGV de la aseguradora = IGV de la venta; cuenta por cobrar del paciente = 0 (pagó su parte en caja); cuenta por cobrar de la aseguradora = lo cubierto. Cada venta se liquida una sola vez.
- **Reembolso:** con la modalidad «reembolso» la caja no aplica el convenio; el paciente paga el total con su boleta y pide el reembolso a la aseguradora.

Límites: las devoluciones de una venta con convenio no reparten lo cubierto (el TPV devuelve el total; la parte de la aseguradora se anula con una nota de crédito a su factura); el redondeo de efectivo de la caja no se aplica a las ventas con convenio.
