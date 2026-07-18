[← Plan del módulo](../PLAN_MODULO_al_l10n_pe_ple.md)

# Libros Electrónicos PLE — mapa de cobertura

Matriz formato → módulo que lo genera → punto de entrada en Odoo 19
(BD de referencia: `ol_pe_v19`).

Todos los accesos están concentrados en la aplicación única **Perú**:
**Perú ▸ Libros PLE** contiene la captura/exportación propia y el submenú
**Reportes PLE nativos** (enlaces a los reportes EE: Diario y Mayor
5.1/5.3/6.1, Caja y Bancos 1.1/1.2, Ventas 14.1, Compras 8.1/8.2,
Inventarios TXT 12.1/13.1), y **Perú ▸ Kardex (12.1/13.1)** abre la capa
visual de `ol_stock_kardex_pe`.

| Formato | Nombre | Módulo | Menú / acción | Doc |
|---|---|---|---|---|
| 1.1 / 1.2 | Caja y Bancos | `l10n_pe_reports` (EE) | Contabilidad ▸ Informes ▸ Flujo de caja → botones PLE | — |
| 3.1–3.7, 3.11–3.18, 3.20, 3.24, 3.25 | Inventarios y Balances | `l10n_pe_reports_lib` (EE) | Libro Mayor → «PLE LIB» (ZIP) | — |
| 5.1 / 5.3 / 6.1 | Diario / Plan contable / Mayor | `l10n_pe_reports` (EE) | Libro Mayor → botones «PLE 5.1 / 5.3 / 6.1» | — |
| 8.1 / 8.2 | Registro de Compras | `l10n_pe_reports` (EE) | Informes ▸ Compras (RCE 8.4/8.5) | — |
| 12.1 / 13.1 | Inventario permanente | `l10n_pe_reports_stock` (EE) + `ol_stock_kardex_pe` | Inventario ▸ wizard PLE / Kardex | [`../../../ol_stock_kardex_pe/README.md`](../../../ol_stock_kardex_pe/README.md) |
| 14.1 | Registro de Ventas | `l10n_pe_reports` (EE) | Informes ▸ Ventas | — |
| **7.1 / 7.3 / 7.4** | **Registro de Activos Fijos** | **`al_l10n_pe_ple`** | **Perú ▸ Libros PLE ▸ Exportar PLE** | [libro_7.md](libro_7.md) |
| **4.1** | **Retenciones Art. 34 LIR** | **`al_l10n_pe_ple`** | **Perú ▸ Libros PLE** (captura + exportar) | [libro_4.md](libro_4.md) |
| **9.1 / 9.2** | **Consignaciones** | **`al_l10n_pe_ple`** | **Perú ▸ Libros PLE ▸ Exportar PLE** (albaranes marcados) | [libro_9.md](libro_9.md) |
| **3.8 / 3.9 / 3.19 / 3.23** | **Libro 3 complementos** | **`al_l10n_pe_ple`** | **Perú ▸ Libros PLE** (captura 3.8/3.19; 3.9 automático desde activos; 3.23 PDF adjunto) | [libro_3_complementos.md](libro_3_complementos.md) |
| **10.1–10.4** | **Registro de Costos** | **`al_l10n_pe_ple`** | **Perú ▸ Libros PLE ▸ Costos (Libro 10)** (captura) + Exportar PLE | [libro_10.md](libro_10.md) |
| **5.2 / 5.4, 8.3, 14.2** | **Formatos simplificados** | **`al_l10n_pe_ple`** | **Perú ▸ Libros PLE ▸ Exportar PLE** (requiere bandera en Ajustes ▸ Perú) | [libros_simplificados.md](libros_simplificados.md) |

Estructura oficial de todos los formatos: [`Estructura del PLE.xls`](../Estructura%20del%20PLE.xls)
(resumen campo a campo en el [plan, §6](../PLAN_MODULO_al_l10n_pe_ple.md)).
