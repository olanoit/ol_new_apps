[← Índice](README.md)

# Retenciones 4.1 — Libro de Retenciones Art. 34 inc. e) y f) LIR

**Qué es:** libro mensual de las retenciones de rentas de cuarta/quinta
categoría de los incisos e) y f) del artículo 34 de la LIR (personal sin
vínculo laboral formal). Odoo no tiene nómina peruana, por lo que el libro
se alimenta por **captura directa**.

## Captura

**Perú ▸ Libros PLE ▸ Retenciones 4.1** — lista editable en línea:

| Columna | Contenido |
|---|---|
| Fecha de pago / retención | Fecha en que se pagó o retuvo. |
| Prestador del servicio | Contacto con **tipo y nº de documento** (DNI → tabla 2 código 1). |
| Monto bruto | Retribución pagada o puesta a disposición, **en positivo**. |
| Retención efectuada | Importe retenido **en positivo** (el TXT lo emite en negativo automáticamente); `0` si no hubo retención. |

Consejos:
- Verificar que el contacto tenga el **Tipo de documento** correcto
  (Contactos ▸ pestaña Ventas y compras ▸ Identificación); si falta, el
  sistema infiere RUC solo para números de 11 dígitos.
- Para volúmenes grandes usar el **importador estándar** (Favoritos ▸
  Importar registros) con las mismas columnas.
- Los filtros «Prestador» y «Mes» permiten cuadrar el periodo antes de
  exportar.

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → Ejercicio + **Mes** → marcar
**4.1 Retenciones** → **Generar**. Solo se incluyen los registros cuya
fecha cae dentro del mes elegido.

## Validaciones

- El sistema impide capturar montos negativos.
- El TXT emite 10 campos por línea; la retención sale con signo negativo o
  `0.00`, como exige el Anexo 2.
