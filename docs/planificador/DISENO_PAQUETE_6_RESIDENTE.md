# Diseño del paquete 6 · rol Residente en el portal de obra

Fuente: «Requerimiento de desarrollo · Paquete 6 · Rol Residente en el portal
de obra», versión 1.1 (06-nov-2026), requerimientos CR-48 a CR-58 y mejoras de
experiencia U1 a U20. Este documento recoge cómo se desarrolló, las decisiones
y cómo se prueba cada criterio. Las pantallas del requerimiento usan la obra de
prueba; aquí no se copian nombres de obras, personas ni montos: el repositorio
es público.

Manda sobre este documento `ARQUITECTURA_COMUN.md`, en lo común (sección 8,
filas del 07-nov-2026).

## 1. Entregas

Se desarrolló en cuatro entregas, en este orden, todas el 07-nov-2026.

| Entrega | Requerimientos | Commit | Módulos |
|---|---|---|---|
| 1 | CR-48 rol Residente y «Mi día», CR-49 «Por validar», CR-50 «Por aprobar», regla «Sin señal» | `347ecd69` | `al_construction_portal` 9, `al_construction_material_request` 35, `al_construction_planner_approvals` 11 |
| 2 | CR-56 partes del día y «Cerrar el día», CR-51 deductivo, CR-52 solicitudes, CR-53 cambio del cliente | `8197b631` | `al_construction_portal` 10, `al_construction_portal_sale` 1 (nuevo) |
| 3 | CR-58 pestaña Obra (Resumen, Semana, Tareas), CR-54 Gantt | `39f6beea` | `al_construction_portal` 11 |
| 4 | CR-57 avisos al celular, CR-55 caja chica y entrega a rendir | `0c5f5875` | `al_construction_portal` 12, `al_construction_portal_cash_fund` 1 (nuevo) |

## 2. Decisiones

| # | Punto | Decisión | Dónde |
|---|---|---|---|
| D1 | CR-55, sección 11, decisión 1: residente sin ficha de empleado | Se usa la entrega a rendir o caja chica de `al_l10n_pe_cash_fund`, que es de un contacto (`partner_id`), no de un empleado. Sirve igual con ficha y sin ella, sin pasar por Gastos. Decidido por Vicente el 07-nov-2026 | `al_construction_portal_cash_fund` |
| D2 | CR-50, sección 11, decisión 2: revisor «Residente de la obra» | La validación por niveles de OCA acepta un usuario de portal como revisor por campo (`tier.review._get_reviewers` no filtra usuarios internos). Se usa el campo `construction_site_resident_id` del requerimiento; no hace falta un tipo de revisor nuevo | `al_construction_portal/models/material_request.py` |
| D3 | Validar y aprobar sin señal | Cada decisión lleva lo que vio el residente (cantidad del avance; nivel de aprobación del requerimiento) y Odoo la vuelve a comprobar al recibirla | `resident_service.py` |
| D4 | Requerimientos sin regla | Nuevo valor «Pasar al residente de la obra (portal)»; sin residente marcado, pasa al jefe de la obra. Es un gancho de la compañía (`_construction_site_fallback_field`) que usan las dos máquinas de aprobación | `al_construction_material_request`, `al_construction_planner_approvals` |
| D5 | Parte diario | Uno por persona, obra y día (también lo envía la contrata) y uno de obra por día, que arma el residente al «Cerrar el día» | `daily_report.py` |
| D6 | Solicitud de contrata o cuadrilla | Actividad en la partida para el jefe de la obra, sin modelo nuevo; el estado se lee de la actividad y de la asignación | `resident_records.py` |
| D7 | Cambio del cliente | Vive en el puente `al_construction_portal_sale`, porque el cambio de obra es del puente de Ventas | `al_construction_portal_sale` |
| D8 | Pestaña Obra | Avance real y montos del tablero del escritorio; fechas de las etapas de cada ambiente (como el Cronograma); hitos del Gantt de proyectos. No se usa la lectura completa del Gantt, que solo admite usuarios internos. Montos solo si la compañía los activa | `site_overview.py` |
| D9 | Avisos al celular | Envío web nativo de Odoo (`mail.push.device`), que alcanza a usuarios de portal. WhatsApp no está instalado en la base de CREVAL. Reglas por papel en «Avisos al celular» | `portal_notice.py`, `sw.js` |
| D10 | Lectura de la foto del comprobante (CR-55, punto 1, «si aplica») | No se incluye: depende del servicio de extracción de pago de Odoo | — |

## 3. Correcciones que salieron al desarrollar

