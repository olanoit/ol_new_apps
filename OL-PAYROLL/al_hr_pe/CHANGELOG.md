Historial de cambios — Planillas Perú - Núcleo (AL)
===================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 28.20261008 — 08/10/2026

- Configuración principal de planillas: una por compañía, creada sola (ya no corta ningún flujo) y editable en Ajustes ▸ Nómina ▸ Perú (SCTR, representante y firma); el menú abre la de la compañía activa.
- Asistentes con _check_company_auto y check_company.

## 27.20261008 — 08/10/2026

- Botones con la convención de Odoo (action_<verbo>): exportadores PLAME/AFPNet/resumen como action_export_*. Migración que renombra los botones en las vistas guardadas para que la actualización no falle.

## 26.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 25.20261008 — 08/10/2026

- Nuevo widget «year_selection»: el año se elige de una lista que va del próximo año hacia atrás y avanza sola cada enero (sin catálogo ni cron; el campo sigue siendo entero). Se usa en la UIT (15 años atrás) y en los beneficios.
- Empleado: página «Planilla PE» con pestañas internas (Identificación, T-Registro con E17/E29/E30, Domicilio), en vez de repartir los datos por «Personal» y «Nómina»; los demás módulos de planillas cuelgan sus pestañas de ahí. Nómina: «Planilla PE ▸ Cálculo». Nombres legibles (UIT, RMV, suspensiones, estudios) y títulos en periodos y parámetros.

## 24.20261007 — 07/10/2026

- Tasas AFP automáticas desde la SBS: un proceso diario lee la tabla oficial de comisiones y primas (comisión sobre flujo, prima de seguros, aporte y remuneración máxima asegurable) y actualiza las AFP; también hay un botón «Actualizar tasas desde la SBS» en Afiliaciones. Si la página no responde o la tabla no cuadra, no se toca nada. La remuneración máxima asegurable pasa a S/ 12 732,70 (octubre-diciembre 2026).

## 23.20261007 — 07/10/2026

- Resumen de planilla en Excel desde el lote (menú del lote ▸ Resumen de planilla): una fila por trabajador y una columna por concepto, con totales, y una hoja por concepto con su código SUNAT y categoría para conciliar con contabilidad.

## 22.20261007 — 07/10/2026

- SCTR (D.S. 003-98-SA) en la estructura general: reglas de salud y pensión para quien tiene la cobertura marcada, con tasas y entidad contratada en Parámetros principales ▸ SCTR. El PLAME declara el código de la entidad: salud 0806 (EsSalud) u 0810 (EPS), pensión 0813 (ONP) u 0814 (aseguradora).

## 21.20261007 — 07/10/2026

- Nueva regla «Indemnización vacacional» (INDVAC, PLAME 0504): llega al neto y a la renta extraordinaria de 5ta, sin pagar aportes.
- Corregido: la indemnización genérica (INDEM) se declaraba en el PLAME como CTS (0904); ahora usa 0501, indemnización por despido.

## 20.20261007 — 07/10/2026

- PLAME: el tipo de documento sale con dos dígitos (01 = DNI) en el .rem, el .jor y el .toc; antes salía «1» y el PLAME lo rechazaba.
- PLAME .toc (estructura 26): declara el seguro +Vida de EsSalud (nuevo indicador en el contrato) y la condición de domiciliado de cada trabajador del mes. Antes marcaba como +Vida a quien tenía Seguro Vida Ley, que es otro seguro.
- AFPnet: el correlativo empieza en 1 y no tiene huecos (antes empezaba en 0 y saltaba a los trabajadores de ONP).
- T-Registro: los regímenes pensionarios y de salud traen su código SUNAT (tablas 11 y 32) y la validación avisa si falta; antes la estructura 11 salía sin régimen.
- Las reglas salariales redondean con el criterio SUNAT (2,675 → 2,68), no con el redondeo al par de Python.
- Corregido: la indemnización (input INDEM) aparecía en la boleta pero no llegaba al neto a pagar.
- Devolución de 5ta: si al cese o en diciembre se retuvo de más, la boleta devuelve el exceso; en el PLAME esa retención se declara en 0.

## 19.20261007 — 07/10/2026

- Sobretasa nocturna (nueva regla NOCT y tipo de entrada «Horas trabajo nocturno»): quien trabaja de noche no cobra menos de la RMV + 35 % (D.S. 007-2002-TR, art. 8), en proporción a sus horas nocturnas. Entra en el básico del mes, así que la toman AFP, ONP, EsSalud y 5ta. Microempresa, practicantes y construcción civil quedan fuera.

