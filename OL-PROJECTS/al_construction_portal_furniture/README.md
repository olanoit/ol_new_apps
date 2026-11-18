# Portal de obra: funciones de campo de mobiliario (AL)

Documentación funcional: [Aplicación de obra en el celular](../../mkdocs/content/applications/services/project/construction/planning/field_app.md)

Puente de `al_construction_portal` con `al_construction_planner_furniture` y
`al_construction_planner_mrp_request` (paquete 1.22, etapa 2, M122-05 a
M122-09). Se instala solo con los tres.

- Cinco funciones del perfil de vertical (`portal_module_reception`,
  `portal_replacement`, `portal_measure`, `portal_stage_progress`,
  `portal_contractor_units`), sumadas a `_portal_feature_fields` del portal.
  Nacen apagadas y la instalación las enciende en el perfil Mobiliario.
- `sync` agrega `furniture`: sub etapas de instalación de la obra,
  departamentos con sus ambientes (etapa actual), módulos y reposiciones
  abiertas, motivos y, para la contrata, lo liquidado y «Esta semana».
- Servicios de `construction.portal.service` (rutas bajo
  `/construction/api/v1/furniture/`): `module_reception`, `replacement`,
  `measure` y `stage_progress`. Cada uno comprueba la persona, su papel y la
  función de la obra; un envío repetido no duplica.
- La recepción de módulos valida con `reception` del portal (hasta lo enviado,
  entrega parcial); la medición usa el asistente del escritorio; el avance por
  sub etapa crea un avance por línea con las reglas del modelo.
- Pantallas en `static/app/furniture.js`, registradas en `window.ObraPortal`.

No pregunta por la vertical ni por códigos de etapa o de nivel: usa la
función del nivel y el tipo de la etapa en el catálogo.
