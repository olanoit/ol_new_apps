---
modulos: [al_report_preview, al_l10n_pe_report_preview]
---

# Reportes PDF en el navegador

Odoo descarga cada reporte PDF. Con el módulo **Reportes PDF en el
navegador** (`al_report_preview`), el reporte se abre en una pestaña nueva,
con el visor del navegador, y desde ahí se imprime o se guarda. Se puede
aplicar a todos los reportes o solo a los que se elijan; por ejemplo, solo a
las facturas.

## Configuración

1. Instale el módulo **Reportes PDF en el navegador** (`al_report_preview`).
   Solo depende de módulos base de Odoo.
2. Vaya a **Ajustes ‣ Ajustes generales ‣ Reportes PDF**.
3. En **Abrir los reportes en el navegador**, elija el alcance:

    | Opción | Qué hace |
    |---|---|
    | **Todos los reportes** | Cada reporte PDF se abre en una pestaña, salvo los reportes marcados como **Descargar**. Es el valor al instalar |
    | **Solo los reportes elegidos** | Los reportes se descargan, como en Odoo estándar, salvo los reportes marcados como **Abrir en el navegador** |

4. Haga clic en **Guardar**.

Con la aplicación **Perú** instalada, el mismo ajuste está también en
**Ajustes ‣ Perú ‣ Reportes PDF** (módulo `al_l10n_pe_report_preview`, que se
instala solo). Es un único ajuste: cambiarlo en un lugar lo cambia en el otro.

## Elegir por reporte

1. En **Ajustes ‣ Ajustes generales ‣ Reportes PDF**, haga clic en **Elegir
   por reporte**. Se abre la lista de reportes PDF.
2. En la columna **Al imprimir** de cada reporte, elija:

    | Opción | Qué hace |
    |---|---|
    | **Según el ajuste general** | Sigue el alcance elegido en Ajustes |
    | **Abrir en el navegador** | Este reporte siempre se abre en una pestaña |
    | **Descargar** | Este reporte siempre se descarga |

3. La columna **Se abre en el navegador** muestra el resultado para cada
   reporte.

La misma opción está en la ficha del reporte, en **Ajustes ‣ Técnico ‣
Informes** (con el modo desarrollador).

!!! example "Ejemplo: solo las facturas"
    Elija **Solo los reportes elegidos** en Ajustes. En **Elegir por
    reporte**, busque el reporte de la factura y ponga **Abrir en el
    navegador**. Las facturas se abren en una pestaña; los demás reportes se
    descargan.

## Imprimir un documento

1. Abra el documento y haga clic en **Imprimir**, o vaya a **⚙ ‣ Imprimir** y
   elija el reporte.
2. El PDF se abre en una pestaña nueva. Use los botones del visor del
   navegador para imprimirlo o guardarlo; el archivo lleva el mismo nombre
   que tendría la descarga.

!!! note "Nota"
    Si el navegador bloquea las ventanas emergentes del sitio, el reporte se
    descarga y Odoo lo avisa. Permita las ventanas emergentes de la dirección
    de Odoo para que se abra en una pestaña.

!!! warning "Importante"
    No instale este módulo junto con `prt_report_attachment_preview`: ese
    módulo abre todos los PDF en el navegador y no sigue esta configuración.
