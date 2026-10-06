# Plan — `al_payment_culqi` (proveedor de pago Culqi para Odoo 19)

Pedido: un módulo equivalente a `tx_culqi_payment` (Techsnas, OPL-1),
construido desde la documentación oficial de Culqi y validado.

## Fuentes oficiales (`oficial/`, descargadas el 06/10/2026)

- `apiculqi.yaml` — especificación OpenAPI de la API v2
  (https://apidocs.culqi.com/apiculqi.yaml); `apidocs_culqi.txt` es su
  versión renderizada.
- `culqi_3ds_docs.txt` — documentación de Culqi 3DS v1
  (https://docs.culqi.com/es/documentacion/culqi-3ds).
- Checkout Custom: https://docs.culqi.com/es/documentacion/checkout/checkout-custom
- Tarjetas de prueba: https://docs.culqi.com/es/documentacion/pagos-online/tarjetas-de-prueba

## Lo que dice la documentación

- **Checkout v4 está en desuso** («pronto se discontinuará»): se usa
  **Checkout Custom** (`https://js.culqi.com/checkout-js`,
  `new CulqiCheckout(publicKey, config)`, `Culqi.culqi = callback`,
  `Culqi.token.id`). El módulo comercial usa Checkout.
- Cargo: `POST https://api.culqi.com/v2/charges` con `Authorization: Bearer
  sk_…`; `amount` en céntimos, `currency_code` PEN/USD, `email`, `source_id`
  (token `tkn_…` o Yape `ype_…`), `antifraud_details` (incluye
  `device_finger_print_id`) y `authentication_3DS`.
  - **201**: cargo exitoso (objeto `charge`, `outcome`, `reference_code`).
  - **200** `{"action_code": "REVIEW"}`: el banco pide **3DS**.
  - **4xx/5xx**: rechazo (`merchant_message`, `user_message`, `decline_code`).
- 3DS: `https://3ds.culqi.com`; `Culqi3DS.publicKey`,
  `Culqi3DS.settings = {charge: {totalAmount, returnUrl, currency}, card: {email}}`,
  `Culqi3DS.generateDevice()`, `Culqi3DS.initAuthentication(token)`. El
  resultado llega por `window.postMessage` con `parameters3DS` (eci, xid,
  cavv, protocolVersion, directoryServerTransactionId) y se repite el cargo
  con ellos.
- Devolución: `POST /v2/refunds` con `amount`, `charge_id` y `reason`
  (`solicitud_comprador`, `duplicado`, `fraudulento`).
- Pruebas: `POST https://secure.culqi.com/v2/tokens` con la llave pública
  crea tokens de las tarjetas de prueba sin navegador (solo para validar).

## Alcance

| | Módulo comercial | `al_payment_culqi` |
|---|---|---|
| Tarjetas | Sí (Checkout v4) | Sí (Checkout Custom) |
| Yape | No | Sí (también tokeniza) |
| 3DS (cargo con REVIEW) | No consta | Sí |
| Huella del dispositivo antifraude | No consta | Sí |
| Devoluciones totales y parciales | Sí | Sí |
| PEN y USD | Sí | Sí |
| Checkout, enlaces de pago de facturas y pedidos | Sí | Sí (flujo nativo de `payment`) |

Fuera de esta versión: los métodos que requieren una orden de Culqi y
webhooks (PagoEfectivo, billeteras, Cuotéalo, agentes), la tarjeta guardada
y la captura manual.

## Diseño (patrones de Odoo 19)

- `payment.provider` con `code = 'culqi'`: llaves pública y secreta,
  opcionalmente el par RSA del checkout. Cliente HTTP con
  `_send_api_request` y sus ganchos.
- Flujo `direct`: `PaymentForm` abre Checkout Custom; el token va por
  `/payment/culqi/charge` (access token firmado + bloqueo de la fila, como
  `payment_authorize`); el servidor crea el cargo y procesa la transacción
  con `_process`. Si responde REVIEW, el navegador hace la autenticación 3DS
  y se vuelve a llamar con los parámetros.
- Devoluciones con `_send_refund_request`.
- Nuevo método de pago Yape (`payment.method`).

## Validación

1. Pruebas unitarias con la API simulada: cargo exitoso, rechazo, REVIEW,
   devolución, montos y monedas, access token.
2. Validación real contra el **sandbox de Culqi** con las tarjetas de
   prueba oficiales: requiere las llaves de integración (`pk_test_…`,
   `sk_test_…`) del CulqiPanel del cliente.
