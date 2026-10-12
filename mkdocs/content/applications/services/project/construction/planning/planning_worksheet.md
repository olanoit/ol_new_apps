---
modulos: [al_construction_planner, al_construction_planner_spreadsheet]
---

# Pestaña Planificación y hoja de trabajo

## Pestaña Planificación de la obra

La ficha de la obra (**Obras ‣ Obras**) tiene la pestaña **Planificación**
con los accesos al **Árbol de recursos**, al **Cronograma** y a los planes, y
tres márgenes, cada uno con su ingreso, su costo, su margen y su porcentaje:

| Margen | Ingreso | Costo |
|---|---|---|
| Planificado | Contratos de obra con sus cambios aprobados o, sin contratos, la orden de venta de la obra (sin impuestos) | Líneas del plan vigente |
| Devengado | Valorizaciones confirmadas por el cliente o facturadas | Real de las líneas del plan: consumido, recibido en OC de servicio y horas |
| Contable | Apuntes analíticos positivos de la cuenta de la obra | Apuntes analíticos negativos de la cuenta de la obra |

Un margen negativo se muestra en rojo.

## Hoja de trabajo del maestro

Con **Documentos** y **Hoja de cálculo** (Odoo Enterprise) se instala solo
**Hoja de trabajo del planificador de obra**
(`al_construction_planner_spreadsheet`). El botón **Hoja de trabajo** de la
pestaña Planificación crea, la primera vez, la hoja de la obra en Documentos
y la abre:

- una pestaña por hoja del [maestro](import_master.md) (CATALOGO,
  TIPOLOGIAS, MUEBLES, MODULOS, ACTIVIDADES, BOM, ARBOL, ETO, VARIANTES…) con
  sus encabezados;
- una pestaña **REFERENCIAS** con listas de Odoo que se actualizan solas: las
  actividades de obra y las tipologías de la obra, para copiar códigos sin
  salir de la hoja.

La hoja se trabaja entre varios a la vez, guarda su historial y admite
fórmulas. Las demás veces, el botón abre la misma hoja.

### Enviar al planificador

En la hoja, **Archivo ‣ Enviar al planificador** lleva los valores de las
pestañas del maestro (no las demás) al asistente **Importar maestro y ETO** de
la obra. El asistente muestra lo que creará o actualizará, las advertencias y
los errores con su hoja y su fila, sin escribir nada; **Importar** lo aplica.
Se puede enviar las veces que haga falta: no duplica.
