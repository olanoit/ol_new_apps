# Pagos con Niubiz (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo técnico `al_payment_niubiz`. Integra el **Checkout All-In-One de
Niubiz (VisaNet Perú)** como proveedor de pago de Odoo 19.

## Qué hace

- **Un solo modal de Niubiz** con:
  - tarjetas Visa, Mastercard, American Express, Diners y UnionPay;
  - billeteras con QR (Yape, Plin y otras);
  - Cuotéalo BCP;
  - PagoEfectivo;
  - puntos.
- **Los datos de la tarjeta los procesa Niubiz** (PCI DSS nivel 1): Odoo solo
  recibe el token de la transacción.
- **Autorización en el servidor**: guarda el código de autorización, el
  número de traza, la fecha y la marca de la tarjeta.
- **Tarjeta rechazada**: el cliente vuelve a la página de pago con el motivo y
  puede reintentar sin crear otro pedido.
- **PagoEfectivo**: genera el código CIP y la transacción queda pendiente
  hasta el pago.
- **Anulación** (reversa) el mismo día, con el botón «Anular en Niubiz» de la
  transacción: cancela también el pago contable.
- **Devoluciones** parciales o totales: requieren el RUC del comercio; Niubiz
  las admite desde 48 horas hábiles después del pago y hasta 6 meses.
- Soles y dólares.

## Configuración

**Contabilidad ▸ Configuración ▸ Proveedores de pago ▸ Niubiz**:

- código de comercio;
- usuario y contraseña de la API (la contraseña solo la ven los
  administradores);
- RUC del comercio (para las devoluciones).

En «Modo de prueba» se usan el sandbox y las credenciales públicas de Niubiz,
que la propia pantalla muestra.

## Tarjetas de prueba del sandbox

| Resultado | Tarjeta | Vencimiento | CVV |
|---|---|---|---|
| Aprobada (Visa) | `4551708161768059` | 03/28 | 111 |
| Aprobada (Mastercard) | `5160030000000317` | 03/28 | 111 |
| Aprobada (Amex) | `371064649323968` | 03/28 | 1111 |
| Rechazada 116, fondos insuficientes | `4041650444437904` | 03/28 | 111 |

## Validación contra el sandbox real (06/10/2026)

Hecha con `docs/niubiz/validar_sandbox_e2e.py` (Playwright + Chrome) sobre
`ol_pe_v19`:

| Caso | Resultado |
|---|---|
| Token de seguridad y sesión de pago | Correctos |
| Pago aprobado con Visa, Mastercard y Amex | Confirmados en Odoo, con autorización, traza y marca |
| Pago rechazado (116) | Vuelve a la página de pago con «Fondos insuficientes…» |
| Anulación el mismo día | Aceptada por Niubiz; transacción y pago contable cancelados |

## Cambios respecto del módulo original (`payment_niubiz`)

Corregidos al adaptarlo y validarlo:

1. **El modal no se abría**: el SDK exige el parámetro `action` y solo
   mostraba un `alert`. Ahora recibe la URL de retorno firmada.
2. **Anulación aceptada informada como rechazada**: Niubiz responde
   `actionCode 400` y `STATUS Voided`, el código ISO 8583 de reverso
   aceptado.
3. **La anulación no cambiaba nada**: Odoo 19 no deja pasar una transacción
   de «hecho» a «cancelado» sin permitirlo. Ahora se cancela la transacción y
   su pago contable.
4. **`res.partner.mobile` ya no existe en Odoo 19**: un cliente sin teléfono
   hacía fallar la sesión de pago.
5. **Rutas públicas sin firma**: quien adivinara una referencia podía marcar
   un pago como fallido o reabrirlo. Ahora exigen un token firmado con la
   referencia.
6. **La contraseña de la API** quedaba visible a cualquier usuario interno.
   Ahora es solo de administradores, y se borra al neutralizar la base.
7. **Conexión intermitente**: Niubiz corta a veces el saludo TLS. El token y
   la sesión, que no mueven dinero, se reintentan; la autorización, no.
8. **Pruebas**: 14 (el original no tenía).

## Licencia

OPL-1. El historial de versiones está en [`CHANGELOG.md`](CHANGELOG.md).
