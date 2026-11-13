---
modulos: [al_user_role]
---

# Roles de usuario

En Odoo, los permisos de cada usuario se marcan grupo por grupo en su ficha.
Con muchos usuarios que hacen el mismo trabajo (cajeros, vendedores,
almaceneros), mantener esos grupos iguales a mano lleva a errores. Con el
módulo **Roles de usuario** (`al_user_role`), el administrador define un
**rol** (perfil) una sola vez y lo asigna a los usuarios: el sistema les da
los grupos del rol, con fecha de inicio y de fin y, si hace falta, solo en una
compañía. Cada alta, cambio o baja queda en un historial.

Un rol también puede ocultar menús y limitar la interfaz: campos, botones,
pestañas, filtros, informes y acciones; crear, borrar, exportar o archivar;
qué registros se ven; el modo desarrollador y el chatter.

## Configuración

1. Instale el módulo **Roles de usuario** (`al_user_role`). Solo depende de
   módulos base de Odoo.
2. Los roles los administran los usuarios con **Ajustes ‣ Usuarios ‣
   Permisos de acceso: Administración de accesos**. Los menús ocultos y los
   elementos de vista solo los ve el **Administrador del sistema**.

## Conceptos

| Término | Significado |
|---|---|
| Rol | Conjunto de grupos de seguridad con un nombre (por ejemplo, *Cajero*). El rol es en sí un grupo |
| Asignación | Un rol para un usuario, con **Desde**, **Hasta** y **Compañía** opcionales |
| Habilitado | La asignación está dentro de sus fechas |
| Agrega | El rol suma sus grupos a los que el usuario ya tenía |
| Reemplaza | Los grupos del usuario pasan a ser exactamente los de sus roles (casilla **Reemplazar permisos del usuario**) |
| Grupos efectivos | Los grupos del rol más los que estos incluyen |
| Restricción | Lo que el rol oculta o bloquea en un modelo o en todo el sistema |

## Crear un rol

1. Vaya a **Ajustes ‣ Usuarios y compañías ‣ Roles de usuario ‣ Roles** y
   haga clic en **Nuevo**.
2. Escriba el nombre y, en **Grupos**, agregue los grupos que da el rol.
3. En **Usuarios**, agregue las asignaciones o use **Agregar usuarios** para
   asignar el rol a varios a la vez. Para cada uno puede indicar **Desde**,
   **Hasta** y **Compañía**.
4. Marque **Reemplazar permisos del usuario** solo si el rol debe definir todos
   los permisos del usuario. Sin marcar, el rol agrega sus grupos.
5. Marque **Por defecto en usuarios nuevos** si todo usuario nuevo debe
   recibirlo.
6. Guarde. Los usuarios reciben los grupos al momento.

La pestaña **Grupos efectivos** y los botones de permisos de acceso y reglas
de registro muestran todo lo que recibe el usuario con el rol.

!!! tip
    Para partir de lo que ya existe: en la lista de usuarios, **Acción ‣ Crear
    rol desde usuario** copia los grupos de un usuario; en la lista de grupos
    (modo desarrollador), **Acción ‣ Crear rol con estos grupos**.

## Cómo se calculan los permisos

| Roles habilitados del usuario | Sus grupos | Aviso en su ficha |
|---|---|---|
| Ninguno | Los que tenga; el módulo no lo toca | — |
| Solo roles que agregan | Su configuración propia más los grupos de sus roles | Gris: *tiene roles asignados* |
| Al menos uno que reemplaza | Solo los grupos de sus roles | Azul: *se administran por roles* |

- Al quitarse o vencer un rol que agrega, el usuario pierde solo los grupos que
  tenía por ese rol; los que tenía por su cuenta se quedan.
- Si se quita a mano un grupo que da un rol habilitado, el rol lo vuelve a dar.
- Si vence un rol que reemplaza, el usuario queda sin grupos, es decir, sin
  acceso.
- Con **Compañía**, el rol aplica solo cuando esa compañía está activa en el
  selector. Si el usuario trabaja con varias compañías a la vez, el rol aplica
  solo si lo tiene en todas ellas.
- Al último administrador del sistema nunca se le quita el grupo
  Administrador.
