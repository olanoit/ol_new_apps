[← Índice](README.md)

# Libro 7 — Registro de Activos Fijos (7.1 / 7.3 / 7.4)

**Qué es:** libro anual que detalla los activos fijos, su depreciación y,
en formatos separados, la diferencia de cambio (7.3) y los activos en
arrendamiento financiero (7.4). Obligatorio para régimen general con
contabilidad completa.

## Configuración (una vez por activo)

En **Contabilidad ▸ Activos**, abrir cada activo → pestaña **PLE SUNAT**:

1. **Código del activo (PLE)** — código interno único (si se deja vacío el
   sistema usa `AF<id>`).
2. **Tipo de activo (T18)** — *obligatorio*; código de 1 dígito de la
   tabla 18 del Anexo 3 de SUNAT (lo define el contador).
3. **Estado del activo (T19)** — por defecto `1`.
4. **Catálogo (T13)** — por defecto `9` (catálogo propio).
5. **Marca / Modelo / Serie-placa** — si se dejan vacíos se emite `-`.
6. **Método (T20) y % depreciación** — se proponen solos (lineal → `1`,
   % = 100/años de vida útil) y son editables; el % es obligatorio para
   SUNAT cuando el método es línea recta.
7. Solo si aplica **7.3**: moneda de adquisición, valor en ME y TC a la
   fecha de compra. El TC al 31/12 lo toma el sistema de las tasas de
   cambio cargadas (módulo `al_l10n_pe_currency`).
8. Solo si aplica **7.4**: marcar «Arrendamiento financiero» y completar
   nº y fecha del contrato (obligatorios), inicio, nº de cuotas y monto
   total.

La depreciación proviene de los **asientos de depreciación publicados** del
activo (los que genera el propio módulo de Activos): campo 29 = acumulada
al cierre del ejercicio anterior (incluye el importe importado de sistemas
previos), campo 30 = depreciación del ejercicio.

## Generación

Perú ▸ Libros PLE ▸ **Exportar PLE** → indicar **Ejercicio** → marcar
**7.1** (y 7.3/7.4 si aplican) → **Generar**. El mes del nombre de archivo
sale como `00` (libro anual).

## Qué revisar antes de presentar

- El total de los campos 15+16 (saldo inicial + adquisiciones) debe cuadrar
  con el mayor de las cuentas 33x del ejercicio.
- Revaluaciones y ajustes por inflación se emiten `0.00` (Odoo no los
  modela): si la empresa revaluó, completar manualmente el TXT.
- Activos totalmente depreciados sin baja **sí** aparecen (correcto).
- El wizard rechaza la exportación listando los activos sin «Tipo de
  activo (T18)».
