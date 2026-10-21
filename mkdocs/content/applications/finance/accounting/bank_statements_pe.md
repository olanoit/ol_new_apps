---
modulos: [al_l10n_pe_bank_statement_import]
---

# Extractos de bancos peruanos

Los bancos peruanos no exportan sus movimientos en OFX ni CAMT, sino en Excel o en texto,
cada uno con sus columnas y con títulos y datos de la cuenta encima de la tabla. El módulo
**Extractos de bancos peruanos** (`al_l10n_pe_bank_statement_import`) los importa
directamente, sin mapear columnas.

## Importar

1. Descargue los movimientos desde la banca por internet en Excel (XLSX o XLS), CSV o TXT.
2. En **Contabilidad ‣ Tablero**, en el diario del banco, haga clic en **Importar** (o
   arrastre el archivo) y elija el archivo.
3. Odoo crea el extracto con sus movimientos y abre la conciliación bancaria.

## Qué reconoce

- **Archivos:** Excel (XLSX y XLS), el «Excel» que en realidad es una tabla HTML (muchos
  portales descargan así), CSV y TXT con separador `;`, `,`, tabulación o `|`.
- **La tabla:** busca la fila de encabezados en las primeras 40 filas, aunque arriba haya
  títulos, el número de cuenta o la moneda.
- **Las columnas, por su nombre** (sin importar mayúsculas, tildes ni signos):

| Dato | Nombres reconocidos (ejemplos) |
|---|---|
| Fecha | Fecha, Fecha de operación, F. Operación, Fecha de proceso |
| Descripción | Descripción, Descripción operación, Concepto, Detalle, Glosa, Movimiento |
| N.º de operación | N.º de operación, Nro. operación, Operación - Número, N.º Doc., Referencia |
| Importe | Monto o Importe (con signo), o bien **Cargo** y **Abono** en dos columnas |
| Saldo | Saldo, Saldo contable, Saldo disponible |

- **Importes:** con o sin «S/», con separador de miles, con punto o coma decimal, y los
  negativos con signo o entre paréntesis.
- **Fechas:** dd/mm/aaaa (y variantes) o fechas de Excel.
- **Orden:** si el banco lista del más reciente al más antiguo, se ordenan.
- **Saldos:** con columna de saldo, el extracto lleva el saldo inicial y final del banco y
  Odoo comprueba que cuadren con los movimientos.

Las filas sin fecha (totales, pies de página) se ignoran.

## Volver a importar

Cada movimiento lleva un identificador calculado de su fecha, importe, número de
operación y descripción: si importa de nuevo el mismo archivo, o uno que se superpone
con el anterior, los movimientos ya importados no se duplican.

## Si el archivo no se reconoce

Si el archivo no tiene una fila con fecha y monto (o cargo y abono), se abre el importador
nativo de Odoo para mapear las columnas a mano. Si su banco usa títulos de columna
distintos, avise para agregarlos.

!!! note "Archivos de recaudación"
    Los archivos de recaudación (cobranza por el banco) usan especificaciones que cada banco
    entrega a sus clientes; se implementan cuando se cuenta con esa especificación.
