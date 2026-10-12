# PE - Consulta de validez de comprobantes en SUNAT (AL)

Documentación funcional: [Consulta de validez de comprobantes](../../mkdocs/content/applications/finance/fiscal_localizations/peru/cpe_validation.md)

Módulo `al_l10n_pe_cpe_validation` para Odoo 19.

Consulta los comprobantes de proveedores en el servicio web oficial de SUNAT
«Consulta integrada de comprobante de pago» (manual v2.0):

- `services/sunat_cpe.py`: token OAuth (`client_credentials`) y consulta
  `validarcomprobante`, con las tablas de estados del manual.
- `account.move`: resultado, estados del comprobante, del emisor y del
  domicilio, fecha y observaciones; botón y acción de servidor «Validar en
  SUNAT»; consulta al publicar (aviso o bloqueo); acción programada.
- `res.company`: credenciales del RUC en la compañía raíz (grupo de sistema)
  y token en caché; si no hay, se usan las del SIRE (`al_l10n_pe_sire`).

Datos de demostración para capturas: `tools/cpe_validation_demo_data.py`.
