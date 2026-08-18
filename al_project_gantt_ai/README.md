# al_project_gantt_ai — Asistente de IA para el Gantt

Panel de chat opcional dentro del diagrama de Gantt del backend. Permite
**preguntar** sobre el cronograma que se está viendo y recibir **propuestas de
cambio** que el usuario revisa y aplica.

Cuarto módulo de la suite; los otros tres siguen funcionando igual sin él.

```
al_project_gantt_base      capa de datos y escritura (contrato neutral)
al_project_gantt_backend   interfaz OWL en el backend
al_project_gantt_website   interfaz en el website
al_project_gantt_ai        ← este módulo: chat + propuestas
```

## Las tres reglas del diseño

**1. La IA no escribe en Odoo.** El modelo solo devuelve propuestas. El usuario
marca las que quiere y pulsa *Aplicar*; a partir de ahí el camino es el mismo
que arrastrar una barra: `project.project.apply_gantt_changes()`, que comprueba
los permisos de cada tarea. Una propuesta sobre algo que el usuario no puede
tocar se rechaza igual que se rechazaría el arrastre.

**2. Solo se envía lo que se ve, resumido.** El cliente manda los ids de las
tareas cargadas; el servidor las **relee con el usuario real** (sin `sudo`) y
arma un resumen. Un id inventado en la petición no sirve de nada: las reglas de
registro de `project` lo dejan fuera.

Se envía, por tarea:

| Se envía | No se envía |
| --- | --- |
| nombre, proyecto | descripción |
| fechas de inicio y fin | mensajes y chatter |
| estado y avance | adjuntos |
| dependencias visibles | cliente / partner |
| personas asignadas *(opcional)* | etiquetas, horas, importes |

**3. Lo que devuelve el modelo es entrada no confiable.** Todo pasa por
`_normalize_proposal`: ids fuera del contexto, tareas sin permiso de escritura,
fechas mal formadas, inicios posteriores al fin, avances fuera de 0-100 y
personas inexistentes se descartan con un aviso visible en el panel.

## Configuración

**Gantt ▸ Configuración ▸ Ajustes** (o *Ajustes ▸ Gantt IA*). Sin clave de API el
botón del asistente **no aparece**: el módulo instalado pero sin configurar no
cambia nada del diagrama.

| Ajuste | Por defecto | Para qué |
| --- | --- | --- |
| Proveedor | Anthropic (Claude) | Anthropic, OpenAI o DeepSeek |
| Clave de API | — | Parámetro del sistema; nunca llega al navegador |
| Modelo | según proveedor | Id exacto; debe admitir *function calling* |
| URL base | — | Solo para pasarelas compatibles |
| Esfuerzo de razonamiento | Medio | Solo lo aplica Anthropic; los demás lo ignoran |
| Tokens máximos | 8000 | Techo de la respuesta, razonamiento incluido |
| Tiempo de espera | 90 s | |
| Tareas por consulta | 200 | Más contexto = más coste por pregunta |
| Enviar personas asignadas | Sí | Necesario para proponer reasignaciones |

Los valores viven en `ir.config_parameter` con el prefijo `al_gantt_ai.`.

### Proveedores

El desplegable de proveedor cambia los enlaces que aparecen bajo la clave y el
modelo: la primera pregunta de quien configura esto es *¿dónde saco la clave?*,
y tenerla a un clic ahorra la búsqueda.

