# Instrucciones para trabajar en este repositorio

## Planificador de obra

Módulos: `OL-PROJECTS/al_construction_planner*`, `al_construction_material_request`,
`al_construction_attendance`, `al_construction_portal`, `OL-INDUSTRIES/al_industry_*`.

El planificador sirve a más de una vertical (hoy mobiliario y construcción por
partidas) con un mismo núcleo. Antes de tocar cualquiera de estos módulos:

1. Lee [`docs/planificador/ARQUITECTURA_COMUN.md`](docs/planificador/ARQUITECTURA_COMUN.md).
   Manda sobre los demás documentos de `docs/planificador/` en lo común. La
   especificación v1.4 y el diseño técnico son historia: no describen las
   dependencias, los grupos ni la ubicación actual de los modelos.
2. Ubica el cambio con la sección 4 de ese documento: núcleo, puente de
   operación o módulo de vertical. No agregues al núcleo nada que solo sirva a
   una vertical.
3. No escribas condiciones del tipo «si la vertical es X». La vertical se
   expresa con el perfil, los catálogos, los puentes instalados y los
   parámetros de la compañía.
4. No pongas códigos de etapa, de tipo de recurso ni de nivel en el código.
   Pregunta por el comportamiento del catálogo.

### Configuración antes que desarrollo

Antes de programar un requerimiento, comprueba que no se cumpla ya con:

1. Odoo nativo instalado en la base del cliente;
2. un módulo de `OL-THIRD-PARTY/` (OCA);
3. algo ya desarrollado en los módulos AL: catálogos, perfiles, parámetros de
   la compañía, interruptores de Ajustes;
4. una combinación de los anteriores.

Si encuentras esa ruta, no programes: devuelve el requerimiento y explica cuál
es la ruta y dónde la comprobaste. Si el requerimiento no trae su sección
«Alternativas descartadas», pídela antes de empezar.

### Convivencia con la suite

- Toda sobrescritura de un método nativo o de terceros llama a `super()`. Si
  interceptas con un asistente, el asistente vuelve a llamar al método con un
  contexto que evita repetir el control.
- Un reemplazo sin `super()` se anota en `ARQUITECTURA_COMUN.md`, sección 7,
  con su alcance.
- El código que corre en cada movimiento de stock, transferencia o apunte
  analítico filtra primero lo que es de obra. Ventas, farmacia y punto de venta
  comparten la base.
- Los cambios en aprobaciones se prueban con los dos motores
  (`construction_approval_engine`).

### Al terminar un cambio

- Si cambia algo común, actualiza `ARQUITECTURA_COMUN.md` en el mismo commit:
  decisión nueva en la sección 8, conflicto resuelto en la sección 9.
- No dejes datos de clientes en el repositorio (nombres, cifras, obras,
  usuarios). Es público.
