-- Al neutralizar una copia de la base, se borran las credenciales de Izipay.
UPDATE payment_provider
   SET izipay_password = NULL,
       izipay_public_key = NULL;
