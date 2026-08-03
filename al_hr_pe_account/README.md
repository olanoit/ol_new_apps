# Planillas Perú — Contabilización

El asiento de la planilla y el de cada beneficio social, con
previsualización, ajuste por redondeo y distribución analítica opcional.

> **Versión** 2.20260722 · **Depende de** `al_hr_pe_benefits`,
> `hr_payroll_account` · **Licencia** LGPL-3

---

## 1. Qué incluye

* **Asiento de planilla por lote**: agrupa las líneas de las boletas en
  cargos y abonos por la cuenta de cada regla, con el detalle por
  trabajador que Odoo ya soporta de forma nativa.
* **Bloque AFP por afiliación**: las administradoras se separan por la
  cuenta de su afiliación, configurable por compañía.
* **Asientos de beneficios sociales**: CTS, gratificación, liquidación de
  cese y provisiones.
* **Distribución analítica opcional**, activable por compañía, con el
  campo nativo de Odoo. Prioridad: la regla salarial sobre la ficha del
  trabajador.

## 2. Es opt-in, y por una razón

Contabilizar la planilla es una decisión de cada empresa. El asiento **no
se genera solo** al validar: se pide, se previsualiza y se ajusta antes de
crearse. El asistente muestra el asiento completo, con su descuadre por
redondeo si lo hay, y permite corregirlo antes de confirmar.

> El redondeo **siempre** aparece en planillas de cierto tamaño: son
> cientos de importes redondeados a dos decimales. Ocultarlo obligaría a
> cuadrar a mano después; mostrarlo con su cuenta de ajuste lo resuelve en
> el momento.

## 3. Cómo se usa, paso a paso

1. **Configurar las cuentas** — *Parámetros principales → Contabilidad
   PE*: cuentas de las reglas, de las afiliaciones AFP, de cada beneficio
   social y la de ajuste por redondeo.
2. **Decidir si se quiere analítica** — al activarla, las líneas llevan la
   distribución que corresponda: la de la regla salarial si la tiene, la
   del trabajador en otro caso.
3. **Generar el asiento del lote** — se previsualiza, se ajusta el
   redondeo si hace falta y se confirma. Queda enlazado al lote.
4. **Generar los asientos de beneficios** — mismo circuito para CTS,
   gratificaciones, liquidaciones y provisiones.

## 4. Qué se hizo distinto

**Por ORM, no por SQL.** La versión anterior agregaba con una vista SQL y
cuatro variantes. Aquí se agrupa con el ORM: multicompañía, permisos y
auditoría funcionan sin nada especial.

**El detalle por trabajador es nativo.** Odoo ya sabe llevar el empleado
en la línea del asiento; no hacía falta un modelo propio.

**La analítica es la de Odoo.** Se usa el campo nativo con su reparto por
porcentajes; desaparece el modelo propio de distribución que había antes.

## 5. Tests

```bash
odoo-bin -d <bd> -u al_hr_pe_account --test-enable \
         --test-tags /al_hr_pe_account
```
