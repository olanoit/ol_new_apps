# Referencia — estructura de los TXT generados por el proyecto origen (Odoo 18)

Generado desde `tecport-mtest`, compañía **TECPORT PERU** (RUC 20517256031), periodos 2026-01 y 2026-03. Solo lectura; sin commit.

Los archivos completos **no se versionan** (38 MB): viven en `docs/tecport/referencia/`, ignorada por git, y se regeneran con `gen_referencia.py`. Este manifiesto es lo que se usa para validar la estructura de la implementación migrada.

## Inventario

| Periodo | Libro | Archivo | Bytes | Líneas | Campos/línea | MD5 |
|---|---|---|---:|---:|---|---|
| 2026-01 | 1.1  Libro Caja | `LE2051725603120260100010100001011.txt` | 1 | 0 |  | `68b329da9893` |
| 2026-01 | 1.2  Libro Bancos | `LE2051725603120260100010200001111.txt` | 3594 | 24 | 15 | `5ac19c4807ee` |
| 2026-01 | 5.1  Libro Diario | `LE2051725603120260100050100001111.txt` | 2599938 | 13391 | 21 | `a8e02d609410` |
| 2026-01 | 5.2  Libro Diario simplificado | `LE2051725603120260100050200001111.txt` | 2599938 | 13391 | 21 | `a8e02d609410` |
| 2026-01 | 5.3  Plan contable (diario) | `LE2051725603120260100050300001111.txt` | 137244 | 1242 | 8 | `d73e325f0a20` |
| 2026-01 | 5.4  Plan contable (diario simplificado) | `LE2051725603120260100050400001111.txt` | 137244 | 1242 | 8 | `d73e325f0a20` |
| 2026-01 | 6.1  Libro Mayor | `LE2051725603120260100060100001111.txt` | 2599938 | 13391 | 21 | `a8e02d609410` |
| 2026-01 | 8.4  Registro de Compras nacional (RCE) | `LE2051725603120260100080400021112.txt *(en LE2051725603120260100080400021112.zip)*` | 106293 | 575 | 38 | `b017a0ee1ed5` |
| 2026-01 | 8.5  Registro de Compras no domiciliados (RCE) | `LE2051725603120260100080500001112.txt *(en LE2051725603120260100080500001112.zip)*` | 6533 | 37 | 36 | `259788e8c9cc` |
| 2026-01 | 13.1 Inventario permanente valorizado | `LE2051725603120260100130100001111.txt` | 4038 | 25 | 26 | `83b19a86b55f` |
| 2026-01 | 14.4 Registro de Ventas (RVIE) | `LE2051725603120260100140400021112.txt *(en LE2051725603120260100140400021112.zip)*` | 19414 | 101 | 34 | `43a3e561be58` |
| 2026-03 | 1.1  Libro Caja | `LE2051725603120260300010100001011.txt` | 1 | 0 |  | `68b329da9893` |
| 2026-03 | 1.2  Libro Bancos | `LE2051725603120260300010200001111.txt` | 5212 | 34 | 15 | `fd351115ce16` |
| 2026-03 | 5.1  Libro Diario | `LE2051725603120260300050100001111.txt` | 1280889 | 7145 | 21 | `0af6a4de02f3` |
| 2026-03 | 5.2  Libro Diario simplificado | `LE2051725603120260300050200001111.txt` | 1280889 | 7145 | 21 | `0af6a4de02f3` |
| 2026-03 | 5.3  Plan contable (diario) | `LE2051725603120260300050300001111.txt` | 137244 | 1242 | 8 | `548828d06dbb` |
| 2026-03 | 5.4  Plan contable (diario simplificado) | `LE2051725603120260300050400001111.txt` | 137244 | 1242 | 8 | `548828d06dbb` |
| 2026-03 | 6.1  Libro Mayor | `LE2051725603120260300060100001111.txt` | 1280889 | 7145 | 21 | `0af6a4de02f3` |
| 2026-03 | 8.4  Registro de Compras nacional (RCE) | `LE2051725603120260300080400021112.txt *(en LE2051725603120260300080400021112.zip)*` | 72598 | 394 | 38 | `48e068455fa5` |
| 2026-03 | 8.5  Registro de Compras no domiciliados (RCE) | `LE2051725603120260300080500001112.txt *(en LE2051725603120260300080500001112.zip)*` | 728 | 4 | 36 | `0a7700a8f6ae` |
| 2026-03 | 13.1 Inventario permanente valorizado | `LE2051725603120260300130100001111.txt` | 6683 | 38 | 26 | `a77dba06437e` |
| 2026-03 | 14.4 Registro de Ventas (RVIE) | `LE2051725603120260300140400021112.txt *(en LE2051725603120260300140400021112.zip)*` | 16856 | 89 | 34 | `9751942e416c` |

## ⚠ Archivos con contenido idéntico dentro del mismo periodo

- **2026-01** — `a8e02d609410…`
  - 5.1  Libro Diario → `LE2051725603120260100050100001111.txt`
  - 5.2  Libro Diario simplificado → `LE2051725603120260100050200001111.txt`
  - 6.1  Libro Mayor → `LE2051725603120260100060100001111.txt`
- **2026-01** — `d73e325f0a20…`
  - 5.3  Plan contable (diario) → `LE2051725603120260100050300001111.txt`
  - 5.4  Plan contable (diario simplificado) → `LE2051725603120260100050400001111.txt`
