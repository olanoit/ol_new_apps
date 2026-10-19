# Requerimiento de obra — selección de nivel y etapa

Oct 16, 2026 · @Vicente

## Objetivo y plazo

Que quien pide material (supervisor, jefe de producción, jefe de proyectos, asistente de proyectos) indique en el mismo requerimiento de obra para qué obra, qué niveles (pisos, departamentos, ambientes, muebles), qué etapa y qué tareas del Gantt es el material, eligiendo varios a la vez, y que el formulario traiga del plan de recursos lo que falta pedir.

Plazo: en producción el lunes 19-oct-2026, junto con el planificador. Es un desarrollo corto: no reemplaza al asistente «Requerimiento de obra desde el plan», que sigue siendo la vía completa.

Este documento va aparte de los paquetes 1.7 y 1.8. Usa sus propios códigos (RQ-01 a RQ-08) para no chocar con la numeración M18.

## Estado actual

Fuente: lectura de `newallcenter_dev_1` y `newallcenter_dev_2` el 16-oct-2026. En las dos bases están instaladas las mismas versiones: Requerimiento de materiales de obra (AL) 19.0.18.20261013 y Planificación de obra (AL) 19.0.33.20261013.

| Elemento | Qué hay hoy |
| --- | --- |
| Cabecera del requerimiento | Obra (obligatoria) y un solo campo Tarea. No se puede elegir más de un nivel |
| Línea del requerimiento | Tarea por línea (columna oculta por defecto), Saldo del plan y Control. No tiene etapa |
| Plan de recursos | Cada línea de material trae su nivel, los niveles superiores (piso, departamento, ambiente, mueble, módulo y los genéricos nivel 1 a 6), la etapa y el saldo por pedir |
| Asistente «Requerimiento de obra desde el plan» | Ya permite elegir varios niveles, varias etapas y agrupar por piso, departamento o ambiente. Hoy se abre desde el formulario del plan de recursos, no desde el requerimiento |
| Control de exceso | El requerimiento ya enlaza sus líneas con el plan y marca «Excede el plan» |

## Requerimientos

### Selección de alcance en la cabecera (RQ-01)
- Recuadro «¿Para qué es el material?» debajo de la obra, en estado Borrador.
- Un selector de varios valores por cada nivel de la plantilla de niveles de la obra, en cascada: cada lista muestra solo los hijos de lo elegido arriba. En mobiliario son Piso, Departamento, Ambiente y Mueble; en construcción por partidas, Disciplina, Subpartida y Partida. Las etiquetas salen de la plantilla de niveles, no se escriben en el código.
- Un nivel sin elegir significa «todos los de arriba». Si solo se eligen pisos, el alcance es todo lo que cuelga de esos pisos.
- El selector de Mueble no aparece si la obra no tiene ese nivel (caso ZZMOMEN PRUEBA, donde los módulos cuelgan del ambiente).

### Etapas (RQ-02)
- Selector de varias etapas del planificador (Producción, Armado, Instalación, Acabado y entrega, o las de la vertical).
- Cada línea del requerimiento guarda su etapa en un campo nuevo, visible como columna.

### Tareas del Gantt (RQ-03)
- Selector opcional de varias tareas de la obra en el Gantt.
- Las tareas del Gantt que no son nivel del planificador no tienen líneas en el plan: el material se agrega a mano y cada línea queda con esa tarea.

### Traer materiales del plan (RQ-04)
- Botón «Traer materiales del plan». Toma el nivel más bajo elegido y crea una línea por material, nivel y etapa con cantidad igual al saldo por pedir.
- Quien pide corrige cantidades o borra líneas antes de solicitar aprobación.
- Cada línea queda enlazada a su línea del plan, así el control de exceso que ya existe sigue funcionando.
- Si se pulsa otra vez, agrega lo que falta sin duplicar líneas ya traídas.
- Puede reutilizar la lógica del asistente «Requerimiento de obra desde el plan»; la diferencia es que llena el requerimiento abierto en vez de crear uno nuevo.

### Columnas de la línea (RQ-05)
- Visibles: Material, Nivel (ruta corta, por ejemplo «Dpto 102 / Cocina»), Etapa, Saldo, Cantidad, Unidad, Disponible.
- Saldo y Control solo cuando la obra tiene plan de recursos.

### Obra sin plan o sin niveles (RQ-06)
- El formulario funciona como hoy: se elige la obra y se agrega material a mano. Nadie queda bloqueado si su obra aún no está en el planificador.

