---
modulos: [al_l10n_pe_mrp_cost]
---

# Costeo de órdenes de fabricación

Odoo carga a cada orden el costo de sus componentes, las horas de máquina de
sus centros de producción y, con órdenes de trabajo, las horas de cada
empleado por su costo hora. Este módulo añade lo que pide un costeo real en el
Perú:

- un **costo hora** que sale de la planilla;
- el **tareo** importado desde Excel;
- un **cierre de costos** mensual que ajusta la mano de obra al costo real y
  reparte los **gastos indirectos de fabricación (CIF)**;
- el **costo de cada orden por elemento**.

## Configuración

1. Instale **Costeo de órdenes de fabricación** (`al_l10n_pe_mrp_cost`).
2. En los parámetros de la planilla, indique los **W.D. días laborados**: sus
   horas son las que dividen el costo de la planilla.
3. En **Fabricación ‣ Configuración ‣ Ajustes ‣ Costeo (Perú)**, elija la
   **contrapartida del ajuste de mano de obra** (71 Variación de la producción
   almacenada en el PCGE).
4. En **Fabricación ‣ Configuración ‣ Bolsas de CIF**, cree una bolsa por cada
   grupo de gastos indirectos:

    | Campo | Qué es |
    |---|---|
    | Cuentas | Prefijos de las cuentas cuyo saldo del mes forma la bolsa, por ejemplo `92` (destino de producción) o `63,65` |
    | Centros de costo | Opcional: solo la parte de los apuntes que va a esos centros de costo |
    | Base de reparto | Horas de las operaciones, cantidad, peso, volumen o costo directo |
    | Centros de producción | Opcional: solo se reparte entre las órdenes que pasaron por ellos |
    | Contrapartida | Cuenta que se abona al cargar la bolsa a las órdenes (71) |

5. Los productos terminados deben usar **costo promedio o PEPS**: el cierre
   ajusta su valor con un costo en destino.

## Costo hora desde la planilla

En **Fabricación ‣ Costeo ‣ Costo hora desde la planilla**, cree el periodo y
pulse **Calcular**. Para cada empleado con boletas calculadas en el periodo:

- **costo de planilla** = ingresos − descuentos afectos + aportes del
  empleador;
- **provisiones** = CTS, gratificación y vacaciones del lote, si están
  calculadas;
- **costo hora** = (costo de planilla + provisiones) ÷ horas laboradas.

**Aplicar a los empleados** deja ese costo hora en cada ficha: las órdenes del
mes siguiente lo usan al registrar tiempo. El cierre de costos toma el costo
hora aplicado de cada mes como costo real.

## Importar el tareo

**Fabricación ‣ Costeo ‣ Importar tareo** recibe un Excel con una fila de
títulos y estas columnas:

| Orden | Operación | Empleado | Fecha | Inicio | Horas |
|---|---|---|---|---|---|
| WH/MO/00012 | Corte | 45678912 | 15/01/2026 | 07:30 | 1,5 |

- **Operación**: nombre de la operación o de su centro de producción; vacía si
  la orden tiene una sola.
- **Empleado**: DNI, código de barras o nombre.
- **Inicio** es opcional (08:00 si falta).

Si una fila tiene un error, no se importa ninguna y el mensaje dice qué fila
corregir.

## Cierre de costos del mes

En **Fabricación ‣ Costeo ‣ Cierres de costos**, cree el mes y pulse
**Calcular**. Para las órdenes terminadas en el mes:

1. **Ajuste de mano de obra**: horas de cada registro de tiempo × (costo hora
   real del mes − costo hora con que se cargó). Si a un empleado le falta el
   costo hora del mes, se avisa y no se ajusta.
2. **CIF**: el saldo del mes de cada bolsa se reparte según su base. El
   redondeo va a la orden con más base.

Revise los cargos y pulse **Validar**: se crea y valida un **costo en destino**
sobre las órdenes, con su asiento (cuenta de existencias del producto contra la
contrapartida de cada concepto). Lo que ya se vendió pasa al costo de ventas.

**Ejemplo.** Una orden de 2 mesas consume 4 tableros a S/ 10 (S/ 40), usa 2 h
de una seccionadora a S/ 30 por hora (S/ 60) y 2 h de un operario cargado a
S/ 10 por hora (S/ 20). El costo hora real del mes es S/ 15: ajuste de
S/ 10. La bolsa de CIF del mes tiene S/ 300 y es la única orden: CIF S/ 300.

## Costo por elemento

**Fabricación ‣ Informes ‣ Costo por elemento** muestra el costo de cada orden
terminada por elemento: **material**, **máquina**, **mano de obra**, **ajuste de
mano de obra** y **CIF**, con sus horas. Agrupe por producto, centro de
producción o mes.

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Empleado sin costo hora aplicado en el mes | El cierre avisa y no ajusta sus horas | Aplicar el costo hora del mes y recalcular |
| Bolsa sin órdenes con base (por ejemplo, sin horas) | El cierre avisa y no la reparte | Revisar la base de reparto o los centros de producción |
| Producto terminado con costo estándar | El cierre no puede validarse | Cambiar su categoría a costo promedio o PEPS |
| Parámetros de la planilla sin días laborados | El costo hora no se calcula | Indicar los W.D. días laborados |

!!! info "Ver también"
    - [Costeo de piezas por medida](piece_costing.md)
    - [Fabricación en Odoo 19](https://www.odoo.com/documentation/19.0/es/applications/inventory_and_mrp/manufacturing.html)
