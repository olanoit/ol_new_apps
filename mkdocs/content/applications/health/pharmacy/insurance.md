---
modulos: [al_pharmacy_insurance]
---

# Convenios con EPS y empresas

La botica atiende a afiliados de EPS y a trabajadores de empresas con
convenio: el paciente paga una parte (copago) y la aseguradora el resto. Por
el criterio de SUNAT (Informe 029-2013), el comprobante de la parte cubierta
va a nombre de la aseguradora: el paciente recibe boleta o factura solo por
lo que paga.

## Configuración

1. **Farmacia ‣ Convenios ‣ Convenios ‣ Nuevo**:
    - **Aseguradora o empresa** a la que se factura.
    - **Cobertura** por defecto (%) y, en las líneas, por categoría o por
      producto (la del producto manda, luego la categoría más cercana).
    - **Copago** fijo por venta, **tope por venta** y **tope mensual** por
      afiliado.
    - **Vigencia**, si **exige receta** y el **diario de ventas** de la factura
      a la aseguradora.
    - **Modalidad**: **en caja** (la botica cobra a la aseguradora) o
      **reembolso** (el paciente paga todo y la aseguradora le reembolsa).
2. Pulse **Crear método de pago del TPV** y agregue el método a la caja con la
   sesión cerrada.
3. Registre los **afiliados** (**Farmacia ‣ Convenios ‣ Afiliados**): paciente,
   número de afiliado y vigencia.

## En la caja

1. Elija al cliente afiliado y agregue los productos (con la receta, si el
   convenio la exige).
2. En la pantalla de pago elija el método del convenio: Odoo calcula lo
   cubierto con la cobertura, el copago y los topes. Si no corresponde
   (afiliado no vigente, falta la receta, tope alcanzado), avisa el motivo.
3. El paciente paga el resto con los demás métodos.

El comprobante del paciente lleva cada línea solo por su parte (base e IGV);
las líneas cubiertas al 100 % no salen.

!!! example "Ejemplo"
    Paracetamol S/ 10 y losartán S/ 20, más IGV: S/ 35,40. El convenio cubre
    80 % del paracetamol y 50 % del losartán (categoría de crónicos), menos
    S/ 2 de copago: S/ 19,24, de los que S/ 10,69 son del losartán. El paciente paga
    S/ 16,16 con su boleta; la aseguradora recibe S/ 19,24 en la factura de la
    liquidación.

## Liquidación mensual

1. **Farmacia ‣ Convenios ‣ Liquidaciones ‣ Nuevo**: elija el convenio y el
   periodo y pulse **Cargar ventas** (solo de cajas cerradas y no liquidadas).
2. **Contabilizar** crea la factura a la aseguradora: una línea por producto
   vendido con su base e IGV cubiertos, y en la descripción la venta, el
   comprobante del paciente, el DNI, el número de afiliado y la receta.
3. Imprima la liquidación como sustento para la aseguradora.

Para corregir, **Anular** cancela la factura si sigue en borrador; si ya está
validada, emita una nota de crédito.

## Devoluciones

La devolución se hace en la caja, como cualquier otra, y el paciente recupera
solo lo que pagó:

1. En **Órdenes**, abra la venta y pulse **Reembolsar** con los productos que
   devuelve.
2. En el pago, elija el método del convenio: la caja propone la parte que
   pagó la aseguradora, en negativo. Devuelva el resto al paciente con su
   medio de pago. Sin la parte del convenio, la caja no deja validar.
3. La nota de crédito del paciente va solo por su parte.

En la liquidación, la devolución se carga con las ventas del periodo:

| Venta original | Qué hace la liquidación |
|---|---|
| En la misma liquidación | Resta lo devuelto de esa línea de la factura (un producto devuelto entero no sale) |
| Ya facturada en una liquidación anterior | Crea una **nota de crédito** a la aseguradora sobre esa factura |
| Aún sin liquidar, en otro periodo | Aviso: liquide primero el periodo de la venta |

!!! example "Ejemplo"
    Del ejemplo anterior, el paciente devuelve el losartán después de la
    liquidación. El convenio cubrió S/ 10,69 de esa línea: la caja devuelve
    S/ 10,69 con el método del convenio y S/ 12,91 al paciente, y la
    liquidación del mes siguiente emite una nota de crédito de S/ 10,69 a la
    aseguradora.

!!! note "Nota"
    Con redondeo de efectivo en la caja, se redondea solo el comprobante del
    paciente: lo cobrado con el convenio no entra en el ajuste.
