# Cobranza (AL)

Documentación funcional: [Cobranza](../../mkdocs/content/applications/finance/accounting/collection.md) ·
análisis y plan: [docs/cobranza/ANALISIS_Y_PLAN_COBRANZA.md](../../docs/cobranza/ANALISIS_Y_PLAN_COBRANZA.md)

Aplicación `al_l10n_pe_collection` sobre `account_followup` (Enterprise):

- **Gestor** = `res.partner.followup_responsible_id` (company_dependent, jsonb); zona
  `l10n_pe_collection_zone_id` también por compañía.
- `l10n_pe.collection.portfolio`: vista SQL de las cuotas abiertas por cobrar; lee gestor y
  zona del jsonb con la compañía del apunte o su raíz; tramo por `l10n_pe.collection.bucket`.
  Las cuentas que no son cobranza (anticipos, detracción) se excluyen en las acciones
  (`res.company._l10n_pe_collection_excluded_accounts`), no en el SQL.
- `l10n_pe.collection.action` (gestión) crea `l10n_pe.collection.promise` si el resultado es
  compromiso y programa la actividad del gestor en el cliente.
- `l10n_pe.collection.promise`: cobrado = baja del saldo de sus apuntes desde el pacto (o
  abonos en bancos/cajas del cliente sin apuntes); cron `_cron_collection_promises` evalúa y
  envía recordatorios.
- `l10n_pe.collection.forecast`: fecha esperada por compromiso (con reparto FIFO si no tiene
  apuntes), atraso promedio (`res.partner._l10n_pe_collection_average_delay`) o vencimiento;
  probabilidad del tramo; ajustes conservados por apunte; XLSX.
- `l10n_pe.collection.tools`: alcance por gestor/zona y cobrado de un periodo (abonos de
  diarios de banco y caja en cuentas por cobrar).
- `l10n_pe.collection.target`, `l10n_pe.collection.dashboard` (transitorio) y cron
  `_cron_collection_digest` (QWeb `collection_digest_mail` → `mail.mail`).
- Estado de cuenta: reporte sobre `res.partner` con `al_report_base.report_pe_page`; plantilla
  de correo con el PDF adjunto y asistente de envío masivo.
- Seguridad: grupos Gestor / Administrador (`res.groups.privilege`), reglas «solo lo propio»
  para el gestor y multicompañía. Las acciones de servidor de cartera llevan `group_ids`
  (sin grupo, Odoo exige escritura sobre el modelo, y la cartera es de solo lectura).
