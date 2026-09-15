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
```

Modelo de referencia: **`al_l10n_pe_retention.yml`** y su guion de capturas.

## Flujo

```bash
PY=/home/och/odoo/ce19/.venv/bin/python
# 1. capturas (servidor de Odoo levantado en http://127.0.0.1:19730)
$PY docs/fichas/capturas/<módulo>.py
# 2. ficha
$PY docs/fichas/generar_fichas.py <módulo>
# 3. revisión visual: deja PNG por tramos en la carpeta indicada
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
| `pasos_titulo`, `pasos_intro`, `pasos` | Recorrido con capturas: `titulo`, `ruta` (menú exacto con `▸`), `texto`, `puntos` (lista), `imagen`, `pie`. |
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

## Criterios de capturas

- 5–8 capturas por módulo, en el orden del recorrido, nombradas
  `NN-descripcion.png` (`01-ajustes.png`…).
- Recortar a lo relevante: `selector='.modal-content'` para diálogos,
  `'.o_form_view .o_form_sheet_bg'` para formularios; vista completa para
  listas, informes y ajustes. El ayudante aparta el ratón y quita el fondo
  vacío sobrante.
- Datos de demostración con prefijo **DEMO**; si faltan, crearlos por
  `odoo shell` con ese prefijo y `env.cr.commit()`, de forma idempotente. Nunca
  borrar ni modificar datos existentes que no sean DEMO.
- Las capturas antiguas que ya no use la ficha se eliminan (`git rm`).
