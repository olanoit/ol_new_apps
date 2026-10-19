---
modulos: [al_pharmacy_base]
---

# Farmacia y botica

La suite de farmacia administra una farmacia o botica completa sobre Odoo: el
maestro de medicamentos con sus datos sanitarios, el almacén según las buenas
prácticas, la caja con receta y alternativas genéricas, los productos
controlados y las obligaciones con DIGEMID. Sigue el Manual de Buenas
Prácticas de Oficina Farmacéutica (RM 554-2022/MINSA), la Ley 29459 y la
Ley 32033.

| Página | Para qué |
|---|---|
| [Productos y presentaciones](pharmacy/products.md) | Principio activo, registro sanitario, condición de venta, equivalentes y venta por caja, blíster o unidad |
| [Almacenamiento](pharmacy/storage.md) | Recepción, lotes y vencimientos, temperatura, alertas sanitarias, actas de baja y bonificaciones |
| [Receta y dispensación en la caja](pharmacy/dispensing.md) | Receta, prescriptores y pacientes, alternativas genéricas y control del químico farmacéutico |
| [Estupefacientes y psicotrópicos](pharmacy/controlled.md) | Receta especial, retención con folio, libros y balance trimestral |
| [DIGEMID, genéricos e IGV](pharmacy/digemid.md) | Observatorio de precios, 30 % de genéricos, precios por DCI, cartel de empresas vinculadas, reacciones adversas e IGV exonerado |
| [Tratamientos crónicos y recompra](pharmacy/care.md) | Días cubiertos, recordatorio por WhatsApp, adherencia y aviso en la caja |
| [Faltantes y sugerido de compra](pharmacy/replenishment.md) | Lo que se pide y no hay, y compra por consumo de cada local |
| [Fidelización por DNI](pharmacy/loyalty.md) | Puntos y vales para los clientes sin premiar los medicamentos con receta |

## Configuración

1. Instale el paquete **Industria: Farmacia y botica** desde **Aplicaciones**
   (categoría OL-INDUSTRIES). Instala todos los módulos de la suite.
2. Asigne a cada usuario su rol en **Ajustes ‣ Usuarios ‣ Farmacia**:

    | Rol | Puede |
    |---|---|
    | Técnico en farmacia | Atender, recibir mercadería, registrar temperaturas. No dispensa con receta |
    | Químico farmacéutico | Además, dispensar con receta, liberar lotes, validar actas y ver datos de salud |
    | Director técnico | Además, firmar actas, balances y alertas |
    | Administrador | Además, configurar catálogos y ajustes |

3. En cada empleado indique su **Función en farmacia** y, si es químico
   farmacéutico, su colegiatura.
4. En cada local (**Inventario ‣ Configuración ‣ Almacenes**) indique el
   **Director técnico** y el **Código de establecimiento**.
5. Revise **Farmacia ‣ Configuración ‣ Ajustes**:
    - **Venta sin receta**: bloquear (por defecto) o solo avisar.
    - **Sin Q.F. en turno**: avisar (por defecto) o bloquear.
    - **Aviso de vencimientos**: días de anticipación (90 por defecto).

## Datos de demostración

En una base creada con datos de demostración, cada módulo de la suite trae lo
que necesita para probarse:

| Módulo | Trae |
|---|---|
| Maestro farmacéutico | 14 medicamentos con composición y presentaciones, laboratorios, directora técnica, Q.F., técnica, turnos y libro de ocurrencias |
| Buenas prácticas de almacenamiento | Lotes y existencias (uno por vencer, uno en cuarentena), control ambiental con una lectura fuera de rango, compra 12 + 1 por recibir, alerta sanitaria y acta de baja en borrador |
| Receta y dispensación | Prescriptores hábil, sin verificar e inhábil; pacientes con alergia; recetas por validar, vigente, dispensada en parte y vencida |
| Punto de venta | Los medicamentos disponibles en la caja |
| Verificación en el CMP | Colegiaturas verificadas con su consejo regional |
| Estupefacientes y psicotrópicos | Clonazepam y alprazolam (lista IVA), morfina (lista IIA), receta especial vigente y receta retenida con folio |
| DIGEMID, genéricos e IGV | Códigos y precios por informar al Observatorio, régimen del IGV, autorización del local, genéricos esenciales y reacciones adversas |
| Unidad SUNAT de las presentaciones | Clientes con DNI y con RUC |
| Tratamientos crónicos y recompra | Dos pacientes con losartán y metformina |
| Faltantes y sugerido de compra | Un faltante de losartán y uno de un colirio fuera del catálogo |
| Fidelización por DNI | Programa «Club de Salud»: 1 punto por S/ 4 y un vale de S/ 5 cada 1 000 puntos |

## Turnos y libro de ocurrencias

- **Farmacia ‣ Establecimiento ‣ Turnos de Q.F.**: quién atiende en cada local.
  Un turno de **Reemplazo del director técnico** se anota solo en el libro.
- **Farmacia ‣ Establecimiento ‣ Libro de ocurrencias**: el libro que exige la
  BPOF. Solo admite asientos nuevos: para corregir uno, ábralo y pulse
  **Corregir**; el original queda legible. La suite agrega sola los asientos
  de excepciones, alertas sin Q.F., lecturas fuera de rango, alertas
  sanitarias y reacciones adversas. Se imprime desde la lista.

!!! note "Nota"
    Los datos de salud de los pacientes (alergias, condiciones crónicas,
    diagnóstico) solo los ven los químicos farmacéuticos (Ley 29733).

## Comprobantes electrónicos

La botica emite boletas y facturas con la
[facturación electrónica de la suite](../finance/fiscal_localizations/peru/electronic_invoicing.md):
series propias para boletas (B001) y facturas (F001), y en la caja el cliente
elige boleta o factura al pagar. La caja o el blíster sale en el comprobante
con su unidad SUNAT (BX, BO…) y los medicamentos exonerados con «0% Exo».

| Caso de botica | Cómo se emite |
|---|---|
| Venta a un cliente con RUC | Factura; en la caja, solo si el cliente tiene RUC |
| Venta al público | Boleta; con DNI desde S/ 700 |
| Muestra médica o bonificación con la compra | Leyenda **1002** y el ítem gratuito con **18% Libre Final** |
| Bolsa plástica | Producto con IGV e **ICBPER** (S/ 0,50 por bolsa) |
| Devolución en la caja | Nota de crédito de la boleta o factura original |
| Venta al crédito | Plazo de pago con cuotas que vencen después de la emisión |

!!! warning "Importante"
    SUNAT rechaza una factura al crédito si alguna cuota vence el mismo día de
    la emisión: no use plazos con una parte «ahora» (por ejemplo «30 % ahora, el
    resto en 60 días»); cree uno con cuotas a 30 y 60 días.

!!! note "Nota"
    Las boletas no se dan de baja: se anulan con una nota de crédito.
