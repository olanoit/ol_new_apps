# Pagos con PagoEfectivo (AL)

Documentación funcional: [PagoEfectivo](../../mkdocs/content/applications/finance/payment_providers/pagoefectivo.md)

Módulo técnico `al_payment_pagoefectivo`. Agrega **PagoEfectivo** como proveedor de pago
de Odoo 19: un código de pago (CIP) que el cliente paga en efectivo en agentes y bodegas,
o desde la banca por internet y las billeteras.

## Qué hace

- **CIP generado en el servidor** con la API REST v1:
  1. `POST /v1/authorizations` con `hashString` = SHA-256 de
     `idService.accessKey.secretKey.dateRequest`, con la fecha en hora de Lima.
  2. `POST /v1/cips` con el token Bearer, por el importe exacto.
- **Flujo de redirección**: el cliente va a la página del CIP (`cipUrl`) y también lo
  recibe por correo. La transacción queda pendiente con el CIP en `provider_reference`.
- **Notificación** (`/payment/pagoefectivo/webhook`): JSON `{eventType, operationNumber,
  data: {cip, currency, amount, paymentDate, transactionCode}}`.
  - `cip.paid` confirma la transacción.
  - `cip.expired` la cancela.
  - Se comprueban el importe y la moneda.
- **Vencimiento**: un cron horario cancela las transacciones pendientes con el CIP vencido
  hace más de dos horas. Si después llega un `cip.paid`, se confirma igual.
- **Soles y dólares**. Funciona donde funciona `payment`: tienda, portal, enlaces de
  pago y los avisos de `al_l10n_pe_collection`.

## Configuración

1. **Contabilidad ▸ Configuración ▸ Proveedores de pago ▸ PagoEfectivo**: el código de
   servicio, la clave de acceso, la clave secreta y la vigencia del CIP.
   - **Modo de prueba** usa `pre1a.services.pagoefectivo.pe`.
   - **Activado** usa `services.pagoefectivo.pe`.
2. Registre la URL de notificación en el panel de PagoEfectivo.
3. Publique el proveedor.

## Seguridad

- Las claves solo las ven los administradores y nunca salen del servidor.
- La notificación se rechaza (403) sin la cabecera `PE-Signature` o si no coincide con el
  HMAC-SHA256 del cuerpo y la clave secreta. También se acepta la firma del cuerpo
  compactado, sin espacios ni saltos de línea.
- La fila de la transacción se bloquea antes de procesar la notificación.
- Al neutralizar una copia de la base se borran la clave de acceso y la secreta.

## Fuentes y verificación

PagoEfectivo entrega su ficha técnica solo al comercio afiliado. Fuentes de la API:
- **Entorno de prueba público:** valida las solicitudes sin credenciales y devuelve sus
  códigos de error. Contra él se comprobaron el formato de la fecha, el `hashString` y
  los errores 111/113/508.
- **Integraciones de terceros publicadas:** la forma de la notificación y de la firma.

**Falta un CIP real:** se generará cuando el cliente tenga sus claves de preproducción.

## Fuera de esta versión

- Devoluciones: PagoEfectivo no las hace por la API.
- Consulta del estado del CIP: la confirmación llega solo por la notificación.

## Pruebas

`tests/`: 16 pruebas con la API simulada:
- la autorización firmada;
- la generación del CIP y la redirección;
- el cliente sin correo y el rechazo de PagoEfectivo;
- las notificaciones pagada, vencida, con firma no válida o importe alterado;
- el cron de vencimiento.

## Licencia

**OPL-1**.
