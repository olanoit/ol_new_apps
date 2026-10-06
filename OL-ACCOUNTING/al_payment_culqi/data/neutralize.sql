-- Al neutralizar una copia de la base, se borran las llaves de Culqi.
UPDATE payment_provider
   SET culqi_secret_key = NULL,
       culqi_public_key = NULL;
