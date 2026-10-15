---
modulos: [al_construction_planner, al_construction_planner_budget]
---

# Tramos, analítica y presupuesto

El presupuesto de la obra se controla por **obra › etapa › partida**: cuánto se
planificó y cuánto se gastó en producción, armado, instalación y acabado, y
dentro de cada etapa en mano de obra variable, tableros, accesorios…

## Producto de servicio por actividad

En **Configuración ‣ Plan de obra ‣ Actividades de obra**, la acción **Crear
productos de servicio** crea, para cada actividad sin producto, un servicio con
su nombre, su código y su unidad, en la categoría de su etapa (producción y
armado en la de armado; instalación y acabado en la de instalación). Las
categorías se eligen en los **Ajustes** del planificador. Las OC de servicio y
las facturas de las contratas usan ese producto.

## Pases y tramos

Algunas actividades se pagan por partes: una entrega se paga 45 % al limpiar
y 50 % al dar el acabado. En la actividad, pestaña **Tramos de pago**, cada tramo tiene
su nombre y su porcentaje. Si los porcentajes no suman 100 la actividad lo
avisa, pero no lo impide (por ejemplo, un repaso R1 de 10 % sobre el 100 %).

Con tramos, **Registrar avance** pide el tramo: cada unidad del tramo vale su
porcentaje del pago (**unidades equivalentes**) y el saldo se controla por
tramo, así que cada tramo admite lo planificado de la línea.

## Reglas analíticas

En **Configuración ‣ Plan de obra ‣ Reglas analíticas** se dice qué cuentas
analíticas lleva cada línea del plan según su **tipo de recurso**, su **etapa**
y la **categoría del producto**:

- **Cuenta de etapa** (plan analítico de etapas: PRD, INS…).
- **Cuenta de partida** (plan de partidas: MODV, MP-TAB, MP-ACC…).
- **Cuenta de área**, si se usa.

Para cada columna gana la regla **más específica** que tenga esa cuenta: una
regla de material de producción en la categoría Tableros gana a una de
cualquier material. Así una línea puede tomar la etapa de una regla y la
partida de otra.

**Generar plan** pone las cuentas a cada línea (además de la cuenta de la
obra); **Aplicar reglas analíticas** las vuelve a poner en un plan en
borrador. Los requerimientos y compras que nacen del plan heredan su
distribución.

## Presupuesto por obra › etapa › partida

Al aprobar el plan, el presupuesto analítico tiene **una línea por combinación
de cuentas** (obra + etapa + partida), con lo planificado de esas líneas. Así
el informe de presupuestos de Odoo compara lo planificado con lo real por etapa
y partida.

## Lo real con su etapa y su partida

Odoo pone solo la cuenta de la obra en algunos apuntes. En las obras, el
planificador completa las columnas vacías con las reglas:

| Apunte | Etapa que toma |
|---|---|
| Consumo de una orden de fabricación | Producción |
| Consumo de material en obra | Instalación |
| Factura de una contrata (producto de una actividad) | La de la actividad |

La partida sale de la regla del tipo de recurso y de la categoría del
producto. Lo que ya trae una cuenta en esa columna no se cambia.
