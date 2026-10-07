Historial de cambios — PE - Letras de cambio y canje (AL)
=========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_account_letter.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20261007 — 07/10/2026

- Corregido: el importe se repartía sin redondear y el céntimo sobrante iba a gasto por redondeo (1 000 en 3 letras = 999,99); ahora la última letra absorbe la diferencia y las letras suman exactamente la deuda.
- Corregido: una letra enviada al banco (cobranza libre o descuento) aparecía «Pagado» aunque el cliente no hubiera pagado; ahora sigue pendiente hasta el cobro.
- Las facturas se concilian con su apunte del canje por vínculo, no emparejando por orden.
- Las letras nuevas quedan «En cartera» y las cuentas de letras del PCGE (1232, 1233, 1234 y 423) se configuran solas al instalar o actualizar, sin tocar las existentes.

## 7.20260901 — 27/09/2026

- El canje masivo ya no muestra ni modifica las facturas o letras de otro canje; restablecer, canjear y refinanciar se hacen en cada canje de origen.
- Un canje refinanciado se puede volver a borrador: se elimina su refinanciamiento.
- Refinanciar solo se ofrece en canjes canjeados o bancarizados y una sola vez.
- Un canje canjeado o bancarizado no se puede cancelar sin volverlo antes a borrador.
- «Todas las letras» en el envío al banco lleva solo las letras que siguen en cartera, sin repetir las ya enviadas.
- El adeudado de cada letra se actualiza al cambiar su importe y sale del apunte de esa letra; los pagos del canje se leen de sus conciliaciones.
- En varias compañías, cada canje usa sus propias cuentas de letras y su cuenta «Redondeo»; si falta la cuenta de redondeo, el canje lo avisa.
- Solo el administrador contable o de letras puede cambiar las cuentas de letras; el usuario de letras las consulta.
- Los grupos de acceso se llaman «Usuario» y «Administrador».

## 14/09/2026

- Corrección: en las facturas del canje ya no aparece una columna vacía.

## 4.20260901 — 01/09/2026

- Etiquetas de campos desambiguadas en filtros, agrupaciones y exportaciones.

## 3.20260828 — 28/08/2026

- Letras de cambio como menú propio de la app Perú y cuentas de letras en su configuración.

## 1.20260731 — 02/08/2026

- Primera versión en Odoo 19: canje, letras masivas, cobranza libre y descuento, refinanciación individual y masiva, canje masivo y vinculación por referencia.
