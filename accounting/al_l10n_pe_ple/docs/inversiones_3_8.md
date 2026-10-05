[← Índice](README.md)

# Inversiones 3.8 — Detalle de la cuenta 30 (Inversiones mobiliarias)

**Qué es:** anexo del Libro de Inventarios y Balances que detalla, al
cierre del ejercicio, los títulos y valores que componen el saldo de la
cuenta 30 (acciones, bonos, participaciones). Odoo no modela títulos, por
lo que el detalle se **captura**.

## Captura

**Perú ▸ Libros PLE ▸ Inversiones 3.8** — lista editable:

| Columna | Contenido |
|---|---|
| Fecha del saldo (EEFF) | La misma fecha de balance que se usará al exportar (normalmente 31/12). |
| Emisor | Contacto del emisor del título (con su documento). |
| Nombre del emisor | Alternativa si el emisor es extranjero sin documento peruano (se emite tipo doc `0`). |
| Código del título (T15) | Tabla 15 del Anexo 3 (acciones, bonos, etc.). |
| Valor nominal unitario / Cantidad | Datos del título. |
| Costo total en libros | Debe cuadrar con el mayor de la cuenta 30. |
| Provisión | Desvalorización, **en positivo** (el TXT la emite negativa). |

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → grupo Libro 3: **Fecha de los EEFF**
y **Oportunidad** → marcar **3.8** → **Generar**. Solo se exportan los
registros cuya fecha coincide exactamente con la fecha de EEFF elegida.

## Qué revisar

- La suma de «Costo total en libros» = saldo contable de la cuenta 30 al
  cierre.
- SUNAT permite presentar el 3.8 «sin información» si el dato consta en
  otro libro; en ese caso simplemente no capture registros: el archivo
  saldrá con indicador de contenido `0`.
