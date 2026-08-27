# Validación de la localización peruana

Material para verificar, módulo a módulo, los desarrollos de localización
peruana sobre Odoo 19 (configuración `cfg/my/pe.cfg`, base `ol_pe_v19`).

## Qué hay aquí

| Archivo | Para qué sirve |
| --- | --- |
| `ANALISIS_VALIDACION_LOCALIZACION_PE.md` | Informe de la validación: cobertura por módulo, resultado de cada suite y hallazgos. |
| `pruebas/auditoria_localizacion_pe.py` | Auditoría **de solo lectura** sobre una base real: comprueba que lo instalado está además configurado (catálogos, series, credenciales, parámetros de nómina). |
| `pruebas/run_tests.sh` | Lanzador de la batería de pruebas unitarias módulo a módulo, con un log por módulo y un resumen. |
| `pruebas/flujo_retencion_detraccion.py` | Recorre de punta a punta los ciclos de retención de IGV y detracción SPOT, y el cruce entre ambos. Escribe y hace `rollback`. |

## 1. Pruebas unitarias, módulo a módulo

Las pruebas se ejecutan **sobre un clon** de la base, nunca sobre
`ol_pe_v19`: `--test-enable` obliga a actualizar el módulo y eso reescribe
sus datos XML.

```bash
# Clonar la base (con el servidor parado)
psql -h localhost -U odoo -d postgres -c "CREATE DATABASE ol_pe_v19_qa TEMPLATE ol_pe_v19;"

# Batería completa (un log por módulo en el directorio de logs)
docs/validacion/pruebas/run_tests.sh al_account_base al_l10n_pe_invoice ...

# O un módulo suelto
cd /home/och/odoo/ce19
.venv/bin/python3 odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19_qa --no-http --stop-after-init \
    -u al_l10n_pe_ple --test-enable --test-tags /al_l10n_pe_ple --log-level=test
```

## 2. Auditoría funcional sobre la base real

No escribe nada (termina con `rollback`), así que se puede lanzar contra
la base de trabajo:

```bash
cd /home/och/odoo/ce19
.venv/bin/python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http --log-level=warn \
    < myodoo/ol_new_apps/docs/validacion/pruebas/auditoria_localizacion_pe.py
```

Cada línea sale como `OK` / `AVISO` / `FALLA`:

* **FALLA** — impide operar: falta un dato imprescindible o el modelo no
  responde.
* **AVISO** — configuración pendiente de puesta en marcha (una credencial
  sin cargar, una cuenta sin asignar). No es un defecto del módulo.

El detalle queda además en `/tmp/auditoria_localizacion_pe.json`.

## 3. Flujo de retención y detracción

Recorre los dos regímenes completos —factura, publicación, reparto del
asiento, pago, constancia y comprobante electrónico— sobre el clon.
Escribe en la base durante la ejecución y termina en `rollback`, pero
conviene lanzarlo sobre el clon y no sobre la base de trabajo:

```bash
cd /home/och/odoo/ce19
.venv/bin/python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19_qa --no-http --log-level=warn \
    < myodoo/ol_new_apps/docs/validacion/pruebas/flujo_retencion_detraccion.py
```

Lo que falte de configuración lo siembra al vuelo y lo dice como
`AVISO`, de modo que el recorrido llega hasta el final aunque la base no
esté puesta a punto. Es la prueba que destapó H-09.

## 4. Pruebas funcionales de planillas

Los guiones de la suite de nómina viven aparte, en
`docs/planillas/pruebas/` (fases 1 a 9); siembran datos y por eso se
ejecutan sobre una base desechable.
