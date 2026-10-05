[← Índice](README.md)

# Patrimonio 3.19 — Estado de cambios en el patrimonio neto

**Qué es:** anexo del Libro de Inventarios y Balances con el estado de
cambios en el patrimonio: una fila por **rubro** (tabla 34 de SUNAT) y doce
columnas monetarias (capital, reservas, resultados, etc.). Se prepara a
partir del EEFF aprobado, por **captura**.

## Captura

**Perú ▸ Libros PLE ▸ Patrimonio 3.19** — lista editable:

1. **Fecha del EEFF** — la misma que se usará al exportar (31/12 normal).
2. **Rubro EEFF (T34)** — se elige del catálogo de rubros que carga la
   localización EE (los mismos rubros del Balance/EEFF configurados en
   Ajustes ▸ Perú de la compañía); el **Catálogo (T22)** se propone solo a
   partir del sector del rubro.
3. Las **12 columnas** (capital, acciones de inversión, capital adicional,
   resultados no realizados, reservas legales, otras reservas, resultados
   acumulados, diferencia de conversión, ajustes al patrimonio, resultado
   neto, excedente de revaluación, resultado del ejercicio) — columnas
   opcionales ocultas se muestran con el selector de columnas de la lista.

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → grupo Libro 3: **Fecha de los EEFF**
y **Oportunidad** → marcar **3.19** → **Generar**.

## Qué revisar

- Cada fila emite 16 campos: periodo, catálogo, rubro y las 12 columnas +
  estado. Los importes pueden ser negativos (p. ej. pérdidas).
- El total por columna debe cuadrar con el estado de cambios en el
  patrimonio del EEFF aprobado por la junta.