| Proveedor | Modelo por defecto | Crear la clave |
| --- | --- | --- |
| Anthropic (Claude) | `claude-opus-5` | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| OpenAI | `gpt-5` | [platform.openai.com](https://platform.openai.com/api-keys) |
| DeepSeek | `deepseek-chat` | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |

**El modelo debe admitir *function calling***: es como llegan las propuestas
estructuradas. Por eso el defecto de DeepSeek es `deepseek-chat` y no
`deepseek-reasoner`, cuyo soporte no ha sido estable.

DeepSeek habla el mismo dialecto que OpenAI (*Chat Completions*), así que
comparten código; lo único que cambia está declarado en dos constantes —la URL
base y el nombre del campo que limita la respuesta, porque OpenAI renombró
`max_tokens` a `max_completion_tokens` y DeepSeek conservó el original—.
Añadir un cuarto proveedor compatible es añadir dos entradas y un enlace.

## Por qué HTTP directo y no los SDK oficiales

Un addon se despliega copiando una carpeta. Depender de `anthropic`, `openai` o
del SDK de turno obligaría a tocar el entorno del servidor en cada instalación y
a mantener esas versiones al día. `requests` ya viene con Odoo y las APIs son
REST estables, así que el módulo funciona sin instalar nada. El precio es que
`services/ai_provider.py` escribe a mano las cabeceras y el formato de cada
proveedor — y ese es todo el código específico de proveedor que hay.

## Cómo pide las propuestas

Se usa **tool use / function calling**: el modelo recibe una herramienta
`propose_changes` con un esquema JSON, y llama a esa herramienta cuando quiere
sugerir algo. Así los cambios llegan estructurados en vez de dentro de un texto
que habría que interpretar. El esquema es el mismo para todos los proveedores;
cambia solo cómo se declara (`input_schema` en Anthropic, `function.parameters`
en OpenAI y DeepSeek).

No se usa `strict`: cada API lo compila con reglas distintas y la garantía
real la da la validación del servidor, que hay que hacer igualmente.

## Estructura

```
models/gantt_ai.py            al.gantt.ai — contexto, prompt, validación
models/res_config_settings.py ajustes (ir.config_parameter)
views/gantt_ai_menus.xml      Gantt ▸ Configuración ▸ Ajustes
services/ai_provider.py       transporte HTTP a Anthropic / OpenAI / DeepSeek
static/src/js/gantt_ai_panel.js        componente OWL del chat
static/src/js/gantt_action_ai_patch.js engancha el panel al Gantt del backend
static/src/xml/gantt_action_ai.xml     herencia `t-inherit` de la plantilla
```

El enganche se hace por parche y herencia de plantilla, no tocando
`al_project_gantt_backend`: desinstalar este módulo deja el diagrama exactamente
como estaba.

## Manejo de errores

Los fallos del proveedor se traducen a mensajes accionables y se muestran
**dentro de la conversación**, no en el diálogo de error de Odoo: no es un fallo
de la vista, es una respuesta.

| Situación | Qué ve el usuario |
| --- | --- |
| 401 | «rechazó la clave de API. Revísela en Ajustes ▸ Gantt IA» |
| 404 | «no reconoce el modelo «…»» |
| 429 | «ha limitado las peticiones. Espere unos segundos» |
| 5xx | «no está disponible ahora mismo» |
| Tiempo agotado | Indica los segundos configurados y dónde subirlos |
| Rechazo por políticas | Se distingue del error técnico (`stop_reason: refusal`) |

Ojo con el tiempo de espera: el de `requests` es **por trozo recibido**, no de
reloj total. Basta para cortar un proveedor caído, pero una respuesta que gotea
puede tardar más que el valor configurado.

## Tests

47 tests, ninguno sale a la red. Cubren disponibilidad, permisos, qué entra en
el contexto, qué se acepta de vuelta, la traducción de errores HTTP y **qué se
manda por el cable a cada proveedor** (URL, cabeceras y el campo de tokens que
cada API nombra distinto), parcheando `requests.post`.

```bash
odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_project_gantt_ai \
         --test-enable --test-tags /al_project_gantt_ai --stop-after-init
```

La verificación E2E se hizo con un proveedor falso local que habla los dos
dialectos (Messages API y Chat Completions): pregunta → respuesta → propuesta →
aplicar → dato guardado, tanto con Anthropic como con DeepSeek.

## Limitaciones conocidas

* Solo backend. La página `/gantt` del website no lleva panel (v1).
* Las propuestas cubren fechas, avance, nombre y personas asignadas. Crear o
  borrar tareas, o cambiar dependencias, se sigue haciendo a mano.
* La conversación no se guarda: vive mientras la vista esté abierta.
* Sin control de gasto por usuario. El coste se acota con «Tareas por consulta»
  y «Tokens máximos», no con una cuota.
