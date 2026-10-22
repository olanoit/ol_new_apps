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
