Historial de cambios — PE - Cierre de tipo de cambio (AL)
=========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_l10n_pe_exchange_closure.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.13 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261018.12 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 20261012.11 — 12/10/2026

- Menú en Perú ▸ Contabilidad ▸ Cierre del mes.

## 20261012.10 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): movimientos en dólares de hace dos meses, el cierre de ese mes contabilizado y el del mes siguiente calculado, con T.C. de cierre registrados sin descargarlos.

## 20261008.9 — 08/10/2026

- Etiquetas en español: campos propios sin texto (Compañía, Moneda, Nombre del archivo…) y campos heredados (creado por, seguidores, actividades) traducidos con su i18n/es.po.

## 20261008.8 — 08/10/2026

- Los años se muestran sin separador de miles (2026, no 2.026) y no se suman al agrupar.

## 20261008.7 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 20261008.6 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 20261007.5 — 07/10/2026

- Corregido: el cierre tomaba el T.C. que SUNAT muestra con fecha del último día del mes, que es el cierre del día hábil anterior. Ahora usa por defecto el cierre de operaciones del último día, como manda el art. 34 del Reglamento de la LIR (SUNAT lo muestra con fecha del día siguiente: el cierre 2014, 2.981 / 2.989, figura el 01/01/2015). Las opciones anteriores siguen disponibles.
- Traer T.C. descarga primero del BCRP, sin token, y solo después intenta apis.net.pe.
- Los cierres sin contabilizar pasan a la opción nueva y hay que volver a traer el T.C.; los contabilizados no cambian.

## 20260828.4 — 27/09/2026

- Si se cambia el mes, la moneda, los tipos de cambio o la analítica de un cierre ya calculado, vuelve a borrador y hay que calcularlo de nuevo: ya no se puede contabilizar un cálculo desfasado.
- Un cierre solo se puede cancelar si no hay cierres posteriores contabilizados.
- Volver un cierre a borrador conserva su asiento cancelado en lugar de borrarlo, como exige la pista de auditoría.
- Cada compañía ve solo sus cierres, y el cierre incluye los apuntes de sus sucursales.
- El T.C. solo se descarga automáticamente para el dólar; para otras monedas se usa el registrado.

## 14/09/2026

- Menús de la app Perú reordenados.

## 20260828.2 — 28/08/2026

- El cierre pasa al grupo **Tipo de cambio** de la app Perú; menú **Cuentas del cierre de T.C.** en Configuración.

## 20260802.1 — 02/08/2026

- Primera versión en Odoo 19: saldos acumulados, detalle por socio, ganancia y pérdida separadas, analítica heredada y vista previa del asiento.
