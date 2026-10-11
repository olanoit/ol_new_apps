# Pautas de contenido

Adaptación al español de las
[pautas de contenido de Odoo](https://www.odoo.com/documentation/19.0/contributing/documentation/content_guidelines.html).

## Estructura de una página

1. **Un solo título (H1)**, corto, en mayúscula solo al inicio, sin «cómo» ni
   «guía de». Ejemplo: `# Detracciones (SPOT)`.
2. **Un párrafo de entrada** que confirma al lector que llegó a la página
   correcta: qué resuelve la funcionalidad y para quién. Sin promoción.
3. **`## Configuración`** primero: requisitos, módulos, ajustes y datos
   maestros que hay que preparar.
4. **Una sección H2 por acción o flujo principal** (registrar, validar,
   pagar, declarar…), en el orden en que se hacen. Las H3 tratan puntos
   concretos dentro de cada una.
5. **`## Reportes`**, si la funcionalidad genera reportes o archivos.
6. Al final, un aviso **Ver también** con la norma, la documentación de Odoo
   y las páginas relacionadas.

Los conceptos o la norma que hay que entender antes de usar la funcionalidad
van en la entrada o en una H2 `## Conceptos` corta, no en un capítulo aparte.
Los errores frecuentes van como aviso junto al paso donde ocurren o, si son
muchos, en una H2 `## Casos especiales` con una tabla.

## Estilo

- **Informar, no convencer.** Describa qué hace el sistema y qué hace el
  usuario.
- **Modo imperativo** en las instrucciones: «Vaya a…», «Active…», «Haga clic
  en **Guardar**». No hable de «usted» ni de «nosotros».
- **Presente**: «El sistema crea el asiento», no «creará».
- **Sin versiones**: no compare con versiones anteriores de Odoo ni de la suite.
  Cada versión del sitio documenta la suya.
- **Mayúsculas**:
    - solo al inicio de títulos y etiquetas;
    - las aplicaciones con mayúscula (la aplicación Contabilidad);
    - las etiquetas de la interfaz tal como aparecen en Odoo.
- **Consistencia**: use los mismos términos que las páginas vecinas y que la
  interfaz (comprobante, contrata, planilla…).
- **Ejemplos con cifras reales del demo** cuando ayudan a entender un
  cálculo. Que las cifras cuadren.

## Listas

- Numeradas cuando el orden importa (procedimientos); con viñetas cuando no.
- Tres elementos o menos que no son pasos: mejor en una frase.
- Punto final solo si el elemento es una oración completa.

## Imágenes

- Acompañan al texto, nunca lo reemplazan: las instrucciones se siguen sin
  verlas. Úselas con moderación, para un punto concreto o un ejemplo.
- **Capturas**:
    - recortadas a la zona útil, sin pantalla completa;
    - como mucho 933 px de ancho;
    - sin flechas ni recuadros: recorte en su lugar.
  `mkdocs/scripts/preparar_imagen.py` recorta, reduce y comprime.
- **Archivos**: en la carpeta con el nombre de la página, en minúsculas y
  con guiones (`detractions/invoice-detraction.png`).
- **Texto alternativo** obligatorio: una línea que describe la acción que se
  ve, sin repetir el texto de al lado.

## Enlaces

- Entre páginas, con rutas relativas a archivos `.md`.
- A la norma (SUNAT, SBS, BCRP, MEF) y a la documentación de Odoo, con
  enlaces verificados por `docs/validacion/verificar_enlaces.py`.
- A detalles técnicos de un módulo, a su página en **Desarrollador ▸ Referencia
  de módulos** (`developer/reference/modules/<módulo>/index.md`).
