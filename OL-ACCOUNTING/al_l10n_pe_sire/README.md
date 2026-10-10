# al_l10n_pe_sire — SIRE (RVIE / RCE) SUNAT

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Conciliación con el **Sistema Integrado de Registros Electrónicos** de SUNAT:
descarga la propuesta del **RVIE** (ventas) y del **RCE** (compras) por API o
carga manual, la compara contra los comprobantes de Odoo y genera el TXT de
reemplazo y el XLSX de trabajo.

## Inicio rápido

1. Instalar el módulo (requiere `al_account_base` y `l10n_pe_edi`).
2. Ajustes → Perú → **SIRE (RVIE / RCE)**: usuario/clave SOL y
   client_id/client_secret (generados en SOL → Credenciales de API SUNAT).
3. Menú **Perú → SIRE → Ventas (RVIE)** o **Compras (RCE)** → crear periodo.
4. Flujo: *Solicitar propuesta → Consultar ticket → Descargar propuesta →
   Desplegar SIRE → Desplegar sistema → Comparar*.
5. Revisar la pestaña **Diferencias** y descargar **XLSX** o **TXT de reemplazo**.
6. Enviar a SUNAT: **Aceptar propuesta** (solo si no hay diferencias) o
   **Enviar reemplazo**, y después **Registrar preliminar**.

## Envío a SUNAT

| Acción | Qué hace | Cuándo |
|---|---|---|
| **Aceptar propuesta** | Da por buena la propuesta tal cual | Solo si la comparación no encontró ninguna diferencia — si las hay, el botón se niega y explica por qué |
| **Enviar reemplazo** | Sube el TXT con las líneas del sistema | Cuando el sistema es la verdad y la propuesta no |
| **Consultar envío** | Estado del ticket del envío | Tras cualquiera de los dos |
| **Registrar preliminar** | Deja el preliminar registrado en SUNAT | Después del envío |

Los dos envíos son excluyentes y solo se admite uno por periodo: un segundo
intento se rechaza mostrando el ticket del primero. Una vez enviado, *Reiniciar*
queda bloqueado — rehacer las líneas no deshace lo declarado.

La **generación del registro** se completa en el portal de SUNAT: no hay
servicio web para hacerla desde fuera.

## Validación antes del envío

Al desplegar el sistema (y con el botón **Validar**) cada línea se revisa con
las reglas de SUNAT; las que fallan aparecen en la pestaña **Observaciones** y
**Enviar reemplazo** se niega mientras haya alguna:

- RUC con dígito verificador (módulo 11), también el de la compañía; DNI de 8 dígitos.
- Tipo de comprobante de la tabla 10; en 01/03/04/07/08, serie de 4
  caracteres y número de hasta 8 dígitos.
- IGV/IPM al 18 % o al 10 % (Ley 31556) de la base, IVAP al 4 %, total igual a
  la suma de bases e impuestos (tolerancia S/ 1 por comprobante).
- Moneda ISO con tipo de cambio, fechas dentro del periodo, notas con su
  comprobante modificado, factura con RUC y, en el RCE, fecha de vencimiento en
  los tipos que la exigen.

## Consulta automática de tickets

Tras solicitar la propuesta, aceptarla o enviar el reemplazo, un cron consulta
el ticket con espera creciente (2, 4, 8, 16, 32 y luego 60 minutos, hasta 30
intentos). La propuesta se descarga sola al terminar; si SUNAT falla o se
agotan los intentos, queda una actividad en el periodo. Los botones manuales
siguen disponibles.

## RCE: destino de las compras gravadas

La columna sale del grupo del impuesto del plan peruano: `IGV G NG 18%` →
DGNG, `IGV NG 18%` → DNG, el resto → DG.

Sin credenciales API se puede marcar **Carga manual** y subir el TXT exportado
desde SUNAT Operaciones en Línea; el TXT de reemplazo también se descarga para
cargarlo a mano en SOL.

