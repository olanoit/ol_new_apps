---
modulos: [al_docs_help]
---

# Ayuda contextual

Cada pantalla de la suite tiene su explicación en esta documentación, pero el
usuario tenía que saber dónde buscarla. Con el módulo **Ayuda contextual de la
suite**, las pantallas y los asistentes de la suite muestran un botón **?** que
abre, en una pestaña nueva, la página de la funcionalidad de esa pantalla, en
la sección que corresponde. Lo usan todos los usuarios internos; los
administradores revisan y completan la lista de pantallas.

El módulo no escribe la documentación ni la publica, y no cambia la ayuda
propia de Odoo.

## Configuración

1. Instale el módulo **Ayuda contextual de la suite** (`al_docs_help`). No
   necesita nada más.
2. El botón abre el sitio de la dirección configurada en **Ajustes ‣ Perú ‣
   Documentación** (con el módulo de configuración contable básica de la
   localización peruana) o, sin ella, `https://docs.altalatam.com/latest/`.
   Vea [Configuración contable básica](../finance/fiscal_localizations/peru/accounting_base.md).

## Conceptos

| Término | Significado |
|---|---|
| Ayuda contextual | Enlace desde una pantalla a la explicación de esa pantalla |
| Pantalla | Una vista de un modelo (por ejemplo, `account.move`), un asistente o una pantalla propia (acción de cliente, como el inicio del planificador) |
| Página de la funcionalidad | Página de esta documentación que declara en su encabezado los módulos que documenta |
| Sección | Encabezado de la página al que salta el enlace (su ancla) |

## Abrir la ayuda de una pantalla

1. En una pantalla con ayuda, haga clic en el botón **?** de la barra superior.
   En un asistente, el botón está en la cabecera, junto a la **X** de cerrar.
2. Al pasar el ratón, el botón dice a qué sección lleva.
3. La página se abre en una pestaña nueva. Si el sitio publicado pide acceso,
   inicie sesión con su usuario de la documentación.

El botón solo aparece si el módulo dueño de la página está instalado: si se
desinstala el módulo, sus pantallas dejan de mostrarlo. Se ve solo en el
backend, no en el TPV ni en el portal.

### Qué abre cada pantalla

La lista de pantallas se genera desde el código y la documentación:

- cada modelo o asistente que define un módulo, y cada pantalla propia (acción
  de cliente), lleva a la página que declara ese módulo, en el encabezado que
  más se parece a su descripción o en la primera sección que lo cita; si no
  hay ninguno, al inicio de la página;
- las pantallas oficiales de Odoo que la suite amplía (facturas, pagos,
  contactos, empleados, contratos, boletas de pago, asistencias, tipos de
  cambio, transferencias) se asignan a mano a su página.

### Ejemplo

Con el planificador de obra instalado:

| Dónde | Qué abre el botón ? |
|---|---|
| Planificación de obra ‣ Inicio | Planificación de obra, sección del cronograma valorizado y el inicio |
| Configuración ‣ Importar maestro y ETO (asistente) | Planificación de obra, sección de la importación del maestro y el ETO |
| Un plan de recursos | Planificación de obra |
| Contabilidad ‣ Facturas | Configuración contable básica de la localización peruana |
| Ajustes ‣ Técnico ‣ Ayuda contextual | Esta página |

## Revisar y completar la lista

Vaya a **Ajustes ‣ Técnico ‣ Ayuda contextual** (modo desarrollador,
administradores). La lista se filtra por módulo, por tipo y por **Con
sección**, y cada fila abre su página.

Para una pantalla sin ayuda, o para llevarla a otra sección, agregue o edite
la fila: el modelo o el tag, el módulo y la ruta del sitio con su ancla. Las
filas creadas a mano no se pisan al actualizar; las generadas, sí. Para
cambiar una generada de forma estable, pida el cambio en la documentación del
proyecto (vea [Organización de la documentación](../../contributing/documentation/organization.md)).

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| No aparece el botón ? | La pantalla no está en la lista o el módulo de su página no está instalado | Agregar la fila o instalar el módulo |
| El enlace pide usuario y contraseña | El sitio publicado tiene acceso con sesión | Pedir acceso al equipo de ALTA Latam |
| La página abre al inicio y no en la sección | La página no tiene una sección propia para esa pantalla | Completar la página o fijar la sección en la lista |
| Se cambió la URL del sitio | El botón usa la nueva al recargar el navegador | Recargar la página |

!!! info "Ver también"
    - [Documentación de usuario de Odoo 19](https://www.odoo.com/documentation/19.0/applications.html)
    - [Organización de la documentación](../../contributing/documentation/organization.md)
