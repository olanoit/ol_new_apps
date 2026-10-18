---
modulos: [al_pharmacy_prescription, al_pharmacy_pos, al_l10n_pe_prescriber_cmp]
---

# Receta y dispensación en la caja

## En la caja

1. Al tocar un producto **de marca** con equivalentes, la caja ofrece las
   **alternativas**: primero los genéricos en DCI y del más barato al más caro
   (Ley 32033). Elija el producto o mantenga el pedido.
2. Si el producto se vende **con receta**, la caja pide los datos: número,
   fecha, prescriptor, colegiatura y, si la venta no tiene cliente, el paciente.
    - Con el ajuste **Bloquear**, un químico farmacéutico puede pulsar
      **Autorizar sin receta (Q.F.)**; queda en el libro de ocurrencias.
    - Con **Solo avisar**, se puede **Continuar sin receta**.
    - Los productos controlados nunca admiten excepción.
3. Si quien atiende no es químico farmacéutico, la caja avisa (o bloquea, según
   el ajuste) y la venta queda en el libro de ocurrencias.
4. Elija la presentación y el lote (los disponibles, el que vence primero
   arriba).
5. Al cobrar, Odoo registra la **receta** y la **dispensación** de la venta.

!!! tip "Consejo"
    Active **Iniciar sesión con empleados** en el punto de venta: la caja sabe
    quién atiende y si es químico farmacéutico.

## Recetas

En **Farmacia ‣ Dispensación ‣ Recetas** están las recetas de la caja y las que
se registran a mano:

- **Tipo** (común o especial), **fecha** y **vigencia**; la receta vencida no
  se atiende.
- **Prescriptor** y **paciente**; **medicamentos** por producto o por principio
  activo, con posología y duración.
- **Dispensaciones**: lo entregado contra cada línea, con lote, químico
  farmacéutico y si fue una **alternativa**. Las entregas parciales dejan la
  receta **Dispensada en parte**.
- **Retención e imagen**: folio de la receta retenida y la imagen escaneada.

Desde la lista se imprimen el **Libro de recetas** y, en las dispensaciones, la
**Etiqueta de dispensación** (producto, laboratorio, lote, vencimiento y
posología) para la venta fraccionada.

## Prescriptores y pacientes

En **Farmacia ‣ Dispensación ‣ Prescriptores**, cada prescriptor lleva su
profesión, colegiatura, especialidad y estado. Para un médico, **Consultar en
el CMP** abre el portal «Conoce a tu médico» del Colegio Médico; tras buscarlo,
el químico farmacéutico pulsa **Verificado: hábil** o **Verificado: inhábil**.
Una receta de un prescriptor inhábil no se valida.

!!! note "Nota"
    El portal del Colegio Médico pide iniciar sesión y reCAPTCHA, por eso la
    verificación es manual.

En el paciente (pestaña **Farmacia**), el químico farmacéutico registra sus
alergias y condiciones crónicas.
