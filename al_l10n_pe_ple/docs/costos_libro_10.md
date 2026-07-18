[← Índice](README.md)

# Costos (Libro 10) — Registro de Costos (10.1 / 10.2 / 10.3 / 10.4)

**Qué es:** libro **anual** obligatorio para empresas del régimen general
con actividad de transformación (producción). Como la base no usa
Fabricación (`mrp`), los cuatro formatos se alimentan por **captura**
(listas editables e importables) en **Perú ▸ Libros PLE ▸ Costos
(Libro 10)**.

## 10.1 Costo de ventas (una fila por ejercicio)

Inventario inicial de productos terminados, costo de producción del
ejercicio, inventario final (**capturar en positivo**, el TXT lo emite en
negativo) y ajustes diversos. El sistema impide duplicar el ejercicio.

## 10.2 Elementos del costo (una fila por mes)

Materiales/suministros directos, mano de obra directa, otros costos
directos y los tres componentes de gastos indirectos de fabricación (GIF).
El archivo es anual pero cada fila lleva su periodo mensual; capture los
12 meses del ejercicio (el sistema impide duplicar un mes).

## 10.3 Costo de producción valorizado (una fila por proceso)

Código y descripción del proceso productivo, los seis elementos del costo,
inventarios inicial/final de productos en proceso (final en positivo → se
emite negativo) y el **código de agrupamiento** (tabla 21 del Anexo 3).

## 10.4 Centros de costos (una fila por centro)

Código/descripción de la unidad de operación y del centro de costos. El
campo **Cuenta analítica** es opcional: al elegirla se proponen código y
descripción del centro (editables) — útil si el plan analítico de Odoo
refleja los centros de costos reales.

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → **Ejercicio** → marcar los formatos
10.x necesarios → **Generar** (mes del archivo = `00`, libro anual).

## Qué revisar

- 10.1 debe cuadrar con el costo de ventas del Estado de Resultados;
  10.2/10.3 con las cuentas de los elementos 6 y 9 del PCGE.
- Los cuatro formatos se presentan juntos en la oportunidad anual que fija
  SUNAT (con la declaración jurada anual).
