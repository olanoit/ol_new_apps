# Cobranza y recaudación bancaria: prueba funcional

Fecha: 22/10/2026. Base `test_pe_collection` (compañía PE Company, plan contable peruano, es_PE).
Versiones: `al_l10n_pe_collection` 3.20261022, `al_l10n_pe_collection_sale` 1.20261022,
`al_l10n_pe_bank_collection` 4.20261022.

## Cómo se ejecuta

```bash
cd ~/odoo/ce19
# 1. Flujos completos (32 comprobaciones; idempotente, cada corrida agrega documentos)
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d test_pe_collection --no-http \
    < myodoo/ol_new_apps/docs/cobranza/pruebas/prueba_funcional_cobranza.py
# 2. Interfaz (12 pantallas): con un servidor en 18069 sobre la misma base
FICHAS_URL=http://127.0.0.1:18069 FICHAS_DB=test_pe_collection \
    python3 myodoo/ol_new_apps/docs/cobranza/pruebas/recorrido_interfaz.py
```

## Datos

Gestores Rosa Quispe Mamani (Lima Norte) y Luis Mendoza Torres (Arequipa); clientes
Agroindustrias San Lorenzo, Distribuidora El Sol, Ferretería Los Andes, Comercial Misti (RUC) y
Juana Huamán Rojas (DNI, consumidora); facturas de 10 a 400 días de atraso; convenio BBVA.

## Resultado

| Etapa | Qué se probó | Resultado |
|---|---|---|
| F1 Cartera | Gestor, zona y tramo; la gestora solo ve lo suyo | 2/2 |
| F2 Gestiones | Gestión con compromiso hecha por la gestora; llamada a consumidora a las 21:00 rechazada (art. 62) y correo permitido; compromiso vencido incumplido con actividad | 4/4 |
| F3 Reclamos | Saca la factura del seguimiento y la marca en disputa; al cerrarse vuelve; ofrece la nota de crédito | 4/4 |
| F4 Riesgo y bloqueo | Cliente con 400 días calificado D y bloqueado; pedido de venta bloqueado; liberado por el administrador | 4/4 |
| F5 Intereses | 12 % TEA a 45 días = S/ 13.55 en el estado de cuenta y en la nota de débito en borrador | 2/2 |
| F6 Provisión | Propuesta con gestiones, asiento 68711/1911, recuperación 7551, expediente con la carta, castigo conciliado | 5/5 |
| F7 Centrales | Aviso previo, plazo, reporte y «por retirar» al pagarse | 3/3 |
| F8 Recaudación BBVA | Archivo de 360 bytes, respuesta identificada y pagada, el mismo archivo otra vez no se paga | 4/4 |
| F9 Seguridad y crons | Visibilidad por gestor, provisiones y liberación solo del administrador, crons sin error | 4/4 |
| Interfaz | 12 pantallas (menús y primer registro) sin diálogos ni errores de JavaScript | 12/12 |

Además: 71 pruebas automáticas en verde (cobranza, bloqueo de ventas y recaudación).

## Hallazgos corregidos

1. **Calificación de clientes sin historial** (defecto): un cliente con una deuda de 400 días y
   ningún pago salía **B**, porque el atraso promedio solo miraba facturas pagadas. Ahora el
   atraso pondera también lo vencido que sigue abierto. Prueba de regresión agregada.
2. **Pruebas dependientes de los datos**: chocaban con diarios y convenios existentes en la base
   (`PROV`, «BBVA soles»); usan nombres propios.
3. **Cola de trabajo vacía para el administrador**: el filtro «Mis clientes» se aplica solo a los
   gestores.
4. **Respuesta del banco**: «Crear pagos y conciliar» ya no aparece si no hay cobros por pagar
   (todo duplicado o descartado), y el estado de cada cobro se ve sin desplazarse.
5. **Listas**: la columna de los documentos decía «Asiento contable»; ahora «Documento» y
   «Vencimiento». Columnas de la provisión con títulos cortos.

## Observaciones (sin cambio)

- La cola de trabajo muestra la calificación del último cálculo diario: un cliente que pagó hoy
  sigue con prioridad hasta la próxima ejecución o hasta pulsar **Calificar** en su ficha.
- Las fechas del aviso a centrales salen en el idioma del cliente (en esta base, inglés).

## Agencias externas y comisiones (v7, 22/10/2026)

`al_l10n_pe_collection` 7.20261022. Se corre después de la prueba anterior:

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d test_pe_collection --no-http \
    < myodoo/ol_new_apps/docs/cobranza/pruebas/prueba_funcional_comisiones.py
# Interfaz como la agencia (usuario y clave de prueba en el script):
FICHAS_URL=http://127.0.0.1:18069 FICHAS_DB=test_pe_collection FICHAS_USER=estudio_recupera \
    FICHAS_PASSWORD=<clave del script> python3 myodoo/ol_new_apps/docs/cobranza/pruebas/recorrido_interfaz.py
```

Agencia «Estudio Jurídico Recupera» con una usuaria; se le entregan Ferretería Los Andes y
Comercial Misti.

| Etapa | Qué se probó | Resultado |
|---|---|---|
| F10 Agencia | Grupo automático; cartera entregada; la agencia solo ve sus dos clientes, no lee otras facturas, gestiona a sus clientes y no a los ajenos | 6/6 |
| F11 Comisiones | Gestora: S/ 4 000 a 50 días al 3 % = S/ 120, sin lo cobrado por la agencia; agencia: 6 % a 95 y 150 días; factura de proveedor en borrador con IGV; cada uno ve solo sus liquidaciones | 6/6 |
| Interfaz | 17 pantallas como administrador (5 nuevas) y 6 como la agencia, sin errores | 23/23 |

Además: 89 pruebas automáticas en verde (cobranza 66, bloqueo de ventas, recaudación y PagoEfectivo).
El menú de la agencia muestra solo Cartera (cola, cartera, antigüedad, cartera de agencias),
Gestión (gestiones, compromisos) y Comisiones; el Tablero quedó solo para gestores.

## Cobranza judicial (v8, 22/10/2026)

`prueba_funcional_judicial.py` (después de la de comisiones): demanda ejecutiva a Ferretería
Los Andes por S/ 18 000, llevada por el Estudio Jurídico Recupera.

| Etapa | Qué se probó | Resultado |
|---|---|---|
| F12 Judicial | El estudio registra expediente, actuaciones y gastos y presenta la demanda; petitorio congelado; la factura sale del seguimiento; plazo agendado al responsable; el estudio no ve otros procesos; la provisión acepta la deuda de 4 meses por la demanda | 6/6 |
| Interfaz | Proceso judicial como administrador y como el estudio, sin errores | 9/9 |

96 pruebas automáticas en verde (7 nuevas de cobranza judicial).