- Los grupos se recalculan al guardar el rol o el usuario, al iniciar sesión,
  al cambiar de compañía y cada día a las 00:05 (hora de la compañía; sin
  zona horaria, la de Lima), para los roles que empiezan o vencen ese día.

### Ejemplo

El rol *Vendedor* agrega **Ventas: Usuario** y el usuario ya tenía
**Contactos: Creación**.

| Momento | Grupos del usuario |
|---|---|
| Antes del rol | Usuario interno, Contactos: Creación |
| Rol habilitado | Usuario interno, Contactos: Creación, Ventas: Usuario |
| Rol vencido | Usuario interno, Contactos: Creación |

## Ocultar menús

En la pestaña **Menús ocultos** del rol, agregue los menús que no deben ver
sus usuarios. Ocultar un menú oculta también sus submenús.

- Un menú se oculta solo si **todos** los roles habilitados del usuario lo
  ocultan: los roles suman acceso, igual que los grupos.
- El **Administrador del sistema** ve siempre todos los menús.
- Es solo visual: quien conozca la dirección de la pantalla podría abrirla si
  sus grupos lo permiten. Para impedirlo, quite el grupo del rol.

**Ajustes ‣ Usuarios y compañías ‣ Roles de usuario ‣ Menús ocultos por rol**
lista todos los menús con los roles que los ocultan.

## Restringir la interfaz y los registros

En la pestaña **Restricciones** del rol:

- **Generales**: bloquear el modo desarrollador, ocultar el chatter, ocultar
  solo **Enviar mensaje** (queda **Registrar nota**, que es interna) y **Todo
  en solo lectura**.
- **Por modelo**, una línea por modelo:
    - solo lectura, y ocultar crear, borrar, duplicar, archivar y exportar;
    - campos ocultos, de solo lectura, obligatorios y sin enlace para abrir;
    - botones, pestañas y filtros ocultos (se leen de las vistas al elegir el
      modelo; **Elementos de vista** los lista y los vuelve a leer);
    - informes de **Imprimir** y acciones de **Acciones** ocultos;
    - un **dominio**: el usuario solo ve y modifica los registros que lo
      cumplen.

Con varios roles, una restricción aplica solo si todos los roles habilitados
del usuario la tienen. El Administrador del sistema no tiene restricciones.
Tras cambiar una restricción, el usuario debe recargar la página.

| Restricción | Alcance |
|---|---|
| Solo lectura (del modelo o de todo) | Real: tampoco se puede escribir por botones, importación o API |
| Dominio de registros | Real: se suma a las reglas de registro |
| Enviar mensaje | Real: el servidor rechaza los mensajes y acepta las notas |
| Modo desarrollador | Real: se apaga aunque se abra `?debug=1` |
| Campos ocultos | Fuera de la vista, de los filtros personalizados y de Exportar |
| Botones, pestañas, crear, borrar, exportar | Visual |

*Todo en solo lectura* deja libres los asistentes, el chatter, los adjuntos,
los filtros favoritos y las preferencias del usuario.

## Historial

**Ajustes ‣ Usuarios y compañías ‣ Roles de usuario ‣ Historial de roles**
muestra cada alta, cambio y baja de una asignación, con el valor anterior y
el nuevo, quién lo hizo y cuándo. Desde la ficha del usuario, el botón
**Historial de roles** filtra los suyos. El historial no se edita y conserva
el nombre del rol aunque el rol se borre.

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| El usuario no recibe los grupos de un rol con **Compañía** | Tiene activas otras compañías donde no tiene el rol | Asignarle el rol en esas compañías o dejar la asignación sin compañía |
| Un usuario quedó sin acceso | Venció un rol que reemplaza sus permisos | Ampliar **Hasta** o asignarle otro rol |
| Un menú oculto sigue apareciendo | Otro rol del usuario no lo oculta | Ocultarlo en todos sus roles |
| Una restricción no se nota | El usuario no recargó la página o otro rol no la tiene | Recargar; revisar los demás roles |
| Se quitó un grupo a mano y volvió | Lo da un rol habilitado | Quitarlo del rol o la asignación |

!!! info "Ver también"
    - [Usuarios y permisos en Odoo 19](https://www.odoo.com/documentation/19.0/es/applications/general/users.html)
