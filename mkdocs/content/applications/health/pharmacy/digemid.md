---
modulos: [al_l10n_pe_pharmacy_digemid]
---

# DIGEMID, genéricos e IGV

## Observatorio de precios

Las farmacias y boticas informan cada mes el precio de venta al público, con
IGV, de lo que tienen a la venta y en stock (Directiva 176-MINSA/DIGEMID).

1. En el producto indique el **Código DIGEMID** y la **Clase DIGEMID**: solo
   se informan medicamentos y biológicos. En el local indique el **Código de
   establecimiento**.
2. Cada alta o cambio de precio queda **Pendiente de informar** en **Farmacia ‣
   DIGEMID ‣ Precios para el Observatorio**.
3. **Farmacia ‣ DIGEMID ‣ Envíos al Observatorio** lleva un envío por local y
   mes:
    - La **primera carga del mes es completa**: toda la oferta en stock. Las
      siguientes llevan **solo los cambios** desde la última carga del local.
    - El archivo es un Excel con la hoja «Hoja1» y las columnas CodEstab,
      CodProd, Precio 1 (empaque) y Precio 2 (unidad), con IGV y 2 decimales.
    - Al informar queda la **fecha límite de rectificación** (7 días
      hábiles).
4. Desde el día del mes que indique en Ajustes (20 por defecto), si el local no
   ha informado, se crea el envío «Por informar» con una actividad para el
   director técnico.

!!! warning "Importante"
    Las columnas siguen la directiva vigente. Antes de la primera carga,
    compárelas con la plantilla que descarga el aplicativo del Observatorio.
    La fecha de rectificación no descuenta feriados.

## Genéricos esenciales (Ley 32033)

1. Importe el listado del MINSA en **Farmacia ‣ Configuración ‣ Catálogos ‣
   Listado de genéricos esenciales** (principio activo, concentración y forma).
2. **Farmacia ‣ DIGEMID ‣ Cumplimiento de genéricos** calcula, por local, en
   cuántos de los ítems que vende de marca tiene el genérico en DCI. El mínimo
   es el 30 %; las microempresas están exceptuadas (ajuste de la compañía).

## Lista de precios por DCI

**Farmacia ‣ DIGEMID ‣ Lista de precios por DCI** imprime los precios por
principio activo, de menor a mayor, con el aviso de los productos de empresas
vinculadas, para exhibir en el local.

## Cartel de empresas vinculadas

**Farmacia ‣ DIGEMID ‣ Cartel de empresas vinculadas** imprime el cartel A4 que
el local debe exhibir (DS 020-2024-SA, art. 32-B): los productos a la venta
marcados como de **Empresa vinculada**, con su principio activo y laboratorio,
y el recordatorio de que el cliente puede pedir el genérico en DCI.

## Reacciones adversas

En **Farmacia ‣ DIGEMID ‣ Reacciones adversas** registre cada sospecha: paciente
(iniciales), medicamento y lote, reacción, gravedad y desenlace. Odoo calcula
el plazo para notificarla en NotiMED (graves, 24 horas; las demás, los días del
ajuste) y la anota en el libro de ocurrencias. Al notificar, registre el código
y pulse **Marcar como notificada**.

## IGV exonerado

El **Régimen del IGV** del producto marca los medicamentos oncológicos y para
VIH/SIDA (Ley 27450) y para diabetes (Ley 28553); su impuesto de venta pasa al
de exonerados.

## Establecimiento

En **Farmacia ‣ Configuración ‣ Ajustes** registre el tipo (farmacia o botica),
la autorización sanitaria, si es microempresa y el plazo de las reacciones no
graves.
