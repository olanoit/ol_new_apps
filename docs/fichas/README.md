# Fichas de los módulos

La ficha de cada módulo (`<módulo>/static/description/index.html`) es la página
que se ve en **Aplicaciones** y, completa, en
`/<módulo>/static/description/index.html`. **No se edita a mano**: se genera
desde un YAML con el contenido.

```
docs/fichas/<módulo>.yml            contenido de la ficha
docs/fichas/capturas/<módulo>.py    guion que toma sus capturas
docs/fichas/generar_fichas.py       YAML → index.html
docs/fichas/capturar.py             ayudante de capturas (Playwright)
docs/fichas/revisar.py              foto de la ficha generada, para revisarla
docs/fichas/diagramas.py            diagramas de flujo (Mermaid → PNG)
```

Modelo de referencia: **`al_l10n_pe_retention.yml`** y su guion de capturas.

## Flujo

```bash
PY=/home/och/odoo/ce19/.venv/bin/python
# 1. capturas (servidor de Odoo levantado en http://127.0.0.1:19730)
$PY docs/fichas/capturas/<módulo>.py
# 2. diagramas (si el YAML tiene «flujos»; necesita acceso a cdn.jsdelivr.net)
$PY docs/fichas/diagramas.py <módulo>
# 3. ficha
$PY docs/fichas/generar_fichas.py <módulo>
# 4. revisión visual: deja PNG por tramos en la carpeta indicada
$PY docs/fichas/revisar.py <módulo> /ruta/temporal
```

## Por qué así

- **Aplicaciones descarta `<style>`** pero conserva los estilos en línea (grid,
  degradados, sombras), `<img>`, tablas y `<details>`; descarta `<svg>`. El
  generador escribe todo en línea, así la ficha se ve igual en los dos sitios.
- El resultado se pasa por `docs/validacion/fichas_modulos.py`: ASCII puro
  (acentos como `&#243;`), enlace «Ver la ficha completa» y pie con versión y
  licencia del manifest.
- Dependencias, edición (Community/Enterprise, detectada de forma transitiva) y
  módulos relacionados salen de los manifests.

## Esquema del YAML

Todas las claves son opcionales salvo `titulo` y `subtitulo`. Las secciones sin
datos no se muestran.

| Clave | Contenido |
|---|---|
| `titulo` | Nombre funcional, corto (no el nombre técnico). |
| `subtitulo` | Una o dos frases: qué resuelve y para quién. |
| `categoria` | Antetítulo, p. ej. `Localización Perú · Contabilidad`. |
| `etiquetas` | Lista de 4–7 etiquetas cortas. |
| `portada` | Captura más representativa (`screenshots/…png`). |
| `ediciones` | Forzar `[community, enterprise]` o `[enterprise]` (normalmente se detecta). |
| `destacados_intro`, `destacados` | 3–6 tarjetas: `icono` (1–3 caracteres o un símbolo), `titulo`, `texto`. |
| `contexto` | `titulo`, `texto` (el problema que resuelve, norma SUNAT/legal si aplica) y `nota` (recuadro lateral). |
| `libros_titulo`, `libros_intro`, `libros`, `libros_mapa` | Guía por libro u obligación legal (módulos que cubren varios libros, p. ej. PLE): `codigo` (insignia), `titulo`, `formatos` (etiquetas), `texto` (qué es), `revisar` (lista «Antes de presentar»), `ficha` (filas `[Aspecto, Detalle]`: quién lo lleva, periodicidad, datos de Odoo, dónde se genera…) y `nota`. `libros_mapa` es una tabla resumen (primera fila = cabecera). Va justo después del contexto. |
| `flujos_intro`, `flujos` | Diagramas del proceso: `id` (nombre del PNG), `titulo`, `texto`, `mermaid` (bloque literal `flowchart TD`) y `pie`. |
| `pasos_titulo`, `pasos_intro`, `pasos` | Recorrido con capturas: `titulo`, `ruta` (menú exacto con `▸`), `texto`, `puntos` (lista), `imagen`, `pie`. Una entrada con `seccion` (y `texto` opcional) abre un grupo: una **función** del módulo. |
| `campos_intro`, `campos` | Referencia por pantalla: `grupo`, `ruta`, `texto` y `campos` (filas `[Campo, Qué hace, Por defecto, Efecto]`). |
| `asientos_intro`, `asientos` | Asientos de ejemplo: `titulo`, `referencia` (nombre real del asiento), `texto`, `lineas` (`[cuenta, descripción, debe, haber]`, importes como `"1.234,56"` o vacío) y `nota`. **Debe y haber tienen que cuadrar**: el generador rechaza el asiento si no. |
| `funcionalidades_intro`, `funcionalidades` | Lista simple, o grupos con `grupo` e `items`. |
| `ejemplos_intro`, `ejemplos` | Casos con `titulo`, `texto`, `tabla` (primera fila = cabecera), `codigo` (bloque literal) y `nota`. |
| `configuracion_intro`, `configuracion`, `requisitos_nota` | Pasos de puesta en marcha; las dependencias se añaden solas. |
| `faq` | Lista de `pregunta` / `respuesta`. |
| `novedades` | Lista de `version` (la primera puede omitirla: toma la del manifest), `fecha`, `cambios`. |
| `relacionados` | Nombres técnicos de otros módulos de la suite. |
| `pie` | Línea final bajo versión y licencia. |

