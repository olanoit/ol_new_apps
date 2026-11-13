# Roles de usuario (AL)

Documentación funcional: [Roles de usuario](../../mkdocs/content/applications/general/user_roles.md)

Módulo `al_user_role` para Odoo 19.

Administra los permisos de los usuarios por **roles** (perfiles). Un rol agrupa
grupos de seguridad y cada usuario recibe los grupos de sus roles habilitados.

Se basa en los módulos OCA `base_user_role`, `base_user_role_company` y
`base_user_role_history`, y en `hide_menu_user` (Cybrosys) para los menús
ocultos, pero no depende de ellos: solo usa `base`, `web` y `mail`.
Por ese origen su licencia es LGPL-3 (excepción declarada en `scripts/areas.py`).
Sus modelos tienen nombres propios (`al.user.role*`), así que puede instalarse
junto a los de OCA.

## Dónde

| Menú / pantalla | Qué hay |
|---|---|
| Ajustes → Usuarios y compañías → Roles de usuario → **Roles** | Lista y ficha de los roles |
| Ajustes → Usuarios y compañías → Roles de usuario → **Historial de roles** | Altas, cambios y bajas de roles (solo lectura) |
| Usuario → pestaña **Roles** | Roles del usuario con vigencia y compañía |
| Usuario → botón **Roles** | Abre la ficha del rol si tiene uno, o la lista si tiene varios (oculto si no tiene roles) |
| Usuario → botón **Historial de roles** | Historial del usuario y fecha del último cambio |
| Usuario → Acción → **Crear rol desde usuario** | Rol con los grupos actuales del usuario |
| Grupos (modo desarrollador) → Acción → **Crear rol con estos grupos** | Rol con los grupos seleccionados |
| Grupo → botón **Roles** | Roles que otorgan el grupo, directa o transitivamente |
| Ajustes → Usuarios y compañías → Roles de usuario → **Menús ocultos por rol** | Todos los menús y los roles que los ocultan (solo Administrador del sistema) |
| Ajustes → Usuarios y compañías → Roles de usuario → **Elementos de vista** | Botones, pestañas y filtros registrados para las restricciones, con su etiqueta y nombre técnico; botón *Releer vistas* (solo Administrador del sistema) |
| Menú (modo desarrollador) → pestaña **Roles que lo ocultan** | Lo mismo desde la ficha del menú |

Solo los **Administradores de permisos** (`base.group_erp_manager`) ven y editan
los roles y el historial.

## Ficha del rol

- **Grupos**: lista completa (Privilegio, Grupo, Descripción) de los grupos que
  otorga directamente el rol (`implied_ids`). El rol es en sí un grupo
  (`_inherits res.groups`).
- **Usuarios**: asignaciones con **Desde / Hasta** y **Compañía** opcionales.
  Botón **Agregar usuarios** para asignar varios a la vez.
- **Menús ocultos**: menús que no ven los usuarios con el rol (ver abajo).
- **Grupos efectivos** (solo lectura): todo lo que recibe el usuario, es decir,
  los de *Grupos* más los que estos incluyen (p. ej. *Punto de venta /
  Administrador* trae *Inventario / Usuario*).
- Botones con los **permisos de acceso** y las **reglas de registro** que trae el rol.
- **Reemplazar permisos del usuario**: si se marca, el rol reemplaza la
  configuración propia del usuario; si no, solo agrega sus grupos (ver abajo).
- **Por defecto en usuarios nuevos**: se asigna al crear cada usuario.

## Cómo se calculan los grupos

- Cada rol tiene el check **Reemplazar permisos del usuario** (por defecto
  **desmarcado**):

  | Modo | Grupos del usuario | Aviso en la ficha |
  |---|---|---|
  | **Agrega** (sin marcar) | Su configuración propia **+** los grupos de sus roles habilitados | Gris: "tiene roles asignados" |
  | **Reemplaza** (marcado) | Exactamente la unión de los grupos de sus roles habilitados | Azul: "se administran por roles" |

