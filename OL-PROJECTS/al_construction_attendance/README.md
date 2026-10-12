# Sedes, marcación y costo de personal de obra (AL)

Documentación funcional: [Portal de obra, sedes y marcación](../../mkdocs/content/applications/services/project/construction/planning/site_portal.md)

Fases 17 y 18 del paquete de mejoras v1.5 del planificador de obra. Une
`al_construction_planner` con la sede de obra de `al_hr_pe_construction`;
se instala solo cuando están ambos y Asistencias.

## Modelos

| Modelo | Qué guarda |
|---|---|
| `l10n_pe.hr.construction.site` (heredado) | Obra, ubicación, radio, hora límite, etapa por defecto y clave del quiosco |
| `construction.contractor.worker` | Personal de contratas: documento, PIN, contrata y SCTR |
| `construction.contractor.attendance` | Marcación de contratas en la sede (quiosco o portal) |
| `hr.attendance` (heredado) | Distancia a la sede, fuera de rango y fuera de hora |
| `construction.task.progress` (heredado) | `attendance_ok`: la contrata marcó en la obra ese día |
| `construction.labor.cost.allocation` y `.line` | Cierre mensual de costo de personal por sede (P-29) |

## Rutas

| Ruta | Autenticación | Uso |
|---|---|---|
| `/obra/quiosco/<sede>/<clave>` | pública, clave HMAC de la sede | Quiosco de marcación (P-27) |
| `/my/obra/parte` | usuario de portal | Parte diario de la cuadrilla (P-26) |

## Costo de personal

`hr.payslip._l10n_pe_site_cost_keys` suma a cada clave de distribución que es
solo la cuenta de una sede la etapa por defecto de la sede y la partida MODF
de la compañía. El cierre mensual valoriza las horas de marcación con
`hr.employee.hourly_cost` y, al publicarse, crea los apuntes analíticos; si la
planilla ya reparte su costo por sede, el cierre solo se usa para contrastar.
