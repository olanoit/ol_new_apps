# Planillas Perú v19 — qué falta para cerrar la localización

Análisis del 2026-08-02 sobre los 7 módulos instalados en `ol_pe_v19`
(`al_hr_pe`, `_account`, `_attendance`, `_benefits`, `_import`, `_reports`,
`_public_holidays`), suite en verde: **103 tests**.

El plan de migración (fases 0-8) está cerrado. Lo que sigue no son restos
de la migración: son obligaciones peruanas que el sistema v18 tampoco
cubría o que quedaron marcadas como `TODO(faseN-revisar)`.

---

## 1. Qué ya está cubierto

| Obligación | Dónde |
|---|---|
| Boleta de pago (D.S. 001-98-TR) | `al_hr_pe_reports` — QWeb, un solo botón, envío con acuse HMAC |
| PLAME `.rem` / `.jor` / `.snl` / `.toc` | `al_hr_pe.hr.payslip.run` |
| AFPnet | `hr_payslip_run_export.afp_net` |
| CTS, gratificaciones + bono 9 %, vacaciones, liquidación de cese | `al_hr_pe_benefits` |
| Renta de 5ta categoría + certificado | `al_hr_pe_benefits` / `_reports` |
| Utilidades (D.L. 892), provisiones, subsidios EsSalud, adelantos y préstamos | `al_hr_pe_benefits` |
| Control de asistencia, HE 25/35/100, nocturnidad, ciclos atípicos N×M | `al_hr_pe_attendance` |
| Asientos contables de planilla y de BBSS | `al_hr_pe_account` |
| TXT bancarios (BCP, BBVA, Interbank, Scotiabank, BanBif) | `al_hr_pe_reports` |
| Contratos, certificado de trabajo, carta CTS | `al_hr_pe_reports` |
| Feriados nacionales 2026-2035 aplicados al calendario | `al_hr_pe_public_holidays` |

---

## 2. Huecos, por prioridad

### P1 — Obligación legal sin cobertura

**1. T-Registro (D.S. 015-2010-TR).**
No hay exportador ni modelo. Es el registro previo a la PLAME: altas,
bajas y modificaciones de trabajadores, y **derechohabientes**. El alta
debe hacerse el día que el trabajador entra y la baja dentro del día
siguiente al cese; incumplir es infracción grave (SUNAFIL).
*Alcance*: modelo de derechohabientes, campos T-Registro que faltan en
`hr.version` (nivel educativo, ocupación CIUO, discapacidad, tipo de
contrato SUNAT), y exportador del archivo de carga masiva.

**2. Derechohabientes.**
No existe el modelo. Bloquea el T-Registro, la acreditación en EsSalud y
la automatización de la asignación familiar. Es el prerrequisito de (1)
y (3).

**3. Asignación familiar (Ley 25129) automática.**
La regla `AF` existe y calcula el 10 % de la RMV, pero el derecho se
concede a mano: no hay control de hijos menores de 18 —o hasta 24 si
cursan estudios superiores— ni corte automático al cumplirse la edad.
Depende de (2).

**4. SCTR (D.S. 003-98-SA).**
`hr_contributions.xml` solo trae `SVLEY` (Vida Ley, D.Leg. 688). Falta el
SCTR salud y pensión para actividades de riesgo del Anexo 5: tasas por
entidad, marca de puesto de riesgo en la versión y su aporte en la
planilla. Sin esto, las empresas de construcción, minería o manufactura
no pueden usar el sistema.

### P2 — Rotura de flujo (obliga a registrar dos veces)

**5. Vacaciones y descansos médicos desde `hr.leave`.**
`TODO(fase3-revisar)` en `hr_vacation.py` y `TODO(fase4-revisar)` en
`hr_subsidies.py`. Hoy el récord vacacional y los subsidios se alimentan
de modelos propios, no de las ausencias nativas: el usuario registra la
vacación en `hr.leave` (para el calendario y el work entry) **y** en el
récord vacacional. Integrar por `hr_payroll_holidays` cierra el doble
registro y es la causa más probable de descuadres en el devengo.

**6. Estructura de quincena (`ADE_QUINCENAL` y reglas `*_AQ`).**
`TODO(fase4-revisar)` en `hr_fortnightly.py`: la quincena genera boletas
sobre la estructura BASE en vez de una propia. Funciona, pero mezcla los
conceptos del adelanto con los del mes y complica la lectura de la
boleta quincenal.

**7. Registro permanente de control de asistencia (D.S. 004-2006-TR).**
El tareaje calcula bien, pero no hay reporte exportable con el formato
que exige la fiscalización: el `TODO(fase6)` «reporte mensual Excel» no
llegó a la Fase 7. Ante una inspección SUNAFIL hay que armarlo a mano.

### P3 — Operativo

**8. Resumen de planilla en Excel.**
El «asiento planilla» de v18 (971 líneas) se declaró fuera de alcance en
la Fase 5. Es el reporte que usa contabilidad para conciliar; hoy se
suple con el asiento nativo.

**9. Cifrado de la boleta con el DNI.**
`TODO(fase7-revisar)`: v18 cifraba el PDF con reportlab. QWeb-PDF no
cifra; si el cliente lo exige, post-procesar con pypdf en un override de
`_render_qweb_pdf`.

**10. Cron de tasas AFP desde la SBS.**
Declarado fuera de alcance en el plan de migración (el wizard de consulta
sí se portó). Las tasas se actualizan a mano cada vez que la SBS las
cambia.

**11. Work entry type nocturno (`DLABN`) y regla del 35 % sobre la RMV.**
`TODO(fase6-revisar)`: la jornada nocturna se detecta y se calcula, pero
no tiene concepto propio en la boleta ni la sobretasa mínima legal del
35 % sobre la RMV (D.S. 007-2002-TR art. 8).

---

## 3. Orden sugerido

```
(2) Derechohabientes ──► (1) T-Registro ──► (3) Asignación familiar automática
                                     │
(4) SCTR ────────────────────────────┘   [desbloquea sectores de riesgo]

(5) hr.leave ──► quita el doble registro de vacaciones y subsidios
(7) Reporte de asistencia ──► cierra el riesgo de inspección
(6) (8) (9) (10) (11) ──► mejoras
```

Los tres primeros son un solo bloque de trabajo: comparten el modelo de
derechohabientes y los campos que faltan en `hr.version`.

---

## 4. Deuda técnica localizada (no bloquea)

* `pe.public.holiday` no sigue la convención `l10n_pe.*` del proyecto.
  Renombrarlo exige migración de datos; no compensa hoy.
* `TODO(fase5-revisar)` en `al_hr_pe_account`: cuatro decisiones de
  paridad con v18 pendientes de confirmar con contabilidad (cuentas de
  gasto por concepto, filtro `less_than_one_month`, `user_partner_id`).
* `TODO(fase2-revisar)` en los exportadores PLAME: la equivalencia
  «contrato ≈ grupo de reglas» y el criterio `ONP`/`SIN REGIMEN` por
  nombre en vez de por marca.
* `TODO(fase6-revisar)`: calendarios de dos semanas (`week_type`) no
  contemplados en el tareaje.
