Historial de cambios — Recaudación bancaria (AL)
================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_l10n_pe_bank_collection.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.8 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261022.7 — 22/10/2026

- El acceso a convenios y formatos en los Ajustes de Cobranza sigue el diseño de las apps de Odoo, con enlace a la guía.

## 20261022.6 — 22/10/2026

- Accesos a los convenios y formatos de recaudación en Cobranza ▸ Configuración ▸ Ajustes, bloque «Cobro, agencias y comisiones».

## 20261022.5 — 22/10/2026

- La respuesta no ofrece «Crear pagos y conciliar» si no hay cobros por pagar y muestra el estado de cada cobro a la vista.

## 20261022.4 — 22/10/2026

- Scotiabank: validación parcial (una línea por cliente, importe libre) y validación de importes (catálogo de tipos de pago en el convenio), con sus archivos de resultados.
- La respuesta guarda la referencia y el tipo de pago informados por el banco.

## 20261022.3 — 22/10/2026

- Formato de Scotiabank (validación completa): archivo de cobranza de 200 posiciones y archivo de resultados, según la macro oficial del banco.

## 20261022.2 — 22/10/2026

- Formato oficial de BBVA (ficha técnica E1891 V21): archivo de entrada de datos de 360 bytes y respuesta de 152 bytes.
- Motor de formatos: códigos de carga por banco, caracteres que se cambian por espacios, equivalencias por campo (tipo de documento, canal), fecha de bloqueo, versión del envío del día y registro de totales.
- La respuesta identifica el documento aunque el banco haya quitado caracteres (BBVA cambia «/» por espacio).

## 20261022.1 — 22/10/2026

- Primera versión: convenios, formatos configurables con el CREP del BCP, archivo de deudores, respuesta del banco con pagos y conciliación automática.
