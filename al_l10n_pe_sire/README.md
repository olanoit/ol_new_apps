# al_l10n_pe_sire — SIRE (RVIE / RCE) SUNAT

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

Sin credenciales API se puede marcar **Carga manual** y subir el TXT exportado
desde SUNAT Operaciones en Línea; el TXT de reemplazo también se descarga para
cargarlo a mano en SOL.

> **Sobre la carga por API**: los endpoints y los metadatos salen de los manuales
> oficiales de servicios web API SIRE (Compras v22 y Ventas v22) y los tests fijan
> que se envíen exactamente esos códigos. La subida usa el protocolo **TUS 1.0.0**,
> que es el que SUNAT documenta. No se ha podido probar contra el servicio real por
> falta de credenciales de producción: la primera ejecución conviene hacerla con un
> periodo de prueba.

## Documentación

- Guía funcional: [`docs/README.md`](docs/README.md)
- Plan técnico: `../docs/sire/PLAN_MODULO_al_l10n_pe_sire.md`
- Demo/validación: `tools/sire_demo_data.py` (ejecutar vía `odoo-bin shell`)

## Tests

```bash
python3 odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_sire \
    --test-tags /al_l10n_pe_sire --stop-after-init --http-port 19799
```
