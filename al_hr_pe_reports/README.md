# Planillas Perú — Documentos y bancos

La boleta legal peruana con un solo botón de imprimir, los certificados,
los contratos y los archivos de pago masivo de los cinco bancos.

> **Versión** 4.20260802 · **Depende de** `al_hr_pe_benefits` ·
> **Licencia** LGPL-3

---

## 1. Qué incluye

* **Boleta de pago** (D.S. N.° 001-98-TR): tres columnas de ingresos,
  descuentos y aportes del empleador con su código SUNAT, días y horas del
  periodo, suspensiones, neto en letras y las dos firmas.
* **Certificados y cartas**: certificado de trabajo, carta de disposición
  de CTS y certificado de rentas de 5ta, en asistentes que aceptan varios
  empleados a la vez.
* **Contratos**: plantillas por compañía rellenadas sobre la ficha del
  trabajador con marcadores `{{…}}`, sin motor de plantillas externo.
  Incluye el régimen de prueba del art. 10 de la LPCL.
* **Pago masivo bancario**: formatos propietarios de BCP, BBVA, Interbank,
  Scotiabank y BanBif, para haberes y para CTS.

## 2. Un solo botón de imprimir

Odoo permite varias plantillas de boleta y deja al usuario la elección. En
una planilla peruana eso es una fuente de errores: la boleta legal es una,
y basta con equivocarse un mes.

Aquí **la estructura salarial declara cuál es su boleta** y el botón
nativo la resuelve. Una empresa con régimen general y construcción civil
imprime cada boleta con su plantilla sin cambiar de menú ni de criterio.

El mecanismo respeta una plantilla peruana ya elegida: si la estructura
apunta a un reporte propio, se usa ese. Lo que evita es que salga la
boleta genérica de Odoo por descuido.

> **Para añadir la boleta de un régimen nuevo**: se crea una variante
> `primary` que herede la plantilla base, se le pone `l10n_pe` en el
> nombre del reporte y se apunta desde `struct_id.report_id`.

## 3. El envío por correo

La boleta se envía en PDF adjunto y el correo lleva un enlace de
confirmación firmado con un **token HMAC** derivado del secreto de la
base. Cuando el trabajador confirma, queda registrada la recepción con su
fecha — que es lo que la norma pide poder demostrar.

El token importa: sin firma, cualquiera con el enlace podría dar por
recibida la boleta de otro.

## 4. Los archivos de pago al banco

| Banco | Cubre |
|---|---|
| BCP | Haberes y CTS |
| BBVA | Haberes y CTS |
| Interbank | Haberes y CTS |
| Scotiabank | Haberes y CTS |
| BanBif | Haberes y CTS |

Se generan desde lotes de boletas, quincena, CTS, gratificaciones y
vacaciones. Los formatos se portaron con **paridad byte a byte** respecto
de la versión anterior: un archivo que el banco aceptaba lo sigue
aceptando, carácter por carácter.

## 5. Cómo se usa, paso a paso

1. **Configurar los datos del documento** — *Parámetros principales*:
   representante que firma, categorías de conceptos de la boleta y la
   regla que da el neto a pagar.
2. **Preparar las plantillas de contrato** — *Planillas → Configuración →
   Plantillas de contrato*, una por tipo de contrato y compañía.
3. **Imprimir o enviar la boleta** — sale la del régimen que corresponda;
   el envío deja constancia cuando el trabajador confirma.
4. **Emitir certificados** — desde la ficha del empleado, para uno o
   varios de una vez.
5. **Generar el archivo del banco** — *Planillas → Pagos masivos
   bancarios*: origen, banco y tipo de pago; el archivo queda como
   adjunto.

## 6. Tests

```bash
odoo-bin -d <bd> -u al_hr_pe_reports --test-enable \
         --test-tags /al_hr_pe_reports
```
