-- Al neutralizar una copia de la base, se borran las credenciales de PagoEfectivo.
UPDATE payment_provider
   SET pagoefectivo_access_key = NULL,
       pagoefectivo_secret_key = NULL;
