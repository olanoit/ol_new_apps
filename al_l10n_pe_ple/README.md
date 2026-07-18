# PE - Libros Electrónicos PLE (AL)

Completa los libros electrónicos PLE de SUNAT que la localización oficial
de Odoo 19 (CE + EE) no genera. Plan completo:
[`docs/ple/PLAN_MODULO_al_l10n_pe_ple.md`](../docs/ple/PLAN_MODULO_al_l10n_pe_ple.md) ·
Mapa de cobertura: [`docs/ple/reportes/README.md`](../docs/ple/reportes/README.md).

## Estado actual (Fases 0 a 5 — alcance del plan completo)

- **Aplicación única «Perú»**: todos los accesos PLE viven bajo el menú
  raíz de `al_account_base` — captura y exportación propias, el submenú
  **Reportes PLE nativos** con enlaces a los reportes EE (Diario/Mayor
  5.1/5.3/6.1, Caja y Bancos 1.1/1.2, Ventas 14.1, Compras 8.1/8.2 e
  Inventarios TXT 12.1/13.1) y el Kardex visual (`ol_stock_kardex_pe`,
  que ahora también depende de `al_account_base`).
- **Motor común PLE** (`l10n_pe.ple.mixin`): nomenclatura oficial del
  archivo (33 caracteres), serialización con `|` (CRLF, UTF-8, igual que
  `l10n_pe_reports` EE), formatos de fecha/importe/TC y validación del
  número exacto de campos por formato según el Anexo 2.
- **Wizard** en **Perú ▸ Libros PLE**: ejercicio + indicador de operaciones
  + selección de formatos; genera TXT (o ZIP si son varios).
- **Libro 7 — Registro de Activos Fijos** sobre `account.asset` (EE):
  - **7.1** revaluados y no revaluados (37 campos),
  - **7.3** diferencia de cambio (15 campos),
  - **7.4** arrendamiento financiero (11 campos).

  Los datos SUNAT (código, tablas 13/18/19/20, marca/modelo/placa, ME/TC,
  leasing) se capturan en la pestaña **PLE SUNAT** de la ficha del activo.
  Documentación: [`docs/ple/reportes/libro_7.md`](../docs/ple/reportes/libro_7.md).
- **Libro 4 — PLE 4.1 Retenciones Art. 34 LIR** (mensual): captura en
  **Perú ▸ Libros PLE ▸ Retenciones 4.1** (sin nómina PE, lista editable e
  importable). Doc: [`docs/ple/reportes/libro_4.md`](../docs/ple/reportes/libro_4.md).
- **Libro 9 — PLE 9.1/9.2 Consignaciones** (mensual): albaranes marcados
  con «Consignación PLE (Libro 9)»; incluye fila de saldo inicial por
  producto/contraparte. Doc: [`docs/ple/reportes/libro_9.md`](../docs/ple/reportes/libro_9.md).
- **Libro 3 — complementos** (fecha EEFF + oportunidad CC en el nombre):
  **3.8** inversiones (captura), **3.9** intangibles (automático desde
  activos con cuenta `34…`), **3.19** patrimonio (captura por rubro T34) y
  **3.23** notas (PDF adjunto al ZIP).
  Doc: [`docs/ple/reportes/libro_3_complementos.md`](../docs/ple/reportes/libro_3_complementos.md).
- **Libro 10 — Registro de Costos** (anual): captura en **Perú ▸ Libros
  PLE ▸ Costos (Libro 10)** — 10.1 costo de ventas (fila única por
  ejercicio), 10.2 elementos del costo (fila por mes), 10.3 procesos
  productivos (agrupamiento T21) y 10.4 centros de costos (precargables
  desde cuentas analíticas).
  Doc: [`docs/ple/reportes/libro_10.md`](../docs/ple/reportes/libro_10.md).
- **Formatos simplificados 5.2/5.4, 8.3 y 14.2** (mensuales, excluyentes
  con 5.1/5.3, 8.1 y 14.1): habilitados por la bandera **Ajustes ▸ Perú ▸
  «Libros PLE simplificados»**; generados desde asientos, compras y ventas
  publicados del mes.
  Doc: [`docs/ple/reportes/libros_simplificados.md`](../docs/ple/reportes/libros_simplificados.md).

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_ple \
  --test-enable --test-tags /al_l10n_pe_ple --stop-after-init
```
