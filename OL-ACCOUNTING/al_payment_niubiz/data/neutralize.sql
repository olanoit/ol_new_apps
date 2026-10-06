-- Al neutralizar una copia de la base, se borran las credenciales de Niubiz.
UPDATE payment_provider
   SET niubiz_secret_key = NULL,
       niubiz_access_key = NULL;
