Historial de cambios — Planillas Perú - Construcción civil (AL)
===============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_hr_pe_construction.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 18.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 17.20261008 — 08/10/2026

- Los datos de construcción civil del trabajador pasan a «Planilla PE ▸ Construcción civil»; nombres legibles en el resumen CONAFOVICER y la tabla de jornales.

## 16.20261007 — 07/10/2026

- Corregido: los códigos PLAME del SCTR estaban invertidos (salud iba como 0805, que es pensión). Ahora usa los mismos de la estructura general, según la entidad contratada.

## 15.20261007 — 07/10/2026

- El dominical (D.S.O.) ya no se infla en una semana con feriado trabajado: el feriado trabajado se paga aparte y no genera otro sexto.
- Gratificación de la semana que cruza el 31 de julio o el 31 de diciembre: cada día devenga en su ventana (Fiestas Patrias ÷210, Navidad ÷150). Antes toda la semana tomaba la del mes de cierre.

## 14.20261007 — 07/10/2026

- Códigos PLAME (tabla 22) de construcción corregidos: descanso 0115, BUC 0311, movilidad 0909, bonificaciones por altura/contacto con agua/cota 0303-0310, escolaridad 0211 y CONAFOVICER 0602.
- Asignación escolar para hijos con estudios técnicos o superiores hasta los 24 años (convenio vigente; el módulo traía 21). Las compañías con el valor antiguo se actualizan solas.

## 13.20261007 — 07/10/2026

- Corregido: las horas extra que vuelca el tareaje (25 % y 35 % del régimen general) no se pagaban en construcción; ahora se pagan al 60 % y al 100 % del convenio.
- Una boleta en borrador creada antes de activar la tabla del convenio toma el jornal al calcularse (antes quedaba en 0); un jornal corregido a mano se respeta.

## 12.20260925 — 27/09/2026

- El feriado no laborado se paga: entra en los días pagados con su jornal, D.S.O. y BUC (D.Leg. 713). Antes una semana con feriado cobraba un jornal de menos.
- Trabajar en feriado o en el día de descanso paga la sobretasa del 100 % sobre el jornal (regla FER100, concepto SUNAT 0107).
- La movilidad solo se paga por los días en que se acude a la obra: ya no en vacaciones, descanso médico, licencias ni feriados no laborados.
- Una tabla salarial propia de la compañía sustituye de verdad a la nacional en las mismas fechas; antes ganaba siempre la nacional.
- Las boletas confirmadas conservan su jornal y su categoría aunque después cambie la ficha del trabajador; la boleta impresa muestra la categoría con la que se pagó.
- El resumen CONAFOVICER deposita lo retenido en cada boleta, aunque la tasa haya cambiado después. Reabrir un resumen ya pagado queda reservado al responsable de nómina, y el detalle de cada compañía solo lo ve esa compañía.
- ONP y AFP se reconocen por el tipo de afiliación y no por su nombre, y redondean como SUNAT (medio céntimo hacia arriba).
- Códigos SUNAT alineados con la planilla general: indemnización 0904, bonificación extraordinaria 0312 y vacaciones 0118.
- La tabla del convenio solo se descarga por https y de dominios conocidos (CAPECO, FTCCP, gob.pe); el administrador puede añadir otros en el parámetro del sistema al_hr_pe_construction.wage_table_hosts.
- Actualizar el módulo ya no restablece el BUC ni la BAE de las categorías que haya ajustado.

## 24/09/2026

- Los datos de construcción civil de la ficha del trabajador se restringen al personal de nómina, en la vista y en cada campo: sin ello, un usuario sin ese permiso recibía un error de acceso al abrir un empleado.

## 10.20260816 — 16/09/2026

- Botón Importar tabla del convenio: lee el PDF de CAPECO o de la FTCCP, lo valida contra los importes semanales publicados y crea la tabla archivada para revisión.
- Acción planificada mensual que busca convenios nuevos y crea una actividad para los responsables de planillas.
- Si la vigencia ya existe, el asistente muestra los cambios y permite actualizar la tabla; con origen Dirección web propone la dirección conocida.
- Historial en las tablas salariales, con la fuente del PDF y el aviso si el CONAFOVICER del convenio difiere del de la compañía.

## 7.20260816 — 18/08/2026

- El menú Construcción civil se ordena en Nómina ▸ Configuración ▸ Perú, entre los catálogos SUNAT y Documentos.
- La boleta del régimen adopta el nuevo diseño de la boleta legal.

## 6.20260803 — 03/08/2026

- Primera versión: maestros del convenio, estructura semanal, beneficios en planilla, CONAFOVICER y boleta del régimen.
- Pestaña Construcción civil (PE) en la empresa para editar las tasas del régimen.