## 18.20261007 — 07/10/2026

- Remuneración Mínima Vital por fecha de vigencia (nueva tabla «RMV»): cada boleta toma la vigente al cierre de su periodo. Incluye S/ 1 230 desde el 01/10/2026 (D.S. 015-2026-TR); antes era un único valor de S/ 1 130 por compañía. La asignación familiar sale del 10 % de esa RMV.
- Tasas del SPP 2026: prima de seguros 1,37 % (antes 1,70 %) y remuneración máxima asegurable S/ 12 672,65; la SBS la actualiza cada trimestre.
- Corregido: los códigos de excepción y de tipo de trabajo de AFPnet tenían rótulos de jornada; marcar a un trabajador a tiempo parcial con «I» anulaba sus aportes. Ahora siguen la guía de AFPnet y el pensionista por jubilación tampoco aporta.
- La asignación familiar se paga también en un mes completo de vacaciones (la remuneración vacacional es la ordinaria); EsSalud y EPS aplican la base mínima de la RMV también con EPS; «mayor de 65» se mide al cierre del periodo de la boleta.
- El .jor del PLAME ya no resta dos veces vacaciones y subsidios, y declara horas y minutos sin truncar.

## 16.20260925 — 27/09/2026

- AFP y ONP se calculan por el tipo de afiliación y sus tasas, no por el nombre de la entidad: renombrar una AFP ya no deja su aporte en cero.
- El feriado o descanso laborado se paga doble (labor más sobretasa del 100 %, D.Leg. 713), además del sueldo del mes.
- Las horas extra ya no restan días de descanso: antes, cada 8 horas extra rebajaban el básico en un día.
- Los practicantes dejan de cobrar asignación familiar (no les corresponde por la Ley 25129).
- Récord vacacional: un periodo dentro de un mismo mes contaba los días como meses; ahora cuenta días.
- PLAME y AFPNet de un lote semanal (construcción civil) declaran el mes completo, con una sola línea por trabajador; «Sin régimen» ya no declara la comisión AFP (0601); los parámetros salen de la compañía del lote.
- Los archivos del T-Registro y de derechohabientes solo los puede descargar quien los generó: antes cualquier usuario interno podía abrirlos.
- Un usuario de RR. HH. sin permiso de nómina vuelve a poder abrir la ficha del empleado; los derechohabientes quedan para nómina.
- Los datos laborales peruanos de la versión del empleado quedan restringidos a Recursos Humanos.
- Una boleta ya validada o pagada conserva su asignación familiar aunque luego se registre un hijo.
- La situación de los derechohabientes y su derecho a asignación familiar se actualizan solos cada día.
- Importe en letras corregido: del 21 al 29 se escribe «VEINTI…» (antes «VENTI…») y 100 000 sale «CIEN MIL» (antes «CIENMIL»).

## 24/09/2026

- Los datos privados del trabajador (identificación PLAME, domicilio, T-Registro y estudios) se restringen a Recursos Humanos, en la ficha y en la definición de cada campo: sin esa restricción, un usuario interno sin permiso recibía un error de acceso al abrir un empleado y el TPV no llegaba a abrir.

## 14.20260901 — 16/09/2026

- UIT 2026 corregida a S/ 5.500 (D.S. N.° 301-2025-EF); venía con el valor de 2025. Al actualizar se corrige en la base si no se había cambiado a mano.

## 13.20260901 — 01/09/2026

- Instalación corregida en bases de datos nuevas.

## 11.20260816 — 18/08/2026

- Configuración ▸ Perú reorganizada en grupos; los catálogos SUNAT, juntos y con su número de tabla.

## 10.20260803 — 03/08/2026

- Periodos semanales colgados del mes y periodo PLAME en el lote.

## 9.20260802 — 02/08/2026

- Derechohabientes con asignación familiar por edad y exportación para la macro de SUNAT.
- Carga masiva del T-Registro (E04, E05, E11, E17, E29 y E30) con validación previa.

## 5.20260722 — 26/07/2026

- Arreglos hallados en las pruebas funcionales de la planilla.

## 4.20260722 — 25/07/2026

- Primera versión para Odoo 19. Ficha laboral en la versión del empleado, catálogos PLAME, reglas salariales y exportadores PLAME/AFPNet.
