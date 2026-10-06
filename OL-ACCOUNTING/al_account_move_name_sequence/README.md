# Numeración de asientos por secuencia (AL)

Adaptación a Odoo 19 del módulo OCA `account_move_name_sequence`
(Akretion/Vauxoo), rediseñada como **opt-in por diario**.

## Diferencia clave con el OCA original

El OCA fuerza la numeración por `ir.sequence` en **todos** los diarios y
desactiva globalmente el mecanismo nativo (`highest_name`,
`sequence_prefix`, avisos de huecos…). Aquí nada cambia hasta que un
diario marca **«Numerar por secuencia»** — el resto de diarios (incluida
la numeración latam por tipo de documento) sigue siendo 100 % estándar.

## Uso para la facturación electrónica peruana

1. En el diario (p. ej. *Facturas TPV*), marcar **Numerar por
   secuencia**. Se crea una secuencia `no_gap` (SUNAT exige correlativo
   continuo) con relleno 8.
2. Editar el prefijo de la secuencia con la serie deseada: `F001-`,
   `B001-`, `FC01-` (NC en su secuencia propia)…
3. Al publicar, el asiento se numera `F001-00000001`, que es a la vez el
   `l10n_latam_document_number` (serie-folio) que consumen el EDI, el QR
   y los reportes CPE.

## Comportamiento

- La secuencia se consume al **publicar** (fecha del asiento aplicada a
  prefijos con fecha y rangos de la secuencia).
- Notas de crédito: secuencia separada opcional; si está vacía se usa la
  principal.
- En diarios con secuencia `no_gap` se omite el aviso nativo de
  renumeración al cancelar (el hueco es deliberado y la secuencia no
  reutiliza números).
