---
modulos: [al_construction_planner]
---

# Adicionales, deductivos y dependencias

Después de aprobado el plan, la obra cambia: el cliente pide otro color, quita
un mueble o hay que rehacer algo; y hay etapas que no pueden empezar hasta que
un tercero cumpla (la encimera, los electrodomésticos, el frente liberado).
Ambas cosas se registran en **Ejecución ‣ Cambios** (P-32).

## Adicionales y deductivos

Un **cambio de obra** tiene su obra, su plan (el vigente, por defecto), el
contrato con el cliente si se cobra, quién lo pide (cliente, interno o
contrata), el motivo y su **tipo**:

| Tipo | Líneas |
|---|---|
| Adicional | Solo cantidades positivas |
| Deductivo | Solo cantidades negativas |
| Neto | Agrega y quita |
| Rehacer | Solo agrega; es costo propio y no se cobra al cliente |

Cada línea dice el nivel (unidad, ambiente, mueble o módulo), el tipo de
recurso, la etapa, el producto o la actividad, la cantidad y el costo
unitario.

### Precio al cliente

La **regla de precio** se propone según el estado de la unidad (el del módulo
más avanzado del nivel) y se puede cambiar:

| Estado de la unidad | Regla propuesta | Precio al cliente |
|---|---|---|
| Planificado o en producción | Diferencia de precio | Cantidad × lo que cuesta de más (o de menos) la pieza nueva |
| Producido o en obra | Pieza suelta | Cantidad × precio de la pieza |
| Instalado o entregado | Reinstalación | Cantidad × precio de la pieza + desmontaje y reinstalación |
| — | Precio nuevo | Cantidad × el precio que se pacte |

### Aprobar

**Aprobar y llevar al plan** (jefatura de planificación) crea las líneas en el
plan vigente con origen **Cambio** y la referencia del cambio, les pone las
[reglas analíticas](analytic_budget.md) y suma su costo al presupuesto
analítico del plan, en la línea de su misma combinación de cuentas. Un cambio
aprobado no se anula: se registra otro al revés. El contrato muestra la suma de
sus cambios aprobados en **Adicionales y deductivos**.

## Dependencias de terceros

Una **dependencia** es lo que un tercero debe entregar antes de una etapa:

- encimera, electrodomésticos, frente liberado, piloto aprobado o
  instalaciones (eléctricas y sanitarias);
- su responsable (el cliente, su proveedor u otra contrata);
- los niveles que espera (agrupadores, pisos, unidades o ambientes; vacío,
  toda la obra), la **etapa que bloquea** y la **fecha prevista**.

Mientras está **abierta**:

- la etapa de esos ambientes **no admite avances**;
- el cronograma la muestra **rayada en rojo** con el aviso de la dependencia;
- la etapa no se puede mover a una fecha anterior o igual a la prevista.

**Mover cronograma** corre las etapas bloqueadas al día hábil siguiente a la
fecha prevista, con sus días hábiles, y empuja las siguientes del ambiente.
**Cumplida** la libera. El botón **Etapas bloqueadas** las lista.

## Avances repetidos

Los avances tienen el aviso **Posible duplicado** cuando hay otro avance
vigente del mismo nivel, actividad, tramo y fecha, y el filtro **Posibles
duplicados** en **Avances**: se revisan antes de liquidar para no pagar dos
veces lo mismo.