Marcado en los textos: `**negrita**`, `` `código` `` y párrafos separados por
una línea en blanco. Nada más (ni cursiva ni HTML).

**Trampas de YAML:** dentro de listas `[...]` pon entre comillas toda celda con
coma, `:`, `?`, `#` o que empiece por un símbolo (`"S/ 650,00"`, `"¿Retiene?"`).
Pon también entre comillas `"No"`, `"Sí"`, `"On"`, `"Off"` y `"Yes"`: sin
ellas YAML los lee como booleanos. El generador rechaza esos valores y las
tablas cuyas filas no tengan tantas celdas como la cabecera.

**Capturas:** el navegador del ayudante usa la hora de Lima y el español. Para
un bloque suelto (p. ej. una sección de Ajustes) usa `c.foto(..., clip={...})`
con la caja del elemento (`locator.bounding_box()`).

## Criterios de contenido

- **Todo verificable en el código**: menús, campos, botones y textos tal como
  aparecen en la interfaz. Nada inventado ni prometido.
- En español, frases cortas, orientado al usuario funcional (contador, jefe de
  planillas), con la norma SUNAT/MTPE cuando la haya.
- Las rutas `ruta:` son las del menú real (preferir la app **Perú** cuando el
  menú está allí).
- Ejemplos con **cifras reales** de los datos de demostración y cálculos que
  cuadren.
- `novedades` desde `git log -- <módulo>` (fechas y cambios funcionales, no
  técnicos).
- No mencionar a terceros ni a otros proveedores.

## Nivel de detalle (contabilidad y planillas)

Modelo: `al_l10n_pe_retention.yml`. Cada ficha debe tener:

1. **Todas las funciones cubiertas.** Recorre menús, botones, asistentes,
   reportes y acciones del módulo; agrupa los pasos con `seccion` (una por
   función: configuración, flujo de clientes, de proveedores, refinanciación,
   reportes, declaración…). Lo típico: 4–7 secciones y 12–20 capturas. Si una
   función no se puede capturar, va igual como paso sin imagen.
2. **Diagramas de flujo.** Al menos uno del proceso principal y uno por cada
   proceso distinto (p. ej. compras y ventas). `flowchart TD` (vertical); textos
   cortos con `<br/>`; decisiones con `{…}` y ramas etiquetadas. Solo lo que el
   código hace.
3. **Referencia campo por campo** de cada pantalla propia del módulo
   (ajustes, formularios, asistentes, campos añadidos a modelos nativos), con
   las etiquetas exactas de la interfaz, el valor por defecto real y su efecto.
4. **Asientos contables** de cada operación que genere uno, copiados de
   asientos reales de la base (`account_move_line`), con la referencia del
   asiento. En planillas: asiento de la planilla, provisiones, CTS, etc.

## Criterios de capturas

- En el orden del recorrido, nombradas `NN-descripcion.png`
  (`01-ajustes.png`…); cantidad según el apartado anterior.
- Recortar a lo relevante: `selector='.modal-content'` para diálogos,
  `'.o_form_view .o_form_sheet_bg'` para formularios; vista completa para
  listas, informes y ajustes. El ayudante aparta el ratón y quita el fondo
  vacío sobrante.
- Datos de demostración con prefijo **DEMO**; si faltan, crearlos por
  `odoo shell` con ese prefijo y `env.cr.commit()`, de forma idempotente. Nunca
  borrar ni modificar datos existentes que no sean DEMO.
- Las capturas antiguas que ya no use la ficha se eliminan (`git rm`).
