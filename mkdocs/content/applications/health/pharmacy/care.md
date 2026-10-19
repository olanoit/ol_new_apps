---
modulos: [al_pharmacy_care]
---

# Tratamientos crónicos y recompra

La venta a pacientes con hipertensión, diabetes o tiroides se repite cada mes,
y es fácil perderla: al paciente se le acaba el tratamiento y nadie le avisa.
Con este módulo la botica registra el tratamiento, sabe hasta cuándo está
cubierto el paciente y le recuerda la recompra a tiempo.

## Crear un tratamiento

- **Desde la receta**: en **Farmacia ‣ Dispensación ‣ Recetas**, abra la receta
  y pulse **Crear tratamientos** (uno por medicamento; no duplica los activos).
- **A mano**: **Farmacia ‣ Dispensación ‣ Tratamientos crónicos ‣ Nuevo**.

Indique el paciente, el medicamento, las **unidades por día**, la fecha de
inicio y el **responsable** (quien hace el seguimiento).

## Días cubiertos

Cada compra del paciente suma días de tratamiento: unidades compradas ÷
unidades por día. Cuentan las ventas pagadas de la caja y los pedidos de venta
confirmados, del medicamento o de un **equivalente** (mismo principio activo,
concentración y forma). Las devoluciones restan.

| Dato | Qué es |
|---|---|
| Cubierto hasta | Día en que se le acaba el medicamento |
| Próxima recompra | Cubierto hasta menos los días de aviso de la compañía |
| Estado de recompra | Sin compras, cubierto, por reponer o atrasado |
| Adherencia (PDC) | Días cubiertos entre los días del tratamiento en los últimos 180; con menos de 80 % el paciente es **no adherente** |

!!! example "Ejemplo"
    Losartán 50 mg, 1 tableta al día. Rosa compra 30 tabletas el 1 de octubre:
    queda cubierta hasta el 31. Con 5 días de aviso, el 26 el responsable
    recibe la actividad **Recompra de tratamiento**.

## Recordatorio

- Cada día, Odoo crea la actividad **Recompra de tratamiento** para el
  responsable de los tratamientos por reponer.
- En el tratamiento, el botón **WhatsApp** abre el chat del paciente con el
  mensaje listo y lo anota en el historial.
- Si la compañía lo activa, también envía un correo al paciente.

Los filtros **Por reponer**, **Atrasados** y **No adherentes** de la lista
ordenan el trabajo del día.

## En la caja

Al elegir al cliente, si tiene tratamientos por reponer o atrasados, la caja
lo avisa y **Agregar al pedido** los suma con el flujo normal de farmacia
(alternativas, receta y presentación). El aviso solo muestra el medicamento y
la fecha: los datos de salud siguen siendo del químico farmacéutico.

## Configuración

En **Farmacia ‣ Configuración ‣ Ajustes ‣ Recompra de tratamientos crónicos**:

- **Días de aviso** antes de que se acabe el tratamiento (5 por defecto).
- **Enviar correo al paciente** con el recordatorio.
