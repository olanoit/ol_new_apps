# Planillas Perú — Beneficios sociales

CTS, gratificaciones, renta de 5ta, liquidación de cese, provisiones,
subsidios, utilidades, vacaciones, préstamos y quincena, sobre un único
motor de remuneración computable.

> **Versión** 4.20260722 · **Depende de** `al_hr_pe` · **Licencia** LGPL-3

---

## 1. Qué incluye

| Beneficio | Qué resuelve |
|---|---|
| **CTS** | Depósitos semestrales mayo–octubre y noviembre–abril, con reserva para quien lleva menos de un mes y descuento del exceso de descanso médico |
| **Gratificaciones** | Fiestas Patrias y Navidad, con la bonificación extraordinaria de EsSalud (Ley 29351) |
| **Renta de 5ta** | Proyección anual por tramos de UIT, reproyección del art. 40 y excluidos |
| **Liquidación de cese** | Truncos de CTS, gratificación y vacaciones más conceptos extra |
| **Provisiones** | Devengo mensual de CTS, gratificación y vacaciones |
| **Subsidios** | Enfermedad —los 20 días a cargo del empleador— y maternidad, con reparto mensual |
| **Utilidades** | Reparto del D.L. 892: 50 % por días trabajados, 50 % por remuneraciones |
| **Adelantos y préstamos** | Cuotas iguales a fin de mes, descontadas en la boleta |
| **Quincena** | Boletas quincenales y su descuento en la mensual |
| **Vacaciones** | Récord vacacional, descansos y adelantos |

## 2. El motor de remuneración computable

Casi ningún beneficio peruano se calcula sobre el sueldo, sino sobre la
**remuneración computable**: lo fijo se suma y lo variable se promedia —
pero solo si esa variable apareció las veces suficientes en el periodo.

> **La regla de las tres apariciones.** Una comisión pagada dos meses de
> seis no entra en el promedio; la pagada tres, sí.

Está implementada **una vez**, en el motor, y la reutilizan la CTS, la
gratificación y la liquidación de cese: si el criterio cambia, cambia en
un solo sitio. El motor vive en los parámetros principales de la
compañía, así que dos empresas de la misma base pueden tener criterios
distintos sin tocar código.

## 3. Cómo se usa, paso a paso

Todos los beneficios siguen el mismo circuito, y eso es deliberado:

1. **Configurar el motor una vez** — *Planillas → Configuración →
   Parámetros principales*. Qué conceptos son fijos, cuáles variables y
   qué reglas entran en la remuneración computable de cada beneficio.
2. **Crear el documento del periodo** — *Planillas → Beneficios
   sociales*. Un registro por semestre de CTS, por gratificación, por
   reparto de utilidades, con su periodo y su compañía.
3. **Calcular** — genera el detalle trabajador por trabajador con la
   base, el tiempo computable y el importe. Recalcular **reemplaza** el
   detalle; no acumula.
4. **Revisar antes de confirmar** — cada línea muestra de dónde sale su
   importe. Es el momento de detectar al trabajador con un dato laboral
   incompleto, no después de pagar.
5. **Confirmar y pagar** — confirmado, el documento queda cerrado a
   cambios. De aquí salen el asiento contable (con `al_hr_pe_account`) y
   el archivo de pago masivo (con `al_hr_pe_reports`).

## 4. Detalles que suelen dar problemas

**CTS de quien lleva poco tiempo.** Al trabajador con menos de un mes no
se le deposita: su importe se reserva y se acumula al semestre siguiente.

**Exceso de descanso médico.** Los días de subsidio que superan el límite
descuentan tiempo computable de la CTS. Se calcula solo, a partir de los
subsidios registrados.

**Reproyección del art. 40.** Cuando aparece un ingreso extraordinario, la
renta de 5ta se reproyecta desde ese mes en vez de rehacer el año entero.

**Quincena que no se paga dos veces.** La boleta quincenal descuenta su
propio importe en la mensual, con la regla configurada en los parámetros.

## 5. Tests

```bash
odoo-bin -d <bd> -u al_hr_pe_benefits --test-enable \
         --test-tags /al_hr_pe_benefits
```
