OL-PAYROLL
==========

**Planillas y recursos humanos de Perú.**

Para qué es esta carpeta
------------------------

Nómina peruana sobre `hr_payroll` de Odoo 19: régimen general y de construcción civil, beneficios sociales (CTS, gratificaciones, vacaciones), asistencia, feriados, importación de novedades, asientos de planilla, boletas y reportes (PLAME, T-Registro, AFP Net).

Qué va aquí
-----------

- Reglas salariales, estructuras y contratos (`hr.version`) de la localización peruana.
- Beneficios sociales, asistencia, feriados e importación de novedades.
- Asiento contable de la planilla y reportes legales de planillas.

Qué no va aquí
--------------

- Configuración contable general (plan de cuentas, diarios) → `OL-ACCOUNTING/`.
- Gestión de obras y materiales, aunque sean de construcción → `OL-PROJECTS/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_hr_pe](al_hr_pe/) | 23.20261007 | OPL-1 | Localización peruana de nómina: tablas PLAME/AFP, campos laborales en hr.version, reglas salariales SUNAT y exportadores PLAME/AFPNet.
[al_hr_pe_account](al_hr_pe_account/) | 5.20261007 | OPL-1 | Asientos de planilla y beneficios sociales con distribución analítica opcional por compañía.
[al_hr_pe_attendance](al_hr_pe_attendance/) | 10.20261007 | OPL-1 | Capa peruana sobre planning EE: régimen atípico, monitor de asistencia, tareaje y horas extra.
[al_hr_pe_benefits](al_hr_pe_benefits/) | 12.20261007 | OPL-1 | CTS, gratificaciones, liquidaciones, renta 5ta, provisiones, subsidios, utilidades, vacaciones, préstamos y quincena.
[al_hr_pe_construction](al_hr_pe_construction/) | 16.20261007 | OPL-1 | Régimen de construcción civil: tabla salarial por convenio, categorías, BUC, BAE, bonificaciones por condiciones de trabajo, obras y CONAFOVICER.
[al_hr_pe_import](al_hr_pe_import/) | 5.20261007 | OPL-1 | Framework de importación Excel (openpyxl) con lotes, progreso en vivo y reporte de errores por fila para toda la suite de planillas Perú.
[al_hr_pe_public_holidays](al_hr_pe_public_holidays/) | 6.20261007 | OPL-1 | Calendario completo de 10 años de días festivos de Peru, listo para Odoo HR. Festivos nacionales y religiosos — aplicados automáticamente al resource.calendar como ausencias.
[al_hr_pe_reports](al_hr_pe_reports/) | 13.20261007 | OPL-1 | Boleta de pago, certificados, contratos y archivos TXT de pago masivo bancario.
[//]: # (end addons)
