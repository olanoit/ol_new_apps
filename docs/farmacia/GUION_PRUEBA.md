# Guion de prueba funcional — suite de farmacias y boticas

> Base: **farmacia-dev** (https://farmacia-dev.altalatam.com, base
> `farmacia_dev_1`), con el catálogo de botica cargado (15 medicamentos con
> stock y lote, presentaciones, directora técnica Rosa Quispe Huamán, dos
> médicos, puntos de control, listado de genéricos). Usuario administrador
> (tiene el rol Administrador de farmacia). Plan:
> [`PLAN_FARMACIA.md`](PLAN_FARMACIA.md).

Marque cada paso: ✅ funciona · ❌ falla (anote qué pasó) · ➖ no aplica.

## 1. Maestro farmacéutico

| # | Paso | Resultado esperado | ✓ |
|---|---|---|---|
| 1.1 | **Farmacia ‣ Productos ‣ Productos farmacéuticos**, abrir «Dolofen 500 mg tableta» | Pestaña **Farmacia** con registro sanitario, laboratorio, condición de venta «Venta libre», tipo «Innovador», composición Paracetamol 500 mg | |
| 1.2 | En la misma ficha, campo **Equivalentes** | Aparece «Paracetamol 500 mg tableta» | |
| 1.3 | Pestaña **Presentaciones** | Blíster x 10 a S/ 5,50 y Caja x 100 a S/ 50,00 | |
| 1.4 | Lista de productos, filtro **Con receta** | Amoxicilina, Azitromicina, Losartán, Metformina, Insulina, Clonazepam, Alprazolam… | |
| 1.5 | Abrir «Clonazepam 2 mg tableta» | Lista de fiscalización IVA, libro de psicotrópicos | |

## 2. Establecimiento

| # | Paso | Resultado esperado | ✓ |
|---|---|---|---|
| 2.1 | **Farmacia ‣ Establecimiento ‣ Turnos de Q.F.** | Turno de Rosa Quispe Huamán como directora técnica | |
| 2.2 | **Libro de ocurrencias ‣ Nuevo**: tipo Incidente, «Prueba de corte de luz» | Se guarda con número OC/2026/… | |
| 2.3 | Intentar editar el detalle del asiento guardado | No se puede; botón **Corregir** crea un asiento nuevo que cita al anterior | |
| 2.4 | **Farmacia ‣ Configuración ‣ Ajustes**, bloque Farmacia | Venta sin receta: Bloquear; Sin Q.F. en turno: Avisar; 90 días; tipo Botica | |

## 3. Almacenamiento

| # | Paso | Resultado esperado | ✓ |
|---|---|---|---|
| 3.1 | **Compras**: OC a un proveedor de 12 cajas de Losartán (o 1200 unidades) con **Bonificación** 100 | Aparece una línea «Bonificación: …» a precio 0; el total no cambia | |
| 3.2 | Confirmar y abrir la recepción; validar sin tocar la pestaña Farmacia | Mensaje: registre la inspección | |
| 3.3 | Marcar **No conforme** con observación, poner lote y vencimiento, validar | Se valida; el lote nuevo queda en **Cuarentena** | |
| 3.4 | Abrir el lote y pulsar **Liberar** | Pasa a Disponible | |
| 3.5 | **Lotes y vencimientos** | Filtro «Por vencer» activo | |
| 3.6 | **Control ambiental ‣ Lecturas**: Refrigeradora, 11 °C sin acción correctiva | No deja guardar | |
| 3.7 | Agregar la acción correctiva y guardar | Se guarda en rojo; asiento nuevo en el libro de ocurrencias | |
| 3.8 | **Alertas sanitarias ‣ Nuevo**: «ALERTA DIGEMID 999-2026», Amoxicilina con su lote; **Confirmar y bloquear lotes** | Lote bloqueado; pestaña Impacto con el stock | |
| 3.9 | **Actas de baja ‣ Nuevo**: el lote bloqueado, 10 unidades, motivo Alerta; **Validar y dar de baja**; imprimir | Baja de inventario hecha y acta en PDF | |

## 4. Caja

Abra **Punto de venta ‣ Botica Principal**.

| # | Paso | Resultado esperado | ✓ |
|---|---|---|---|
| 4.1 | Tocar «Dolofen 500 mg tableta» | Ventana de alternativas: primero «Paracetamol 500 mg tableta» (genérico en DCI, más barato) | |
| 4.2 | Elegir el genérico y luego **Blíster x 10** | Línea «1 Paracetamol 500 mg tableta (Blíster x 10)» a S/ 1,50; pide el lote | |
| 4.3 | Tocar «Amoxicilina 500 mg cápsula» | Ventana **Receta médica** (el administrador no es Q.F.: aviso de venta sin Q.F.) | |
| 4.4 | Completar N.º 000555, prescriptor «Dra. Ana Torres Quispe», colegiatura 067890, paciente; **Registrar receta**; elegir Blíster x 10 | Línea agregada | |
| 4.5 | Cobrar en efectivo | Ticket emitido | |
| 4.6 | **Farmacia ‣ Dispensación ‣ Recetas** | Receta 000555 dispensada, prescriptor existente, dispensación con lote y venta | |
| 4.7 | **Libro de ocurrencias** | Asiento «Venta … sin químico farmacéutico en la caja» | |
| 4.8 | En la caja, tocar «Clonazepam 2 mg tableta» | Ventana de **Receta especial** sin botones de excepción | |

## 5. Controlados y DIGEMID

| # | Paso | Resultado esperado | ✓ |
|---|---|---|---|
| 5.1 | **Controlados ‣ Libros y balance**: psicotrópicos, trimestre actual, **PDF** | Libro con la entrada de clonazepam y alprazolam | |
| 5.2 | Balance trimestral, **Excel** | Archivo con saldo inicial, entradas, salidas y saldo final | |
| 5.3 | **DIGEMID ‣ Precios para el Observatorio** | Pendientes de los productos con código DIGEMID | |
| 5.4 | Cambiar el precio de un producto y volver | Su pendiente muestra el precio nuevo | |
| 5.5 | **Exportar al Observatorio** | Descarga el Excel; los pendientes pasan a Informado | |
| 5.6 | **Cumplimiento de genéricos ‣ Calcular** | Ítems de marca con genérico; porcentaje y «Cumple» | |
| 5.7 | **Lista de precios por DCI** | PDF por principio activo, de menor a mayor | |
| 5.8 | **Reacciones adversas ‣ Nuevo**: grave | Plazo a 24 horas; asiento en el libro | |
| 5.9 | Prescriptor «Dr. Jorge Salazar Pérez» ‣ **Consultar en el CMP** | Abre conoceatumedico.cmp.org.pe | |
| 5.10 | **Verificado: inhábil** y validar una receta suya | No valida: prescriptor inhábil | |

## Pendientes conocidos

- La boleta y la factura electrónicas no se envían a SUNAT en farmacia-dev (sin
  certificado ni operador): la caja emite recibos.
- El archivo del Observatorio usa columnas por confirmar con DIGEMID.
- El precio de las presentaciones no aplica listas de precios ni descuentos.
