# Formatos oficiales del PLE (SUNAT)

Documentos publicados por SUNAT en el compendio **Libros y Registros Contables
Electrónicos** de gob.pe, descargados el 17/09/2026. Son la fuente de verdad de
las estructuras que genera `al_l10n_pe_ple`: ante una diferencia manda el
archivo oficial.

| Archivo | Qué es | Fuente | MD5 |
|---|---|---|---|
| `Estructura del PLE.xls` | Anexo 2 de la R.S. 286-2009/SUNAT: estructura campo a campo de todos los libros (versión 5.0.0, guardada el 28/02/2021) | [Estructura de los Libros y Registros Electrónicos en el PLE](https://www.gob.pe/institucion/sunat/informes-publicaciones/356712-estructura-de-los-libros-y-registros-electronicos-en-el-ple) | `3aea7a6988b905b265a5c1fb1d5d9ad3` |
| `Nomenclatura de libros electronicos.pdf` | Reglas del nombre del archivo TXT | [Nomenclatura de libros electrónicos](https://www.gob.pe/institucion/sunat/informes-publicaciones/356705-nomenclatura-de-libros-electronico) | `942ef555a0d91812e7fd1a4c974cf818` |
| `Control de versiones del PLE.pdf` | Historial de versiones del programa PLE | [Control de versiones del PLE](https://www.gob.pe/institucion/sunat/informes-publicaciones/356576-control-de-versiones-del-programa-de-libros-electronicos) | `978fb16e6ba7151f901f89ed1765f373` |
| `Obligados a libros electronicos.pdf` | Quiénes deben llevar libros electrónicos desde 2018 | [Obligados a llevar libros electrónicos](https://www.gob.pe/institucion/sunat/informes-publicaciones/356696-obligados-a-llevar-libros-electronicos-a-partir-del-2018) | `2c367b7511d1876733c8675c52ec4785` |

El `Estructura del PLE.xls` descargado es idéntico (mismo MD5) al que se usó
para diseñar el módulo en julio de 2026. Los registros del **SIRE** (RCE 8.4 /
8.5 y RVIE 14.4) no están en este archivo: tienen sus propias resoluciones
(R.S. 040-2022/SUNAT y 000112-2021/SUNAT).

## Encabezados del Excel de revisión

Los encabezados de las hojas XLSX de los formatos de la localización oficial
(1.1, 1.2, Libro 3, 5.1, 5.3, 6.1, 12.1 y 13.1) salen de este archivo:

```bash
/home/och/odoo/ce19/.venv/bin/python docs/ple/oficial/generar_encabezados.py
```

genera `al_l10n_pe_ple/models/ple_official_headers.py`. El script comprueba
que cada formato tenga exactamente el número de campos que valida el módulo
(`PLE_EXPECTED_FIELDS`); si SUNAT publica otra versión, basta con reemplazar
el XLS y volver a ejecutarlo.
