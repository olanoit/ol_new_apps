Historial de cambios — Planillas Perú - Documentos y bancos (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_reports.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 14.20261008 — 08/10/2026

- Certificado de quinta: el año se elige de una lista.
- La plantilla de contrato del trabajador pasa a «Planilla PE ▸ Contrato de trabajo»; título en la plantilla; nombre legible en las líneas de pago masivo; estados con insignia.

## 13.20261007 — 07/10/2026

- Opción para cifrar la boleta enviada por correo con el número de documento del trabajador (Parámetros principales ▸ Envío de boletas), como en v18. La impresión no cambia.

## 12.20261007 — 07/10/2026

- El enlace de confirmación de la boleta caduca a los 90 días del envío; reenviar la boleta lo renueva.

## 11.20261007 — 07/10/2026

- Certificado de 5ta: el impuesto a la renta se calcula con la escala progresiva sobre la renta imponible (antes copiaba la retención) y el saldo por regularizar muestra la diferencia real, también con retenciones de otros empleadores.

## 10.20261007 — 07/10/2026

- TXT bancarios: Interbank en dólares ya no multiplica el total de cabecera; los haberes con cuenta de cargo en otra moneda se convierten a la fecha de pago; BBVA CTS usa el tipo de proceso configurado; el checksum de BCP CTS cuenta solo las cuentas del archivo; Scotiabank limpia los nombres antes de ajustarlos, usa el mismo tipo de documento en CTS y valida cuentas de 10 dígitos sin guiones.
- Una boleta con neto negativo (adelanto o préstamo mayor que el ingreso) ya se puede imprimir y enviar.

## 9.20260925 — 27/09/2026

- El TXT bancario solo paga boletas validadas o pagadas, no se puede generar con el lote aún abierto y deja fuera las cuentas en una moneda distinta a la de la cuenta de cargo.
- La cabecera del TXT cuenta solo a los trabajadores que se pagan, así el banco no rechaza el archivo cuando alguien tiene neto cero; generar de nuevo reemplaza el archivo anterior.
- El aviso tras generar los pagos lista también a quienes tienen banco sin diario de pago masivo.
- Generar el TXT, recargar líneas y finalizar quedan para el responsable de nómina.
- El enlace del correo abre una página con el botón «Confirmar recepción»: la boleta ya no se da por recibida solo porque el correo o su antivirus abrieran el enlace.
- Las plantillas de contrato se limpian de código peligroso al guardarlas; los campos {{...}} y los estilos se mantienen. El contrato se imprime solo desde el botón de la ficha.
- El envío masivo de boletas sigue con las demás si una falla.
- Los certificados y la carta de CTS salen con la compañía del trabajador; el certificado de 5ta no muestra renta imponible negativa ni suma boletas en borrador.

## 24/09/2026

- El bloque de contrato de la ficha del trabajador se restringe al personal de nómina.

## 7.20260827 — 27/08/2026

- El TXT de Interbank vuelve a salir con el formato completo de 380 caracteres por línea.

## 6.20260816 — 18/08/2026

- Nueva boleta de pago rediseñada.
- Plantillas de contrato en Configuración ▸ Perú ▸ Documentos y Pagos masivos bancarios al final del menú de Nómina.

## 4.20260802 — 03/08/2026

- Un solo botón de impresión para la boleta en todos los caminos.
- Neto y sobretiempo correctos en regímenes con estructura propia.

## 3.20260722 — 26/07/2026

- TXT bancario desde el lote: neto de la regla configurada y sin error por el número de boleta.

## 2.20260722 — 25/07/2026

- Primera versión en Odoo 19: boleta, certificados, contratos y pago masivo bancario.
