# Plan — `al_payment_izipay` (proveedor de pago Izipay para Odoo 19)

Pedido (14/10/2026): un módulo equivalente a `payment_izipay` de BuildFish
(Odoo Apps, v17, LGPL-3, 137,85 €), con el mismo patrón que
`al_payment_culqi` y `al_payment_niubiz`. La ficha de Odoo Apps no describe la
integración: el módulo se construye desde la documentación oficial de Izipay,
no desde ese código.

## Fuentes oficiales (`oficial/`, descargadas el 14/10/2026)

Izipay usa la plataforma de Lyra con la marca **Mi Cuenta Web**
(`micuentaweb.pe`):

- Documentación REST V4: https://secure.micuentaweb.pe/doc/es-PE/rest/V4.0/
  (es una SPA; los `.txt` se extrajeron con Playwright):
  - `javascript_guide_embedded_keys.txt`: las 4 claves de la API REST.
  - `javascript_guide_embedded_formToken.txt`: `Charge/CreatePayment`.
  - `ws_charge_createpayment.txt`: todos los campos de `Charge/CreatePayment`.
  - `ws_transaction_cancelorrefund.txt`: anulación y reembolso.
  - `api_kb_ipn_usage.txt`: la IPN y su firma.
  - `kb_payment_done.txt`: el retorno a la tienda y su firma.
  - `api_kb_status_reference.txt`: ciclo de vida (`status`, `detailedStatus`).
  - `api_kb_test_cards.txt`: tarjetas de prueba.
- Ejemplos oficiales: https://github.com/izipay-pe (Embedded/PopIn
  PaymentForm en Python-Flask, Server-IPN, PopIn React con
  `@lyracom/embedded-form-glue`).

## Lo que dice la documentación

- **Claves** (Back Office Vendedor ▸ Configuración ▸ Tienda ▸ Claves de la
  API REST), una de test y otra de producción por cada uso:
  1. Usuario: el identificador de la tienda.
  2. Contraseña (`testpassword_…`/`prodpassword_…`): llamadas REST y firma de la IPN.
  3. Clave pública (`<tienda>:testpublickey_…`/`<tienda>:publickey_…`): formulario en el navegador.
  4. Clave HMAC-SHA-256: firma del retorno al navegador.
- **Pago**: `POST https://api.micuentaweb.pe/api-payment/V4/Charge/CreatePayment`
  con HTTP Basic (`tienda:contraseña`). Recibe `amount` en céntimos,
  `currency`, `orderId` (solo `[A-Za-z0-9_-]`), `customer`, `metadata`,
  `ipnTargetUrl`, y devuelve `answer.formToken`, válido 15 minutos.
- **Formulario**: `static.micuentaweb.pe/static/js/krypton-client/V4.0/stable/kr-payment-form.min.js`
  con `kr-public-key`. Se muestra incrustado (`.kr-embedded`) o en ventana
  emergente (`kr-popin`). Izipay se encarga de 3DS y de las cuotas.
- **IPN**: POST con `kr-answer` (JSON `V4/Payment`), `kr-hash`,
  `kr-hash-key=password` y `kr-hash-algorithm=sha256_hmac`. `kr-hash` =
  HMAC-SHA256 hex de `kr-answer` con la contraseña. Origen: 194.50.38.0/24.
- **Estados**: `orderStatus` PAID / UNPAID / RUNNING / ABANDONED; `detailedStatus`
  AUTHORISED (por capturar), CAPTURED, REFUSED, CANCELLED…
- **Anulación/reembolso**: `Transaction/CancelOrRefund` (`uuid`, `amount`,
  `currency`, `resolutionMode` AUTO / CANCELLATION_ONLY / REFUND_ONLY),
  `Transaction/Update` (reducir el importe por capturar), `Transaction/Get`.

## Lo comprobado en la tienda de prueba pública (89289758)

La documentación publica la contraseña de prueba de la tienda 89289758; la
clave pública se obtuvo de su playground. Con ellas se hicieron pagos reales de
prueba (`docs/izipay/validar_sandbox.py`):

- Los errores llegan con **HTTP 200** y `status: ERROR`
  (`answer.errorCode`, `errorMessage`, `detailedErrorMessage`).
- Visa 4970100000000055: `orderStatus PAID`, `detailedStatus AUTHORISED`; la
  `metadata` vuelve en cada transacción, no en `orderDetails`.
- Visa 4970100000000113: el formulario muestra «Fondos insuficientes…», el
  pedido sigue **abierto** (`orderCycle OPEN`) y el cliente puede reintentar.
- `Order/Get` devuelve `V4/OrderTransactions` con todas las transacciones del
  pedido.
- **Trampa**: `CancelOrRefund` con `AUTO` y un importe **parcial** sobre una
  transacción sin capturar **anuló la transacción completa**.
  `REFUND_ONLY` y `Transaction/Refund` rechazan una transacción sin capturar
  (`PSP_101`). `Transaction/Update` con `cardUpdate.amount` sí reduce el
  importe.

## Alcance

| | Módulo de BuildFish | `al_payment_izipay` |
|---|---|---|
| Tarjetas (y cuotas que ofrezca la tienda) | Sí | Sí, formulario emergente de Izipay |
| 3DS | No consta | Sí (lo hace el formulario de Izipay) |
| Confirmación en el servidor (no se confía en el navegador) | No consta | Sí, `Order/Get` con la contraseña |
| IPN firmada | No consta | Sí, `ipnTargetUrl` en cada pago |
| Anulación y devoluciones totales o parciales | No consta | Sí, según la captura |
| PEN y USD | No consta | Sí |

Fuera de esta versión: tarjeta guardada (`REGISTER_PAY`), captura manual,
y los medios distintos de la tarjeta que la tienda tenga activos en el
formulario (Yape, PagoEfectivo, QR): el formulario los muestra si están
contratados, pero no se han probado.

## Diseño (patrones de Odoo 19, igual que Culqi)

- `payment.provider` con `code = 'izipay'`: identificador de la tienda,
  contraseña (solo administradores) y clave pública; Odoo comprueba los
  prefijos según el modo. No hace falta la clave HMAC: el retorno no se lee del
  navegador.
- Cliente HTTP con `_send_api_request`: `_build_request_auth` (Basic) y
  `_parse_response_content` (convierte `status: ERROR` en `ValidationError`).
- Flujo `direct`: `_get_specific_processing_values` crea el formToken. El JS
  carga krypton-client en modo SPA (`kr-spa-mode`, como embedded-form-glue) y
  abre la ventana emergente. `KR.onSubmit` → `/payment/izipay/return`
  (access token firmado + bloqueo de la fila) → `Order/Get` → `_process`.
- `/payment/izipay/webhook`: IPN con firma verificada; un rechazo con el
  pedido abierto no cambia la transacción.
- Devoluciones: `Transaction/Get` → sin capturar: `CANCELLATION_ONLY` (todo) o
  `Transaction/Update` (una parte); capturada: `REFUND_ONLY`.
- `orderId` = referencia sin caracteres no admitidos; la referencia exacta
  viaja en `metadata.odoo_reference`.

## Validación

1. Pruebas unitarias con la API simulada con las respuestas reales.
2. `docs/izipay/validar_sandbox.py`: pago real en la tienda de prueba desde
   la página de pago de Odoo, más una devolución parcial y una total.
