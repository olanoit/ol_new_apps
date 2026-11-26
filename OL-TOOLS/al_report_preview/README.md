# Reportes PDF en el navegador (AL)

Documentación funcional: [Reportes PDF en el navegador](../../mkdocs/content/applications/general/report_preview.md)

Módulo `al_report_preview` para Odoo 19.

Abre los reportes PDF en una pestaña del navegador en vez de descargarlos,
para todos los reportes o solo para los que se elijan.

- Ajuste general `al_report_preview.scope` (**Ajustes ▸ Ajustes generales ▸
  Reportes PDF**): `all` (todos, valor por defecto) o `selected` (solo los
  elegidos).
- `ir.actions.report.al_preview_mode`: `default` (según el ajuste general),
  `preview` (abrir en el navegador) o `download` (descargar).
- `ir.actions.report.al_preview_in_browser`: resultado calculado; viaja al
  cliente web en la acción (`_get_readable_fields` para el menú Imprimir y
  `report_action()` para los botones).
- Cliente web: manejador `al_report_preview` del registro
  `ir.actions.report handlers`. Abre `/report/pdf/...?al_preview=1` en una
  pestaña; si el reporte no está marcado, falta wkhtmltopdf o el navegador
  bloquea la pestaña, devuelve `false` y sigue la descarga nativa.
- Controlador: `report_routes` llama a `super()` y, solo con `al_preview`,
  agrega `Content-Disposition: inline` con el nombre de archivo del reporte
  (`print_report_name`). `/report/download` no cambia.

Con `al_account_base` instalado, el puente `al_l10n_pe_report_preview`
(`auto_install`) repite el ajuste en **Ajustes ▸ Perú**.

No instalar junto con `prt_report_attachment_preview` (Cetmix): ese módulo
abre todos los PDF sin mirar la configuración.

## Pruebas

```bash
.venv/bin/python odoo-bin -c cfg/my/pe.cfg -d test_pe_report_preview -i al_report_preview \
  --test-enable --test-tags /al_report_preview --stop-after-init --workers=0 \
  --http-port=18069 --gevent-port=18072
```
