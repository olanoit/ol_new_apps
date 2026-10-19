# Mejoras de proceso de la suite de farmacia

> 19/10/2026. Cómo trabajan las cadenas peruanas y qué le falta a la suite
> `al_pharmacy_*` para una botica. Fuentes y detalle en
> [`INVESTIGACION_CADENAS.md`](INVESTIGACION_CADENAS.md) (cadenas y DS
> 020-2024-SA) y [`INVESTIGACION.md`](INVESTIGACION.md) (normativa y
> software). Las entregas E0-E4 están en [`PLAN_FARMACIA.md`](PLAN_FARMACIA.md).

## 1. Qué hacen las cadenas y qué exige la norma

| Práctica | Quién | Estado en la suite |
|---|---|---|
| Cliente identificado por DNI, puntos y vales (Inkaclub: 1 punto por S/ 4, vale de S/ 5 cada 1 000 puntos) | Inkafarma, Mifarma | Falta. **Límite legal:** no se premia la compra de medicamentos con receta ni se incentiva al Q.F. |
| Recompra de pacientes crónicos (hipertensión, diabetes, tiroides) y adherencia | Cadenas internacionales; programas de apoyo al paciente | Falta |
| Reposición por consumo desde el centro de distribución; inventarios cíclicos; stock por temporada | InRetail, Boticas Perú | Parcial (reglas mín./máx. a mano) |
| Registro de la demanda perdida (lo que se pide y no hay) | Práctica de retail | Falta |
| Empresa vinculada: avisar al vender y cartel A4 visible (DS 020-2024-SA art. 32-B, 0,5 UIT por falta) | Obligatorio | Falta el aviso y el cartel |
| Venta fraccionada con envase rotulado: establecimiento, producto, laboratorio, concentración y vía, vencimiento y lote (art. 48) | Obligatorio | La etiqueta existe solo para dispensaciones con receta |
| Genéricos primero, 30 % de genéricos, receta, controlados, Observatorio, alertas | Obligatorio | Hecho (E2-E4) |

## 2. Mejoras que se desarrollan

### E5 · `al_pharmacy_care`: tratamientos crónicos y recompra

- **Tratamiento** por paciente y medicamento: DCI o producto, unidades por
  día, inicio, responsable y estado (activo, en pausa, terminado). Se crea a
  mano o desde una receta.
- **Cada compra** del paciente (TPV o pedido de venta) del producto o de un
  **equivalente** (misma clave de equivalencia) suma días cubiertos: fechas
  «cubierto hasta» y «próxima recompra» calculadas.
- **Recordatorio diario** (cron): actividad para el responsable y botón de
  **WhatsApp** con el mensaje listo; correo opcional.
- **Adherencia**: proporción de días cubiertos (PDC) de los últimos 180 días;
  menos de 80 % se marca como no adherente.
- **En la caja**: al elegir al cliente, aviso de los tratamientos que toca
  reponer, que se agregan al pedido con un clic.

### E6 · `al_pharmacy_replenishment`: faltantes y sugerido de compra

- **Faltante** desde la caja: el producto de la línea o un texto libre, con
  cantidad y motivo (sin stock, no lo trabajamos, precio); queda por local y
  cajero. Análisis por producto y local.
- **Sugerido de compra** por local: venta diaria promedio del periodo ×
  días de cobertura + faltantes − stock − lo que está por llegar. Crea las
  solicitudes de presupuesto agrupadas por proveedor o el traslado desde el
  almacén central, y marca los faltantes atendidos.

### E7 · Cumplimiento en la caja (`al_pharmacy_pos`, `al_l10n_pe_pharmacy_digemid`)

- **Empresa vinculada**: aviso al agregar el producto en el TPV, leyenda en
  el ticket y **cartel A4** imprimible con los productos de empresas
  vinculadas del local.
- **Etiqueta de fraccionado** desde la orden del TPV para las líneas
  vendidas por unidad o blíster: los seis datos del art. 48 con el lote
  vendido.

### E8 · `al_pharmacy_loyalty`: fidelización por DNI dentro de la norma

- Programa de puntos de Odoo (`loyalty`, `pos_loyalty`) con el cliente
  identificado por DNI.
- **Los medicamentos con receta y los controlados no suman puntos ni reciben
  recompensas**, aunque la regla del programa no los excluya: se filtran en
  el cálculo (TPV y pedido de venta).
- Datos de ejemplo: «Club de Salud» (1 punto por S/ 4, vale de S/ 5 por
  1 000 puntos), parecido a Inkaclub.

## 3. Siguientes etapas (no incluidas)

1. `al_pharmacy_website`: genéricos primero también en la web (art. 49),
   receta subida por el cliente, validación del Q.F., recojo en tienda y
   reparto con cadena de frío.
2. `al_pharmacy_insurance`: convenios con empresas y EPS (cobertura, copago,
   topes y cuenta por cobrar a la aseguradora).
3. Precio por vencer: descuento automático en lotes cercanos al vencimiento
   y canje con la droguería.
4. Servicios complementarios (presión, glucosa, inyectables) en un área
   propia: la lista oficial de servicios permitidos está por verificar; la
   toma de muestras y la consulta médica están prohibidas en la botica.