- **2026-03** — `0af6a4de02f3…`
  - 5.1  Libro Diario → `LE2051725603120260300050100001111.txt`
  - 5.2  Libro Diario simplificado → `LE2051725603120260300050200001111.txt`
  - 6.1  Libro Mayor → `LE2051725603120260300060100001111.txt`
- **2026-03** — `548828d06dbb…`
  - 5.3  Plan contable (diario) → `LE2051725603120260300050300001111.txt`
  - 5.4  Plan contable (diario simplificado) → `LE2051725603120260300050400001111.txt`

## Muestras (primeras 2 líneas)

### 1.1  Libro Caja

```
```

### 1.2  Libro Bancos

```
20260100|BNK5202600011|M000156755|||31/01/2026|003|- /  / MANTENIMIENTO DE CUENTA|6|20100053455|Banco Internacional del Perú- Interbank S.A.A.|BNK5/2026/00011|0.00|50.00|1|
20260100|BNK7202600012|M000156981|||31/01/2026|003|999960236 / COMISION MANT. CUENTA         |6|20100043140|SCOTIABANK PERU SAA|BNK7/2026/00012|0.00|45.00|1|
```

### 5.1  Libro Diario

```
20260500|BNK1202600275|M000221850|6561012|||PEN|6|20523621212|00|0000|00000000|18/05/2026||18/05/2026|Robinson Pacherrez Guevara: A RENDIR RP - Enero I|BNK1/2026/00275|0.00|0.00||1|
20260500|BNK1202600275|M000221851|1041000|||PEN|6|20523621212|00|0000|00000000|18/05/2026||18/05/2026|Robinson Pacherrez Guevara: A RENDIR RP - Enero I|BNK1/2026/00275|0.00|0.00||1|
```

### 5.2  Libro Diario simplificado

```
20260500|BNK1202600275|M000221850|6561012|||PEN|6|20523621212|00|0000|00000000|18/05/2026||18/05/2026|Robinson Pacherrez Guevara: A RENDIR RP - Enero I|BNK1/2026/00275|0.00|0.00||1|
20260500|BNK1202600275|M000221851|1041000|||PEN|6|20523621212|00|0000|00000000|18/05/2026||18/05/2026|Robinson Pacherrez Guevara: A RENDIR RP - Enero I|BNK1/2026/00275|0.00|0.00||1|
```

### 5.3  Plan contable (diario)

```
20260101|0111000|Goods and securities delivered|01|Plan contable empresarial|||1|
20260101|0112000|Rights on financial instruments|01|Plan contable empresarial|||1|
```

### 5.4  Plan contable (diario simplificado)

```
20260101|0111000|Goods and securities delivered|01|Plan contable empresarial|||1|
20260101|0112000|Rights on financial instruments|01|Plan contable empresarial|||1|
```

### 6.1  Libro Mayor

```
20260500|BNK1202600275|M000221850|6561012|||PEN|6|20523621212|00|0000|00000000|18/05/2026||18/05/2026|Robinson Pacherrez Guevara: A RENDIR RP - Enero I|BNK1/2026/00275|0.00|0.00||1|
20260500|BNK1202600275|M000221851|1041000|||PEN|6|20523621212|00|0000|00000000|18/05/2026||18/05/2026|Robinson Pacherrez Guevara: A RENDIR RP - Enero I|BNK1/2026/00275|0.00|0.00||1|
```

### 8.4  Registro de Compras nacional (RCE)

```
20517256031|TECPORT PERU|202605||09/05/2026||07|F001||2644||6|20601034809|EUROCAPITAL SERVICIOS FINANCIEROS S.A.C.|0.00|0.00|0.00|0.00|0.00|0.00|-253.61|0.00|0.00|0.00|-253.61|USD|3.450|26/01/2026|01|F001||00038031|||||||
20517256031|TECPORT PERU|202601||31/01/2026||02|E001||160||6|10456824507|COCHACHIN GUERRERO JAVIER ARTURO|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|650.00|PEN|||||||||||||
```

### 8.5  Registro de Compras no domiciliados (RCE)

```
202601||23/01/2026|01|2601034565||30930.40|0.00|30930.40|||||0.00|USD|3.360|9087|TVH PARTS NV|Brabantstraat 15, Waregem|BE0425399042|||||0.00|0.00|0.00|0.00|0.00||||||||
202601||09/01/2026|01|762||30332.82|0.00|30332.82|||||0.00|USD|3.368|9249|Tecport Latam LLC|Columbus Center, 1 Alhambra Plaza Floor PH|81-1451349|||||0.00|0.00|0.00|0.00|0.00||||||||
```

### 13.1 Inventario permanente valorizado

```
20260100|STJ2026011643|M000211748|0000|||533442||08/01/2026|00|0000|00000000|99|BUSHING|NIU|2|0.00|0.00|0.67|0.00|0.00|0.00|0.00|0.00|0.67|1|
20260100|STJ2026011645|M000258920|0000|||W2128670||26/01/2026|00|0000|00000000|99|Casquillos (TEREX, TFC46M)|NIU|2|0.00|0.00|112.47|0.00|0.00|0.00|0.00|0.00|112.47|1|
```

### 14.4 Registro de Ventas (RVIE)

```
20517256031|TECPORT PERU|202601||31/01/2026|||PS|19||6|00000000|INTERNO - Tecport peru - Interno|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|USD|3.355|||||||
20517256031|TECPORT PERU|202601||30/01/2026|||PS|9||6|00000000|INTERNO - Tecport peru - Interno|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|USD|3.345|||||||
```

