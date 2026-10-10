# Pagos con Culqi (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo técnico `al_payment_culqi`. Agrega **Culqi** como proveedor de pago de
Odoo 19, construido desde su documentación oficial: API v2, Checkout Custom y
Culqi 3DS.

## Qué hace

- **Tarjetas y Yape** con **Culqi Checkout Custom**. Checkout v4 está en
  desuso según Culqi. Los datos de la tarjeta van del navegador a Culqi y
  nunca pasan por Odoo.
- **Cargo en el servidor** con la llave secreta, por el monto exacto en
  céntimos (`POST /v2/charges`), con los datos antifraude del cliente y la
  huella del dispositivo (`Culqi3DS.generateDevice`).
- **Autenticación 3DS**: cuando Culqi responde `action_code: REVIEW`, el
  cliente se autentica con Culqi 3DS y el cargo se repite con
  `authentication_3DS`.
- **Devoluciones** totales o parciales desde la transacción de Odoo
  (`POST /v2/refunds`).
- **Soles y dólares** (Yape, solo soles). Funciona donde funciona el módulo
  `payment`: tienda en línea, portal y enlaces de pago de facturas y pedidos.

Cada petición y respuesta queda en el registro de pagos de Odoo, y el mensaje
de Culqi de un rechazo queda en la transacción.

## Configuración

1. **Contabilidad ▸ Configuración ▸ Proveedores de pago ▸ Culqi**.
2. Llaves de CulqiPanel ▸ Desarrollo ▸ API Keys:
   - **Modo de prueba**: `pk_test_…` y `sk_test_…`.
   - **Activado**: `pk_live_…` y `sk_live_…`.

   Odoo comprueba que el prefijo corresponda al modo.
3. Opcional: el ID y la llave pública RSA para cifrar el checkout.
4. Publique el proveedor y active los métodos **Tarjeta** y **Yape**.

## Seguridad

- La llave secreta solo la ven los administradores y nunca se envía al
  navegador.
- `/payment/culqi/charge` exige un token firmado con la referencia y el
  cliente de la transacción, bloquea la fila mientras cobra (un token de Culqi
  es de un solo uso) y no vuelve a cobrar una transacción ya procesada.
- Al neutralizar una copia de la base se borran las llaves.

## Fuera de esta versión

- Métodos que requieren una orden de Culqi y webhooks: PagoEfectivo,
  billeteras, Cuotéalo y agentes.
- Tarjeta guardada.
- Captura manual.

## Pruebas

- `tests/`: 15 pruebas con la API simulada con la forma exacta de la
  especificación oficial (cargo, rechazo, 3DS, importe alterado, devolución
  parcial, endpoint).
- `docs/culqi/validar_sandbox.py`: validación contra el sandbox real con las
  tarjetas de prueba de Culqi.

## Procedencia y licencia

Equivalente funcional del módulo comercial `tx_culqi_payment` (Techsnas),
implementado desde la documentación oficial de Culqi, sin su código.
Licencia **OPL-1**.
