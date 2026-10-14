# Pagos con Izipay (AL)

Documentación funcional: [Izipay](../../mkdocs/content/applications/finance/payment_providers/izipay.md)

Módulo técnico `al_payment_izipay`. Agrega **Izipay** como proveedor de pago
de Odoo 19, construido desde su documentación oficial (API REST V4 de
micuentaweb.pe y formulario incrustado).

## Qué hace

- **Formulario emergente de Izipay** (modo pop-in del cliente
  `krypton-client` V4.0 en «modo SPA»). Los datos de la tarjeta van del
  navegador a Izipay y nunca pasan por Odoo. Izipay se encarga de 3DS y de
  las cuotas que tenga la tienda.
- **formToken creado en el servidor** (`Charge/CreatePayment`) por el
  importe exacto en céntimos, con los datos del cliente para el antifraude y
  la URL de la IPN.
- **Confirmación en el servidor**: al terminar el formulario, Odoo consulta el
  pedido (`Order/Get`) con la contraseña. No usa la respuesta del navegador.
- **IPN** (`/payment/izipay/webhook`) firmada con la contraseña: confirma el
  pago aunque el cliente cierre la ventana. Un intento rechazado con el pedido
  abierto no cambia la transacción, porque el cliente puede reintentar.
- **Anulación y devoluciones**, según el estado en Izipay:
  - Sin capturar (el mismo día): se anula todo o se reduce el importe por
    capturar.
  - Capturada: se reembolsa, total o parcial.
- **Soles y dólares**. Funciona donde funciona el módulo `payment`: tienda en
  línea, portal y enlaces de pago de facturas y pedidos.

## Configuración

1. **Contabilidad ▸ Configuración ▸ Proveedores de pago ▸ Izipay**.
2. Claves del Back Office Vendedor ▸ Configuración ▸ Tienda ▸ Claves de la
   API REST: el usuario (identificador de la tienda), la contraseña y la
   clave pública. En **Modo de prueba** se usan las de test
   (`testpassword_…`, `<tienda>:testpublickey_…`); en **Activado**, las de
   producción. Odoo comprueba los prefijos.
3. Publique el proveedor. La URL de notificación se envía en cada pago y debe
   ser accesible desde Internet (Izipay llama desde 194.50.38.0/24).

## Seguridad

- La contraseña solo la ven los administradores y nunca se envía al
  navegador.
- `/payment/izipay/return` exige un token firmado con la referencia y el
  cliente, bloquea la fila y consulta el resultado a Izipay.
- La IPN se rechaza (403) si la firma HMAC-SHA256 no coincide.
- Al neutralizar una copia de la base se borran la contraseña y la clave
  pública.

## Fuera de esta versión

- Tarjeta guardada.
- Captura manual.
- Medios distintos de la tarjeta (Yape, PagoEfectivo, QR): el formulario los
  muestra si la tienda los tiene contratados, pero no están probados.

## Pruebas

- `tests/`: pruebas con la API simulada con las respuestas reales de la
  tienda de prueba de Izipay. Cubren formToken, retorno, IPN, firma, importe
  alterado y los tres caminos de devolución.
- `docs/izipay/validar_sandbox.py`: pago real en la tienda de prueba pública
  de Izipay desde la página de pago de Odoo, con devolución parcial y total.

## Procedencia y licencia

Equivalente funcional del módulo `payment_izipay` (BuildFish, v17),
implementado desde la documentación oficial de Izipay, sin su código.
Licencia **OPL-1**.