- Si **algún** rol habilitado del usuario reemplaza, manda el reemplazo y se
  pierde la configuración propia.
- En modo Agrega, el usuario guarda en *Grupos otorgados por roles*
  (`al_role_granted_group_ids`) los grupos que tiene **solo** por sus roles. Al
  quitarse o vencer el rol se quitan solo esos grupos. Un grupo que el usuario
  ya tenía por su cuenta sigue siendo propio aunque también lo dé un rol.
- Los cambios a mano en Permisos de acceso se respetan para la configuración
  propia. Si se quita un grupo que da un rol habilitado, el rol lo vuelve a dar.
- Un usuario **sin roles** conserva sus grupos: el módulo solo administra a
  quien tiene roles. Al quitarle su último rol se quedan solo los grupos que
  no se pueden quitar.
- Se recalcula al cambiar un rol, una asignación, los grupos, las compañías o
  el estado del usuario, al iniciar sesión, al cargar el cliente web y una vez al
  día a las **00:05** (cron *Roles de usuario: actualizar grupos por vigencia*),
  para las asignaciones que empiezan o vencen. El cron usa la zona horaria de la
  compañía (si no tiene, `America/Lima`) tanto para la hora de ejecución como
  para decidir qué día es "hoy".
- **Habilitado**: hoy está entre Desde y Hasta (vacíos = sin límite).
- Un usuario cuyo rol **Reemplaza** venció queda **sin grupos**, ni siquiera
  Usuario interno: rol exclusivo vencido = sin acceso (igual que OCA). Si el rol
  vencido era **Agrega**, conserva su configuración propia. Un rol que aún no
  empieza no cambia nada hasta su fecha Desde.
- **Compañía**: vacía, aplica siempre. Con compañía, aplica si esa compañía está
  activa en el selector y el usuario tiene el mismo rol en **todas** las
  compañías activas. El mismo rol puede asignarse una vez por compañía.
- Nunca se quita el grupo **Administrador** al último administrador.
- Los grupos que elige el propio usuario (multicompañía, notificaciones en
  Odoo) no los quitan ni los dan los roles.

## Menús ocultos

- Un menú se oculta a un usuario solo si **todos** sus roles habilitados lo
  ocultan: los roles suman acceso, igual que los grupos. Un usuario sin roles
  ve todos los menús que le permiten sus grupos.
- Ocultar un menú oculta también sus submenús. Si un rol oculta *Ventas* y otro
  solo *Ventas → Pedidos*, se oculta solo *Pedidos*.
- El **Administrador del sistema** ve siempre todos los menús.
- Es **solo visual**: no cambia los permisos sobre los modelos. Quien conozca la
  URL de una acción puede abrirla si sus grupos lo permiten. Para restringir de
  verdad, quite el grupo del rol.
- Los menús visibles se guardan en caché por grupos del usuario; la caché se
  limpia al cambiar los menús ocultos de un rol o los grupos de un usuario.

## Restricciones

Pestaña **Restricciones** del rol (basada en `access_roles` de Cybrosys):

- **Generales**: bloquear el modo desarrollador (en el servidor, aunque se abra
  `?debug=1`, incluida la página `/odoo`; el usuario ve un aviso y Ctrl+K no
  ofrece activarlo), ocultar el chatter, ocultar solo **Enviar mensaje** del
  chatter (queda Registrar nota, que es interna; también se rechaza en el
  servidor) y **todo en solo lectura** (real; ver abajo).
- **Por modelo** (una línea por modelo):
  - acciones: **solo lectura** (real; ver abajo) y ocultar crear (también en
    los campos que apuntan al modelo), borrar, duplicar, archivar y exportar;
  - campos ocultos (también fuera del filtro y la agrupación personalizados y
    de Exportar), de solo lectura, obligatorios y sin enlace para abrir;
  - botones, pestañas y filtros ocultos. Se leen de las vistas del modelo al
    elegirlo, y se identifican por su nombre técnico, no por la etiqueta, que
    se traduce;
  - informes (Imprimir) y acciones de servidor (Acciones) ocultos;
  - los selectores muestran solo el nombre (p. ej. *Envíe un correo*); campos,
    botones, pestañas y filtros también se buscan por su nombre técnico;
  - **dominio de registros**: el usuario solo ve y modifica los registros que
    lo cumplen. Se suma (AND) a sus reglas de registro.