### Material de producción, temporal (RQ-07)
- La vía regular del material de producción es la orden de fabricación. Mientras el flujo de orden de fabricación del planificador no esté listo, el jefe de producción también puede pedir por este formulario eligiendo la etapa Producción.
- Cuando la etapa es Producción, el material se despacha a la ubicación de preproducción de la planta (BRE/Preproducción o PPD/Preproducción, que existen en `newallcenter_dev_2`); quien pide elige la planta. El costo sigue yendo a la obra por la distribución analítica de la línea. Las demás etapas van a la ubicación de la obra, como hoy.
- Si un mismo requerimiento mezcla Producción con otras etapas, el despacho se separa en una transferencia por destino.
- Ajuste en Configuración: «Permitir la etapa Producción en el requerimiento de obra», activo por defecto. Cuando se desactive, la etapa Producción deja de aparecer en el selector.

### Permisos (RQ-08)
- Se usa el grupo «Solicitante» que ya trae el módulo de requerimiento de obra. No requiere desarrollo.
- Lo tendrán el jefe de proyectos, el jefe de producción y los supervisores de proyectos. La asignación de usuarios la configura ALTA.
- La aprobación y el despacho siguen como están hoy (validación por niveles y almacén).

## Fuera de alcance para el lunes
- Pedido del capataz por el portal.
- Agrupación de líneas por piso o departamento (ya la tiene el asistente desde el plan).
- Cambios en el flujo de aprobación.

## Pantalla

Imagen adjunta: «Requerimiento de obra — selección de nivel y etapa (pantalla).png». El recuadro con borde azul es lo nuevo. Esquema en texto:

```
Requerimiento de obra  RQO/2026/00011                       [Borrador]
Obra: ZZMOMEN-98-26 MOMEN PRUEBA          Plan de recursos: PLR/2026/00001

┌ ¿Para qué es el material? ───────────────────────────────────────────┐
│ Pisos           [Piso 01 ×]                                          │
│ Departamentos   [Dpto 101 ×] [Dpto 102 ×]                            │
│ Ambientes       [Cocina · Dpto 101 ×] [Cocina · Dpto 102 ×]          │
│ Muebles         (no aparece: la obra no tiene nivel Mueble)          │
│ Etapas          [Armado ×]                                           │
│ Tareas del Gantt  (opcional)                                         │
│ [Traer materiales del plan]                                          │
└──────────────────────────────────────────────────────────────────────┘
Material                         Nivel              Etapa   Saldo  Cant.  Unidad
Bisagra lateral Danco            Dpto 101 / Cocina  Armado    10    10   Unidades
Bisagra push open copa 35 mm     Dpto 101 / Cocina  Armado     4     4   Unidades
Corredera telescópica 50 cm      Dpto 101 / Cocina  Armado     3     3   Juego
Tarugo trefilado capirona 8x30   Dpto 101 / Cocina  Armado    36    36   Unidades
Bisagra lateral Danco            Dpto 102 / Cocina  Armado    18    18   Unidades
Bisagra push open copa 35 mm     Dpto 102 / Cocina  Armado     4     4   Unidades
Corredera telescópica 50 cm      Dpto 102 / Cocina  Armado     3     3   Juego
Tarugo trefilado capirona 8x30   Dpto 102 / Cocina  Armado    48    48   Unidades
```

## Criterio de aceptación

En `newallcenter_dev_1`, obra ZZMOMEN-98-26 MOMEN PRUEBA, plan PLR/2026/00001:
1. Elegir Piso 01, Dpto 101 y Dpto 102, ambiente Cocina de ambos y etapa Armado, y pulsar «Traer materiales del plan»: se crean 8 líneas, las de la pantalla, con valor estimado S/ 100.18 (S/ 43.67 de Dpto 101 y S/ 56.51 de Dpto 102).
2. Elegir solo Piso 01 y Armado: trae los materiales de Armado de todos los ambientes del piso.
3. Pulsar el botón dos veces no duplica líneas.
4. Pedir más que el saldo marca la línea como «Excede el plan».
5. Una obra sin plan de recursos permite agregar material a mano como hoy.
6. Un requerimiento con etapa Producción y planta Breña genera la transferencia a BRE/Preproducción, con la analítica de la obra.
7. Con el ajuste de material de producción (RQ-07) desactivado, la etapa Producción no aparece.

## Fuentes
- Modelos, campos, vista del formulario y datos del plan: `newallcenter_dev_1` y `newallcenter_dev_2`, lectura del 16-oct-2026.
- Cantidades y montos de la pantalla y del criterio de aceptación: plan PLR/2026/00001 de ZZMOMEN PRUEBA en `newallcenter_dev_1`, ambientes Cocina de Dpto 101 (tipo 09) y Dpto 102 (tipo 06), etapa Armado.
- El número RQO/2026/00011 es ilustrativo.
- Grupos de usuario y ubicaciones de preproducción: `newallcenter_dev_2`, lectura del 16-oct-2026.
- Decisiones de Vicente del 16-oct-2026: selección de varios niveles, etapa y tarea del Gantt; manda el nivel más bajo elegido; producción puede pedir por aquí de forma temporal y su material va a preproducción de la planta; permisos con el grupo Solicitante para jefe de proyectos, jefe de producción y supervisores.
