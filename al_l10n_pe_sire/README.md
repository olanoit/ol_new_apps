# al_l10n_pe_sire — SIRE (RVIE / RCE) SUNAT

Conciliación con el **Sistema Integrado de Registros Electrónicos** de SUNAT:
descarga la propuesta del **RVIE** (ventas) y del **RCE** (compras) por API o
carga manual, la compara contra los comprobantes de Odoo y genera el TXT de
reemplazo y el XLSX de trabajo.

## Inicio rápido

1. Instalar el módulo (requiere `al_account_base` y `l10n_pe_edi`).
2. Ajustes → Contabilidad (PE) → **API SIRE (SUNAT)**: usuario/clave SOL y
   client_id/client_secret (generados en SOL → Credenciales de API SUNAT).
3. Menú **Perú → SIRE → Ventas (RVIE)** o **Compras (RCE)** → crear periodo.
4. Flujo: *Solicitar propuesta → Consultar ticket → Descargar propuesta →
   Desplegar SIRE → Desplegar sistema → Comparar*.
5. Revisar la pestaña **Diferencias** y descargar **XLSX** o **TXT de reemplazo**.

Sin credenciales API se puede marcar **Carga manual** y subir el TXT exportado
desde SUNAT Operaciones en Línea.

## Documentación

- Guía funcional: [`docs/README.md`](docs/README.md)
- Plan técnico: `../docs/sire/PLAN_MODULO_al_l10n_pe_sire.md`
- Demo/validación: `tools/sire_demo_data.py` (ejecutar vía `odoo-bin shell`)

## Tests

```bash
python3 odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_sire \
    --test-tags /al_l10n_pe_sire --stop-after-init --http-port 19799
```
