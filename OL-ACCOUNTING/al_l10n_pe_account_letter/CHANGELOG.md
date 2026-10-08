Historial de cambios — PE - Letras de cambio y canje (AL)
=========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_account_letter.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 17.20261008 — 08/10/2026

- Menú Perú ▸ Letras de cambio reordenado: en Clientes, Letras por cobrar, Canje de letras, Canje masivo, Letras en el banco, Refinanciaciones e Historial de canje masivo; en Proveedores, lo mismo sin banco; y Análisis de letras (tabla dinámica y gráfico).
- Listas de letras con canje, contacto, vencimiento, tipo, importe y saldo con totales; vencidas en rojo; filtros Con saldo, Vencidas, Vencen en 30 días y por tipo; agrupar por contacto, tipo, banco, moneda y mes.
- Etiquetas en español en todo el módulo: «Contacto» en lugar de «Socio», «N.º de …» en lugar de «Nro.», y campos que salían en inglés (N.º de documento, Diarios de letras permitidos, Letras disponibles, Resumen).

## 16.20261008 — 08/10/2026

- Los asistentes validan en el servidor que lo que reciben sea de su compañía (_check_company_auto y check_company).

## 15.20261008 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 14.20261008 — 08/10/2026

- Botones con la convención de Odoo: «Crear letras» llama a action_create_letters y el asistente de refinanciamiento a action_create_refinance.

## 13.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 12.20261007 — 07/10/2026

- Reclasificación: una letra ya enviada al banco pasa de cobranza libre a descuento (o al revés) con un asiento que lleva su saldo de una cuenta a otra al mismo valor en soles. Funciona desde el canje por letra y desde el canje masivo; no aplica a letras con el descuento ya liquidado, cobradas o protestadas.

## 11.20261007 — 07/10/2026

- Canje masivo: ahora envía al banco las letras en cartera con su asiento contable (cartera → cobranza libre o descuento), pidiendo fecha, banco y código. Antes solo cambiaba el tipo de las letras y la contabilidad seguía en cartera.
- Refinanciamiento con intereses: si las letras nuevas no suman lo que se renueva, se avisa que los intereses o gastos se facturan con una nota de débito, que se añade como documento del refinanciamiento y queda conciliada (antes: «asiento descuadrado»).
- Multicompañía: las letras, los documentos y el redondeo del canje guardan la compañía y tienen su regla de acceso; el número de letra se repite solo dentro del socio y la compañía; la numeración del canje usa la secuencia de su compañía si se configura una.

## 10.20261007 — 07/10/2026

- Canje: al restablecerlo a borrador se deshace la conciliación (antes la factura seguía «Pagado» y no se podía volver a canjear); no se restablece si hay pagos contra las letras; un documento no se canjea por más de su saldo ni en dos canjes a la vez; una diferencia entre facturas y letras mayor que el redondeo ya no va a la cuenta de redondeo; un canje ya contabilizado no se vuelve a canjear por doble clic.
- Canjes en dólares: el asiento ya no queda descuadrado por un céntimo (la última letra absorbe la diferencia en soles).
- Refinanciamiento: cierra la letra en la cuenta donde está realmente (cartera, banco o protestada); antes una letra en cobranza o protestada quedaba abierta y el cliente debía el doble. Una letra descontada no se renueva hasta que el banco la cobre o la proteste, y un refinanciamiento con letras ya enviadas al banco no se cancela.
- El selector de documentos del canje solo ofrece documentos de la compañía y con saldo.

## 9.20261007 — 07/10/2026

- Nuevo: liquidación del descuento con el banco (abono neto, intereses, comisiones y préstamo por el valor nominal).
- Nuevo: cobro del banco en cobranza libre (con su comisión) y en descuento (cancela el préstamo); la letra queda pagada.
- Nuevo: protesto de letras. La letra vuelve a cobrarse al cliente, el banco carga la letra descontada y los gastos de protesto van a gastos bancarios; se avisa si se protesta fuera del plazo de 15 días.
- Los diarios de letras se marcan en el diario y las cuentas de redondeo, descuento e intereses se eligen en Ajustes; ya no se buscan por el nombre (al actualizar se adopta lo existente).

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
