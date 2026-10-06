Historial de cambios — Planillas Perú - Beneficios sociales (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_benefits.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20260816 — 27/09/2026

- CTS y gratificación: una falta ya no hace perder el mes entero; se descuenta una sola vez.
- El descanso médico cuenta como tiempo trabajado: en la gratificación completo y en la CTS hasta 60 días por año, sin volver a abonar en noviembre los días ya pagados en mayo.
- Recalcular una línea de CTS da el mismo importe que el cálculo: incluye el saldo del semestre anterior y el exceso de descanso médico.
- La asignación familiar de CTS, gratificación y vacaciones sigue a los derechohabientes, como la boleta.
- El promedio de variables exige el concepto en 3 meses distintos, no en 3 boletas.
- Liquidación de cese: las vacaciones truncas se cuentan desde el último aniversario; un cese en julio antes del día 15 cobra la gratificación de enero a junio.
- Récord vacacional: un cesado no recibe un año que no completó, y la pequeña y la microempresa acumulan 15 días al año.
- El recálculo de la liquidación vacacional ya no parte la tarifa a la mitad en la pequeña empresa.
- El bono extraordinario de la gratificación viene marcado por defecto; las faltas admiten medios días.
- Lo ya exportado no se puede recalcular ni exportar otra vez sin volver antes a borrador.
- El detalle histórico de las líneas de la liquidación de cese ya se abre sin error.
- La 5ta retiene con los divisores legales del Art. 40 (enero a marzo /12, abril /9, mayo a julio /8, agosto /5, setiembre a noviembre /4, diciembre /1) y cuenta ya las retenciones de abril y agosto.
- La retención por ingresos extraordinarios (utilidades, bonos) se calcula sola y se descuenta en la boleta.
- Utilidades: tope de 18 sueldos por trabajador (el exceso se muestra aparte, para FONDOEMPLEO); no toman borradores ni quincenas, y la línea marcada «no recalcular» ya no se duplica.
- Subsidios de un solo mes: se pagan los días correctos; el histórico de 12 meses solo usa boletas cerradas.
- Provisión de vacaciones: acumula desde el último aniversario; la asignación familiar sigue a los derechohabientes y la gratificación se provisiona también a quien trabaja menos de 4 horas.
- Préstamos: la última cuota cuadra al céntimo, y los adelantos sin concepto de boleta ya no se marcan como pagados.

## 16/09/2026

- Los tramos de 5ta generados con la UIT 2026 errónea (S/ 5.350) se recalculan con S/ 5.500 al actualizar; una tabla personalizada no se toca.

## 5.20260816 — 18/08/2026

- El menú Beneficios sociales se sitúa detrás de Recibos de nómina, en el orden del trabajo.

## 4.20260722 — 26/07/2026

- Parámetros de quincena (modo de cálculo, tasa, asignación familiar y aportes) que usan las reglas de adelanto quincenal.

## 3.20260722 — 25/07/2026

- Primera versión en Odoo 19: CTS, gratificaciones, renta de 5ta, liquidación de cese, provisiones, subsidios, utilidades, vacaciones, préstamos y quincena.
