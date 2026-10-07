Historial de cambios — Planillas Perú - Beneficios sociales (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_benefits.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 16.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 15.20261008 — 08/10/2026

- Fichas de quinta (afectos y excluidos), utilidades y saldo de vacaciones con el trabajador como título y bloques rotulados (proyección anual / impuesto y retenciones, trabajador / cálculo, saldo / días y montos).

## 14.20261008 — 08/10/2026

- Formularios de CTS, gratificación, vacaciones, liquidación, utilidades y quincena con bloques rotulados («Periodo» a la izquierda; depósito, cálculo o factores a la derecha) y el año como lista desplegable.
- Vistas reordenadas: título en CTS, gratificación, vacaciones, liquidación, utilidades, quinta, adelantos y préstamos; las líneas de CTS, gratificación y vacaciones van con el trabajador como título y su cálculo en pestañas (remuneración computable, cálculo, depósito o aportes); subsidios y préstamos con sus tablas en pestañas; estados con insignia de color; años sin separador de miles. Nombre legible en todas las líneas (ya no «hr.cts.line,5»). «Devengue de vacaciones» pasa a «Planilla PE» de la nómina.
- El nombre de los lotes de CTS, gratificación, vacaciones, liquidación, utilidades y quinta (el que propone el sistema) ya no se puede editar a mano. El botón de detalle de las líneas de CTS, gratificación y vacaciones pasa al final de la fila, como en el resto de listas, y en la quincena «Volver a borrador» va al final de la barra, junto a «Reabrir quincena».

## 13.20261007 — 07/10/2026

- Adelanto quincenal con estructura propia («Adelanto quincenal»): adelanta el porcentaje configurado del sueldo o los días trabajados, más la asignación familiar si se pide, menos los adelantos y préstamos de quincena. Antes la quincena usaba la estructura general y calculaba EsSalud, AFP y 5ta de medio mes que la boleta mensual volvía a calcular. Los aportes van en el mes; solo se descuentan AFP/ONP a cuenta si la compañía lo activó.

## 12.20261007 — 07/10/2026

- Corregido: «Vacaciones pagadas» no recibía su código T21 23 en las bases nuevas de Odoo 19 (el tipo cambió de identificador).

## 11.20261007 — 07/10/2026

- Sin doble registro de ausencias: el tipo de ausencia lleva su código de suspensión PLAME (T21) y, al aprobarse, la ausencia crea sola sus suspensiones, una por mes. De ellas leen la liquidación vacacional, los subsidios y el .snl. Si se rechaza o cancela, desaparecen. Las vacaciones pagadas vienen configuradas con el código 23.

## 10.20261007 — 07/10/2026

- La indemnización vacacional de la liquidación va a la boleta por su propio concepto (INDVAC, PLAME 0504) y tributa como renta de 5ta extraordinaria.

## 9.20261007 — 07/10/2026

- Liquidación: indemnización vacacional (D.Leg. 713, art. 23) por vacaciones vencidas no gozadas; suma al neto sin pagar aportes y va a la boleta como indemnización.
- Cese en mayo antes del depósito: la liquidación paga la CTS de noviembre a abril, que antes no pagaba nadie. Si ya se depositó, no se duplica.
- 5ta: al cese o en diciembre, la retención en exceso se devuelve en la boleta en vez de perderse en «excluidos».
- Adelantos y préstamos: importarlos dos veces suma todo lo del periodo; antes la segunda importación pisaba la primera, que quedaba marcada como pagada sin descontarse.
- Corregido: «Recalcular» una línea de vacaciones de la liquidación cambiaba el importe (los días se guardaban sin decimales).

## 8.20261007 — 07/10/2026

- Renta de 5ta: ya no suma una gratificación de julio que el trabajador no cobra; las gratificaciones se proyectan en proporción a los meses completos desde el ingreso.
- Renta de 5ta en el mes del cese: sin proyección de meses futuros ni gratificaciones, con divisor 1 (como la regularización de diciembre).
- Liquidación: las vacaciones adelantadas se descuentan en la boleta (antes solo se restaban en el total de la línea).

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
