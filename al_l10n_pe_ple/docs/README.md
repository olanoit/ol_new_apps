# Guía funcional — Libros Electrónicos PLE (app Perú)

Documentación para el **consultor funcional**: qué es cada reporte, cómo se
configura y cómo se genera. La referencia técnica campo a campo está en
[`docs/ple/reportes/`](../../docs/ple/reportes/README.md) del repositorio.

## Mapa del menú (aplicación Perú)

| Menú | Guía |
|---|---|
| Perú ▸ Libros PLE ▸ **Exportar PLE** | [exportar_ple.md](exportar_ple.md) |
| Perú ▸ Libros PLE ▸ **Retenciones 4.1** | [retenciones_4_1.md](retenciones_4_1.md) |
| Perú ▸ Libros PLE ▸ **Inversiones 3.8** | [inversiones_3_8.md](inversiones_3_8.md) |
| Perú ▸ Libros PLE ▸ **Patrimonio 3.19** | [patrimonio_3_19.md](patrimonio_3_19.md) |
| Perú ▸ Libros PLE ▸ **Costos (Libro 10)** | [costos_libro_10.md](costos_libro_10.md) |
| Perú ▸ Libros PLE ▸ **Reportes PLE nativos** | [reportes_nativos.md](reportes_nativos.md) |
| Perú ▸ **Kardex (12.1/13.1)** | [kardex.md](kardex.md) |
| Ficha del activo (pestaña PLE SUNAT) → Libro 7 | [libro_7_activos_fijos.md](libro_7_activos_fijos.md) |
| Albaranes marcados → Libro 9 | [consignaciones_libro_9.md](consignaciones_libro_9.md) |
| Ajustes ▸ Perú → formatos simplificados | [simplificados.md](simplificados.md) |

## Conceptos comunes

- **Nombre del archivo** (lo arma el sistema, 33 caracteres):
  `LE + RUC(11) + año + mes + día + código de libro(6) + oportunidad(2) +
  indicador de operaciones + con/sin información + moneda + 1`. Los libros
  anuales llevan mes `00`; solo el Libro 3 lleva día y oportunidad.
- **Estado de operación**: todos los registros se emiten con estado `1`
  (operación del periodo). Las regularizaciones de periodos anteriores
  (estados `8`/`9`) deben gestionarse manualmente antes de validar en SUNAT.
- **Requisito general**: la compañía debe tener **RUC de 11 dígitos** en su
  ficha (NIF); si falta, cualquier exportación se detiene con un aviso.
- **Validación interna**: cada archivo se valida contra el Anexo 2 de SUNAT
  (número exacto de campos por línea) antes de descargarse.
- **Datos de prueba**: el script
  [`tools/ple_demo_data.py`](../tools/ple_demo_data.py) crea registros de
  demostración (prefijo «DEMO PLE») y valida los 22 reportes de una vez.
