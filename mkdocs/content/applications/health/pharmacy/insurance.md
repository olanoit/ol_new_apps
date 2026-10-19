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
    Paracetamol S/ 10 y losartán S/ 20, más IGV: S/ 35,40. Con 80 % de
    cobertura y S/ 5 de copago, el convenio cubre S/ 19,24. El paciente paga
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

!!! warning "Importante"
    Una devolución en la caja de una venta con convenio devuelve el total al
    paciente: la parte de la aseguradora se corrige con una nota de crédito a
    su factura.