- Con la aplicación Aprobaciones, un requerimiento pedido desde el portal no
  llegaba a enviarse: el nombre del tipo de aprobación se leía con el usuario
  de portal (`construction_approval_mixin.py`).
- Un usuario de portal no puede adjuntar a un mensaje archivos que no vengan
  del redactor (`_process_attachments_for_post`): los PDF que se envían desde
  el portal se crean con el mensaje.

## 4. Pruebas del requerimiento (sección 9)

Las pruebas automáticas reproducen cada caso con datos ficticios en
`test_pe_creval`. El 07-nov-2026 se repitieron P1 a P16 y P18 en creval-dev
por la API real del portal (residente de portal de prueba, capataz y contrata
de prueba, obra de prueba), con la aplicación real revisada en celular y
tablet: todas pasaron. Salió una corrección: la curva de avance y el Gantt
llegan hasta hoy aunque el plan haya terminado antes (`6f536565`).

Configuración que no está en la obra de prueba de creval-dev:

- La obra no tiene sede de marcación: sin coordenadas ni radio, no salen el
  aviso de GPS ni el aviso «fuera del radio».
- La cuenta 1413000 «Personal - Entregas a rendir cuenta» está archivada: no
  se puede entregar un fondo, y P11 no se probó en creval-dev (sí en las
  pruebas automáticas, con el paso de Contabilidad).

| N.º | Prueba | Prueba automática | Estado |
|---|---|---|---|
| P1 | Residente entra con usuario y clave y ve «Mi día» | `test_resident.TestResident.test_role_and_scope` | Verde |
| P2 | Llamar al servicio de otra obra | `test_role_and_scope` | Verde |
| P3 | Avance del capataz en «Por validar» | `test_validate_reject_rework` | Verde |
| P4 | Validar, rechazar y re-trabajo con autor y aviso | `test_validate_reject_rework` | Verde |
| P5 | Requerimiento «En aprobación» con el residente | `test_request_approval_by_resident`, `test_request_reject_and_two_levels` | Verde |
| P6 | Aprobar el requerimiento | `test_request_approval_by_resident`, `test_request_approval_with_approvals_app` | Verde, con los dos motores |
| P7 | Deductivo con foto | `test_resident_records.test_deduction_with_photo` | Verde |
| P8 | Solicitud de cuadrilla y estado «Asignada» | `test_crew_request_states` | Verde |
| P9 | Cambio del cliente con firma y constancia | `al_construction_portal_sale` · `test_change_with_signature_and_record` | Verde; PDF revisado por HTTP |
| P10 | Cronograma en tablet y celular | Recorrido con Playwright (capturas en 390 y 1024 px) | Verde |
| P11 | Comprobante del residente sin ficha de empleado | `al_construction_portal_cash_fund` · `test_receipt_and_settlement` | Verde, con el paso de Contabilidad |
| P12 | Entrar con QR y PIN no muestra las bandejas | `test_role_and_scope` | Verde |
| P13 | Validación sin señal rechazada en el escritorio | `test_offline_decision_rechecked` | Verde |
| P14 | Aprobación sin señal | `test_request_approval_by_resident` | Verde |
| P15 | Partes del día del capataz y la contrata | `test_daily_parts_and_close_day` | Verde |
| P16 | «Cerrar el día» con PDF al cliente | `test_close_day_sends_pdf_to_client` | Verde; PDF revisado por HTTP |
| P17 | Pedido urgente llega al celular con la aplicación cerrada | `test_portal_notice.test_urgent_request_reaches_resident` (el mensaje) | El mensaje al residente sale en creval-dev; falta la prueba con un teléfono: el navegador automático no da permiso de avisos |
| P18 | Resumen igual al tablero del escritorio | `test_site_overview.test_summary_matches_desktop_board` | Verde; medido en la obra más grande de creval-dev (432 líneas, 1,5 s) |

## 5. Configuración por obra

1. Personal del portal: el residente con el papel «Residente de obra» y
   «Aprobador por defecto de la obra». No necesita ficha de empleado.
2. «Contacto del cliente en obra» en la pestaña Portal de obra.
3. Requerimientos: «Pasar al residente de la obra (portal)» o el revisor por
   campo «Residente de la obra» en las reglas. En la validación por niveles
   revisa primero la regla de secuencia más alta.
4. Caja chica: la entrega a rendir o la caja chica a nombre del contacto del
   residente, entregada.
5. Ajustes: montos en la pestaña Obra y umbral de partida en riesgo.
   Configuración: motivos del residente y avisos al celular.