- Con varios roles, una restricción aplica solo si **todos** los roles vigentes
  del usuario la tienen; los dominios de los roles se unen con OR. El
  **Administrador del sistema** no tiene restricciones.
- **Reales** (se aplican en el servidor, también por botones, importación o API):
  - la **solo lectura** (del modelo o *Todo en solo lectura*): `ir.rule` no da
    ningún registro para crear, modificar o borrar, con el mensaje *"Su rol
    solo permite consultar…"*. Tampoco se pueden registrar notas en esos
    registros (el chatter pide permiso de escritura, como en Odoo). *Todo en
    solo lectura* deja libres los asistentes y lo propio del usuario: chatter,
    adjuntos, filtros favoritos, preferencias y sesión;
  - el **dominio de registros**;
  - **Enviar mensaje**: `/mail/message/post` rechaza los mensajes
    (`mail.mt_comment`) y acepta las notas. No afecta a Conversaciones ni a
    los correos de los asistentes (p. ej. *Enviar por correo* de un pedido).
- Los **campos ocultos** salen además de `fields_get` como no buscables, no
  agrupables y no exportables. Quien pida el campo por su nombre a la API aún
  puede leerlo: para eso, `groups=` en el campo.
- Lo demás es **visual**: ocultar Crear o un botón no impide hacerlo por RPC.
- Casi todo se aplica en el servidor: arch de las vistas
  (`_postprocess_access_rights`, por usuario y fuera de la caché de vistas),
  `get_bindings`, `ir.rule._compute_domain` y `fields_get`. Exportar, Archivar
  y Enviar mensaje usan además un parche JS, con los datos de `session_info`; tras cambiar una restricción, el
  usuario debe recargar la página.

## Historial

Cada alta, cambio (rol, fechas, compañía) y baja de una asignación guarda el
valor anterior y el nuevo, quién lo hizo y cuándo. Guarda el nombre del rol,
para que se lea aunque el rol se borre después.

## Diferencias con OCA

| Tema | OCA | Este módulo |
|---|---|---|
| Dependencias | 3 módulos (+ `mail` el historial) | Solo `base`, `web` y `mail` |
| Al borrar un rol | El grupo queda huérfano | Se borra el grupo y la baja queda en el historial |
| Historial al borrar el rol | Se borra con el rol | Se conserva, con el nombre del rol |
| Mismo rol sin compañía | `UNIQUE` con `NULL` permite duplicados | Índice único con `COALESCE(company_id, 0)` |
| Reaplicar roles | En cualquier `write` del usuario | Solo si cambian roles, grupos, compañías o estado |
| Asignar desde el wizard | No reaplica grupos hasta el cron | Reaplica al crear la asignación |
| Caché de menús | Quita `Cache-Control` en `load_menus` | No hace falta: Odoo 19 ya responde `no-store` |
| Grupos efectivos | — | Pestaña en el rol y botón Roles en el grupo |
| Menús ocultos (`hide_menu_user`) | Por usuario o por grupo; basta un grupo para ocultar | Por rol; se oculta si todos los roles lo ocultan, con sus submenús |
| Restricciones (`access_roles`) | Un rol por usuario; botones y pestañas por etiqueta, escaneando todas las vistas en cada arranque; 6 parches JS con una llamada RPC por vista | Varios roles con vigencia; nombre técnico; elementos leídos al elegir el modelo; en el servidor salvo Exportar / Archivar |

## Tests

```bash
cd /home/och/odoo/ce19
.venv/bin/python odoo-bin -c cfg/my/pe.cfg -d test_pe_al_user_role -i al_user_role \
  --test-enable --test-tags /al_user_role --stop-after-init --workers=0 \
  --http-port=18069 --gevent-port=18072
```
