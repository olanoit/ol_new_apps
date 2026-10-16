---
modulos: [al_construction_planner, al_construction_attendance, al_construction_planner_subcontract]
---

# Portal de obra, sedes y marcación

Las contratas reportan su avance desde el celular, el personal marca su
ingreso en la tablet de la obra y el costo de la planilla llega a la obra, a
la etapa y a la partida que le corresponden.

## Portal de la contrata

El usuario de portal de una contrata (un contacto de la empresa de la
contrata) ve en **Mi cuenta ‣ Mis obras**:

| Código | Pantalla | Qué hace |
|---|---|---|
| P-23 | Mis obras y tareas | Las obras y actividades asignadas a su empresa, con lo planificado, lo ejecutado y el saldo. Solo ve lo de su empresa. |
| P-24 | Registrar avance | Por actividad: unidades por módulo o ambiente, fecha y **al menos una foto**. El celular agrega su ubicación. |
| P-25 | Mis avances y liquidaciones | Historial de avances con su estado (por validar, validado, rechazado) y las liquidaciones de su empresa con su pago. |
| P-26 | Parte diario de cuadrilla | Quién de su empresa marcó hoy, en qué sede, con ingreso, salida y observaciones. Lo agrega **Sedes, marcación y costo de personal de obra**. |

Las contratas de armado reportan igual que las de instalación: en **Registrar
avance** aparece una fila por módulo (Tarugo 1, Tornillo 1…) de cada ambiente,
y se escribe 1 por cada módulo armado.

El avance del portal entra **Por validar**, con origen *Portal*, la ubicación
y la distancia a la sede. Sus fotos quedan en el historial del mismo avance,
con la contrata como autor, junto con la evaluación del supervisor, la
validación o el rechazo (ver [el avance en su
formulario](contractors.md#el-avance-en-su-formulario)). El supervisor lo
valida o rechaza en **Ejecución ‣ Avance ‣ Avances por validar**, como
cualquier otro.

## Sedes de obra

El módulo **Sedes, marcación y costo de personal de obra**
(`al_construction_attendance`) se instala solo con el planificador y la
planilla de construcción civil. En **Configuración ‣ Plan de obra ‣ Sedes de
obra**, cada sede tiene:

- su **Tipo de sede**: **Obra** (de un proyecto: su costo de personal es de la
  obra) o **Planta** (producción central de la compañía, sin proyecto: su
  costo es de fabricación y llega a las obras con las órdenes de
  fabricación). Una sede de planta no se vincula a ninguna obra;
- su **obra** (solo las sedes de obra), **latitud**, **longitud** y **radio**
  (200 m por defecto);
- la **hora límite de ingreso** (7:50 por defecto);
- la **cuenta de etapa por defecto**: instalación en la obra, producción en la
  planta;
- el enlace del **quiosco**, con una clave propia.

### Crear la sede con la obra

En **Ajustes ‣ Planificación de obra**, active **Crear la sede de obra con la
obra** y escriba la **Latitud por defecto**, la **Longitud por defecto**, el
**Radio por defecto (m)** y la **Hora límite por defecto**. Al marcar un
proyecto como obra, se crea su sede con el nombre y la cuenta analítica de la
obra y esos valores, que luego se corrigen en la sede. Si la obra ya tiene una
sede, no se crea otra. Los dos perfiles de vertical dejan esta opción activa.

La marcación en la sede de la obra da los jornales ejecutados de las
[cuadrillas propias](control.md#cuadrillas-en-jornales).

## Quiosco de marcación

El quiosco es una página para la tablet de la obra, sin usuario: el personal
escribe su documento o su PIN y marca ingreso o salida (la segunda marcación
del día es la salida). Sirve para el personal propio y para el de las
contratas, y avisa en pantalla:

- **fuera de hora**, si el ingreso pasa la hora límite;
- **fuera del radio**, si la tablet está lejos de la sede;
- **SCTR vencido**, para el personal de contratas.

El personal de contratas (**Ejecución ‣ Asistencia ‣ Personal de contratas**)
se registra con su documento, su empresa y el vencimiento de su SCTR; no entra
a la planilla ni al T-Registro.

## Asistencia diaria

Una marcación con ubicación hecha desde la app o el quiosco de Odoo
(Asistencias), sin sede, toma la **sede más cercana** de la compañía; con ella
se calculan la distancia, si está fuera de rango y si llegó fuera de hora.

**Ejecución ‣ Asistencia** reúne la marcación del personal propio (con
distancia, fuera de rango y fuera de hora), la de las contratas y los
**avances sin asistencia**: avances de una contrata en un día en que nadie de
su empresa marcó en la obra, para revisarlos antes de pagar.

## Costo de personal por sede

Cuando la distribución analítica de la boleta lleva solo la cuenta de una
sede, se le suman la **etapa por defecto de la sede** y la partida de **mano de
obra fija** (MODF) de la compañía, que se elige en **Configuración ‣ Ajustes**. Así la
planilla queda en obra › etapa › partida y se compara con el
[presupuesto de la obra](analytic_budget.md).
