# al_project_gantt_website — Gantt de Proyectos (página del sitio web)

Publica el mismo diagrama en `/gantt`, dentro del sitio web, para consultarlo
fuera del backend (pantallas de obra, enlaces internos, tableros).

**No es una página pública ni de portal.** Solo entran usuarios internos con el
grupo del Gantt.

## Instalación

```bash
odoo-bin -c <config> -i al_project_gantt_website --stop-after-init
```

Arrastra `al_project_gantt_base` y **`website`** (que a su vez instala `portal`
y `http_routing`). Si solo quieres la interfaz de backend, no instales este
módulo: las dos son independientes y pueden convivir.

Tras instalar, el menú **Gantt** aparece en la barra del sitio (es un registro
`website.menu` editable desde el editor; una actualización del módulo no lo
rehace).

## Control de acceso

| Quién | `/gantt` | `/gantt/data`, `/gantt/apply`, `/gantt/baseline` |
|---|---|---|
| Visitante no autenticado | Redirección a `/web/login?redirect=/gantt` (efecto de `auth='user'`) | Igual |
| Usuario de portal o compartido | **403 Forbidden** | Rechazado (ver nota) |
| Interno sin el grupo del Gantt | **403 Forbidden** | Rechazado (ver nota) |
| Interno con el grupo | Página | Datos |

El controlador comprueba `user._is_public()`, `user.share` y el grupo antes de
tocar el ORM. Es **redundante a propósito** con
`al.gantt.data._check_gantt_access`: la capa de datos protege el modelo se llame
desde donde se llame, y el controlador protege la ruta.

> **Nota sobre el 403 en `/gantt/data`.** La ruta es `type='jsonrpc'` y ese
> protocolo transporta los errores en el cuerpo de la respuesta con HTTP 200
> (`{"error": {...}}`, sin `result`), no en el código de estado. Es el
> comportamiento estándar de Odoo y lo que espera el cliente `rpc()`; forzar un
> 403 real rompería el manejo de errores del frontend. Lo que sí está
> garantizado —y probado— es que un usuario no autorizado **no recibe ningún
> dato**. En Odoo 19, `type='json'` es un alias obsoleto de `type='jsonrpc'`.

## Cómo está construido

- **Plantilla** `gantt_page`: hereda `website.layout` y solo aporta el
  esqueleto (barra, avisos, contenedor). Los datos no se renderizan en el
  servidor.
- **Interacción** `al_project_gantt_website.gantt_page`: usa el framework de
  *public interactions* de Odoo 19 (`@web/public/interaction`), no OWL ni
  `publicWidget`. Carga la librería con `loadJS`/`loadCSS`, pide los datos a
  `/gantt/data` y monta el diagrama.
- **Código compartido**: adaptador de datos, configuración de la librería y
  estilos de barras vienen del módulo base; aquí solo está la maquetación de la
  página y el armado de la barra de herramientas.
- Los nombres de proyecto y tarea se insertan con `textContent`, nunca con
  `innerHTML`.

## Edición

La página es **editable con las mismas reglas que el backend**: arrastre,
redimensionado, avance, alta y baja de tareas y dependencias, ruta crítica,
línea base y reprogramación en cadena. La escritura entra por `/gantt/apply`,
que delega en `project.project.apply_gantt_changes()`; el permiso se comprueba
tarea por tarea contra la ACL y las `ir.rule` de `project`, así que un usuario
que solo puede leer ve el diagrama en modo consulta.

## Herramientas de vista

Las mismas que en el backend: búsqueda instantánea, código EDT,
expandir/contraer, ocultar terminadas, pantalla completa, marca de hoy,
sombreado de no laborables y menú contextual (con «Abrir en Odoo» en una
pestaña nueva, en lugar de la acción del webclient).

## Exportación

Los mismos botones que en el backend: el Excel se descarga de
`/al_project_gantt/export/xlsx` y el PDF se abre por la ruta estándar de
informes de Odoo. Ambos se generan en el servidor.

## Filtros

Los mismos que en el backend —responsable, estado, rango de fechas e «incluir
tareas sin fecha»— en un panel plegable. El estado de los filtros y su
traducción a las `options` del contrato salen de `gantt_filters.js`, en el
módulo base: las dos interfaces comparten reglas y validaciones.

## Diferencias con la interfaz de backend

| | Backend | Website |
|---|---|---|
| Framework | Componente OWL (`ir.actions.client`) | Interaction del frontend |
| Alto del diagrama | Ocupa el área de contenido | `70vh` (mínimo 420 px) |
| Notificaciones | Servicio `notification` de Odoo | Sin notificaciones (la selección vacía simplemente se ignora) |
| Entrada de datos | `orm.call` | Endpoints `/gantt/data` y `/gantt/apply` |
| Aviso de guardado | Notificación de Odoo | Texto en la barra de herramientas |

## Pruebas

```bash
odoo-bin -c <config> -u al_project_gantt_website --test-enable \
         --test-tags /al_project_gantt_website --stop-after-init
```

8 tests `HttpCase`: página y endpoint para interno con grupo, interno sin grupo,
portal y visitante anónimo, forma del contrato y ausencia de la librería en el
bundle del frontend.

## Limitaciones

Las del módulo base (dependencias solo `FS`, sin calendarios laborales) y:

- La página no es editable con el editor de website (el bloque del diagrama es
  un `oe_structure` alrededor, pero el Gantt en sí lo monta el JS).