> **Sobre la carga por API**: los endpoints y los metadatos salen de los manuales
> oficiales de servicios web API SIRE (Compras v22 y Ventas v22) y los tests fijan
> que se envíen exactamente esos códigos. La subida usa el protocolo **TUS 1.0.0**,
> que es el que SUNAT documenta. No se ha podido probar contra el servicio real por
> falta de credenciales de producción: la primera ejecución conviene hacerla con un
> periodo de prueba.

## Operaciones con SUNAT (pestaña «SUNAT»)

Cada llamada queda en el historial de operaciones del periodo con su ticket,
el archivo enviado y los reportes que SUNAT devuelve. Un cron consulta los
tickets con espera creciente y adjunta los reportes al terminar.

| Fase | Qué hace | Dónde |
|---|---|---|
| Reportes | Reportes del ticket (inconsistencias del envío), resumen de inconsistencias (tipos 1-4), inconsistencias del preliminar registrado y constancia de recepción | Pestaña SUNAT |
| Tipo de cambio | RVIE: JSON a `guardacomplementomasivo`; RCE: archivo RCETCA (anexo 10) en multipart; RVIE individual (5.12) | Pestaña SUNAT y acción por comprobante |
| No domiciliados | Registro 8.5 (anexo 9, 35 campos, codProceso 56) con los datos de renta de la factura y el país SUNAT (tabla 16); exportación del preliminar | Pestaña «No domiciliados» del RCE; pestaña «No domiciliado (SIRE)» de la factura |
| Complementos | RCE: completar o reubicar datos (RCECOM, 54), excluir o volver a incluir (RCEINEX, 55); nuevos CP en la propuesta (CPF / CP, 1) o en el preliminar (4) | Acciones por comprobante |
| Ajustes posteriores | Del periodo (RVIE anexo 4, RCE anexo 12 en 8.4 y 8.5) con el CAR del anotado; de periodos anteriores al SIRE en formato general (RVIE 5.1, RCE 5.1); envío de los ajustes del RCE (5.19/5.22/5.25) | Acciones por comprobante, «Otras acciones» y la operación |
| Eliminaciones y crédito fiscal | Exclusión definitiva (RVIE), eliminar de la propuesta o del preliminar, eliminar reemplazo o preliminar; reintegro, crédito especial y prorrata (RCE) | Acciones por comprobante y «Otras acciones» (solo responsables) |

Fuentes: manuales API SIRE v22 y anexos de las R.S. 112-2021, 040-2022 y
138-2023 en `docs/sire/oficial/`; resumen en `docs/sire/SERVICIOS_RVIE.md`,
`SERVICIOS_RCE.md` y `ESTRUCTURAS_TXT.md`.

**Decisiones ante contradicciones del manual** (sin probar contra SUNAT):

- Tipo de cambio RVIE: fecha `AAAA-MM-DD` y moneda ISO, como el ejemplo (la tabla dice `dd/mm/aaaa` y código numérico).
- Ajustes RVIE: `codProceso` 6/7 de la tabla (el ejemplo usa 87/88).
- Periodo del archivo de no domiciliados: `AAAAMM` (la norma dice «AAAAMM3.», una errata).
- Número de ajuste posterior del RCE: se busca en `listarcap` (respuesta no documentada); si no aparece, se escribe en la operación.
- Constancia de recepción: el nombre se deduce del registro (`LE…01OIM2.pdf`) probando los indicadores; se puede fijar a mano.
- Quedan fuera los ajustes de periodos anteriores en formato simplificado (5.2 / 5.3) y de no domiciliados anteriores al SIRE (5.2).

## Documentación

- Guía funcional: [`docs/README.md`](docs/README.md)
- Plan técnico: `../docs/sire/PLAN_MODULO_al_l10n_pe_sire.md`
- Demo/validación: `docs/sire/pruebas/sire_demo_data.py` (en la raíz del repositorio) (ejecutar vía `odoo-bin shell`)

## Tests

```bash
python3 odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_sire \
    --test-tags /al_l10n_pe_sire --stop-after-init --http-port 19799
```
