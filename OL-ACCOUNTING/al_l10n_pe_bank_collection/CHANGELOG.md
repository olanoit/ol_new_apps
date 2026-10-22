Historial de cambios — Recaudación bancaria (AL)
================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_bank_collection.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261022 — 22/10/2026

- Accesos a los convenios y formatos de recaudación en Cobranza ▸ Configuración ▸ Ajustes, bloque «Cobro, agencias y comisiones».

## 5.20261022 — 22/10/2026

- La respuesta no ofrece «Crear pagos y conciliar» si no hay cobros por pagar y muestra el estado de cada cobro a la vista.

## 4.20261022 — 22/10/2026

- Scotiabank: validación parcial (una línea por cliente, importe libre) y validación de importes (catálogo de tipos de pago en el convenio), con sus archivos de resultados.
- La respuesta guarda la referencia y el tipo de pago informados por el banco.

## 3.20261022 — 22/10/2026

- Formato de Scotiabank (validación completa): archivo de cobranza de 200 posiciones y archivo de resultados, según la macro oficial del banco.

## 2.20261022 — 22/10/2026

- Formato oficial de BBVA (ficha técnica E1891 V21): archivo de entrada de datos de 360 bytes y respuesta de 152 bytes.
- Motor de formatos: códigos de carga por banco, caracteres que se cambian por espacios, equivalencias por campo (tipo de documento, canal), fecha de bloqueo, versión del envío del día y registro de totales.
- La respuesta identifica el documento aunque el banco haya quitado caracteres (BBVA cambia «/» por espacio).

## 1.20261022 — 22/10/2026

- Primera versión: convenios, formatos configurables con el CREP del BCP, archivo de deudores, respuesta del banco con pagos y conciliación automática.
