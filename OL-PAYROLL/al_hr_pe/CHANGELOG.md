Historial de cambios — Planillas Perú - Núcleo (AL)
===================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

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
