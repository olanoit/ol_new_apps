# Farmacia: tratamientos crónicos y recompra (AL)

Tratamientos crónicos por paciente: cada compra (caja o pedido de venta) del
medicamento o de un equivalente suma días cubiertos; la botica recuerda la
recompra antes de que se acabe (actividad, WhatsApp y correo opcional), mide
la adherencia (PDC de 180 días) y avisa en la caja al elegir al cliente.

Plan: [docs/farmacia/MEJORAS_PROCESOS.md](../../docs/farmacia/MEJORAS_PROCESOS.md) (E5).

## Cómo se calcula

- Días cubiertos de una compra = unidades compradas ÷ unidades por día. Las
  compras se encadenan: si compra antes de terminar, el saldo se suma al
  final. Las devoluciones acortan lo cubierto.
- **Próxima recompra** = cubierto hasta − días de aviso (Ajustes ▸ Farmacia).
- **Recompra**: cubierto, por reponer (dentro del aviso), atrasado (ya se le
  acabó) o sin compras.
- **Adherencia (PDC)**: días cubiertos de los últimos 180 días (o desde el
  inicio) entre los días del periodo; 80 % o más es adherente.
- Las fechas de las compras se toman en el huso del responsable o de la
  compañía.

## Uso

- Farmacia ▸ Dispensación ▸ Tratamientos crónicos; desde la receta, «Crear
  tratamientos»; desde el contacto, el botón «Tratamientos».
- Cron diario «Farmacia: recordatorios de recompra de tratamientos».
- En la caja, al elegir al cliente aparecen los tratamientos por reponer;
  «Agregar al pedido» los agrega con la presentación y la receta que pida
  cada producto.

## Pruebas

`tests/`: 10 pruebas (cobertura con equivalentes y devoluciones, PDC,
recordatorio único con correo, venta del TPV y pedido de venta, aviso para la
caja, WhatsApp, receta y el recorrido en la caja).
