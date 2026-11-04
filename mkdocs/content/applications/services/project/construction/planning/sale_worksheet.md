---
modulos: [al_construction_planner_spreadsheet_furniture]
---

# Hoja de venta de mobiliario

La hoja de venta responde qué se vende y a qué precio. Nace con la cotización, antes
de que exista la obra, y sigue el orden en que el analista de presupuestos lee los
planos. La usa Presupuestos; cuando la venta se adjudica, su contenido llega a la
hoja de planificación.

## Configuración

Tres listas se mantienen en **Planificación de obra ‣ Configuración ‣ Plan de obra**:

- **Parámetros de las hojas de trabajo**: IGV, redondeo, recargos por acabado, factor
  sobre costo. Cada hoja nueva copia los valores iniciales.
- **Tarifario de venta de mobiliario**: una línea por ítem, con su precio base, moneda,
  cliente con convenio y vigencia. Se carga desde Excel. Un precio con **Desde** cierra
  el anterior el día previo.

En **Ajustes ‣ Planificación de obra**, indique el **Producto de venta por partida**,
el **Responsable de planificación** y la **Plantilla de hitos por defecto**.

La cotización crea esta hoja si el perfil de la plantilla de proyecto del producto, o
el de la compañía, abre la hoja de mobiliario.

## Cotizar

1. En **Ventas**, abra la cotización y pulse **Hoja de trabajo**.
2. Siga la ruta de **INICIO**: cada paso dice qué falta y lleva a su pestaña.
3. En **EDIFICIO**, escriba cada rango de departamentos iguales. En las filas de abajo
   basta el ambiente y la tipología: el rango se repite.
4. En **ACABADOS**, copie la leyenda del cliente y elija el acabado por defecto de cada
   partida.
5. En **PRECIOS**, elija partida e ítem. El precio sale solo: base, medida, recargo y
   redondeo. Un precio acordado se escribe aparte y queda en ámbar.
6. En **METRADO**, escriba las medidas de cada tipología. Acepta sumas, como
   `=1.27+1.27`. Si la medida del plano es mayor, vale esa y se marca.
7. Revise **RESUMEN VENTA**.

Para cotizar en grueso, use un ítem de grupo **Global**: por ML, por ambiente o por
costo estimado.

## Pasar a la cotización y enviar

1. Pulse **Hoja de venta ‣ Pasar el resumen a la cotización**. Valida la hoja: con
   errores no sigue; los avisos no impiden nada.
2. Revise las líneas por partida y los dos totales, y confirme.
3. En **Ventas**, use **Enviar por correo**: lleva el PDF de esta versión. La hoja pasa a
   **Cotización enviada** y queda de solo lectura.

!!! note
    El PDF se arma con lo que se pasó a la cotización. Si cambia la hoja, vuelva a
    pasar el resumen antes de enviar.

## Cambios del cliente

Pulse **Hoja de venta ‣ Nueva versión**: guarda la versión vigente con su PDF, sube el
número y abre la hoja. Escriba quién pidió el cambio en **OBRA**. Desde una hoja
adjudicada la fase es **Adicional en curso**, y al pasar el resumen se agregan líneas
«Adicional» con la diferencia, sin tocar las confirmadas.

## De la venta a la planificación

Al confirmar la venta, el responsable de planificación recibe una actividad. Al crear
la hoja de planificación de la obra, **Traer la venta** muestra por pestaña lo nuevo,
lo que cambia, lo igual y lo que sobra. Lo que editó a mano queda desmarcado y solo se
reemplaza si lo marca. Se deshace con **Restaurar versión**.

Después elija el tablero de cada acabado en **ACABADOS DE OBRA**. Al validar, las piezas
sin producto reciben su propuesta de tablero, agrupada por tipología, grupo y zona.
