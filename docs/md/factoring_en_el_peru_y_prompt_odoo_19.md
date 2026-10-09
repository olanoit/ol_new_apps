# Investigación de Factoring y Prompt Profesional para Odoo 19 (Perú)

## 1. Investigación y Marco Contable del Factoring en el Perú

El **factoring** es una herramienta financiera fundamental para las empresas en el Perú (especialmente MYPES), permitiendo convertir cuentas por cobrar a plazo (facturas comerciales convertidas en **Facturas Negociables** como títulos valores) en liquidez inmediata a través de una entidad financiera o empresa de factoring ("el factor").

### A. Tipos de Factoring y Tratamiento Contable (PCGE / NIIF 9)

Desde la perspectiva contable y bajo las Normas Internacionales de Información Financiera (NIIF 9), el tratamiento varía fundamentalmente según la transferencia de riesgos y beneficios:

1. **Factoring Sin Recurso (Con transferencia de riesgo):**
   * **Definición:** La empresa transfiere la factura y **el factor asume el riesgo de incobrabilidad** si el cliente final no paga.
   * **Tratamiento Contable:** Se procede a la **baja (derecognition)** de la cuenta por cobrar comercial (`Cuenta 12`). Se reconoce el efectivo recibido en caja/bancos (`Cuenta 10`), y la diferencia entre el valor nominal de la factura y el efectivo entregado se registra como un **gasto financiero** (`Cuenta 67` - por intereses y comisiones de descuento).

2. **Factoring Con Recurso (Sin transferencia de riesgo):**
   * **Definición:** La empresa transfiere la factura para obtener el adelanto, pero **mantiene el riesgo de incobrabilidad** (si el cliente no paga, la empresa cedente debe devolver el dinero al factor).
   * **Tratamiento Contable:** La cuenta por cobrar **no se da de baja** de inmediato; se mantiene en el activo o se reclasifica a una cuenta de instrumentos financieros, y el importe recibido como adelanto se registra como una **obligación financiera** (`Cuenta 45`). Los intereses se devengan en el tiempo que dure el financiamiento.

### B. Aspectos Tributarios en el Perú (SUNAT)
* **Impuesto General a las Ventas (IGV):** La transferencia o cesión de créditos (la venta de la factura) **no constituye una operación gravada con el IGV**. Sin embargo, los servicios financieros accesorios (intereses por el adelanto y comisiones de estructuración o cobranza) cobrados por empresas del sistema financiero están inafectos o sujetos a las reglas de servicios financieros de la Ley del IGV.
* **Comprobantes:** No se emite una factura adicional por la cesión del crédito; la operación se sustenta con el contrato de factoring y la respectiva Factura Negociable anotada en una ICL (Institución de Compensación y Liquidación de Valores, como CAVALI) o canalizada mediante entidades autorizadas.

---

## 2. Enlaces y Fuentes de Documentación Verificada

Para que los agentes de desarrollo e investigación cuenten con bases sólidas y oficiales al momento de construir el módulo, se han recopilado las siguientes referencias clave:

### Marco Legal, Financiero y Contable (Perú)
* **[Reglamento de la Ley N° 29623 (MEF)](https://www.mef.gob.pe/en/por-instrumento/decreto-supremo/12989-anexos-01-02-03-escolaridad/file):** Decreto Supremo que regula la Ley que promueve el financiamiento a través de la factura comercial, esencial para entender el tratamiento de títulos valores y obligaciones.
* **[Informe Técnico Legal sobre Factura Negociable y Factoring (CAVALI)](https://www.cavali.com.pe/factrack/uploads/shares/Decreto_legislativo_1529.pdf):** Documento oficial de la Institución de Compensación y Liquidación de Valores respecto al impacto normativo y los flujos operativos de las facturas negociables.

### Marco Técnico (Odoo 19)
* **[Guía sobre Runtime Documentation y APIs en Odoo 19](https://www.zbeanztech.com/blog/general-11/api-documentation-url-in-odoo-19-runtime-documentation-193):** Resumen técnico del funcionamiento de las nuevas herramientas de introspección y documentación nativa de modelos en Odoo 19.
* **[Video de Referencia Técnica API Odoo 19](https://www.youtube.com/watch?v=wARVXWjMBtc):** Recurso audiovisual útil para comprender cómo interactuar con las referencias de modelos nativos y optimizar las consultas de desarrollo dentro de la versión 19.

---

## 3. Prompt Profesional para Desarrollar el Módulo en Odoo 19

```text
Actúa como un Arquitecto de Software Senior y Consultor Experto en Odoo 19 especializado en localizaciones de negocios. 

Primero, investiga y analiza a fondo el marco contable, financiero y legal del factoring en el Perú, utilizando obligatoriamente fuentes oficiales de referencia como el Reglamento de la Ley N° 29623 (MEF) y los lineamientos de CAVALI para la Factura Negociable, así como la documentación técnica y de runtime estándar de Odoo 19.

A partir de dicha investigación, diseña la solución funcional y arquitectónica para un módulo en Odoo 19 que permita gestionar este proceso de manera integrada. 

Asegúrate de seguir estrictamente las mejores prácticas del estándar de Odoo 19, priorizando la máxima reutilización de los flujos nativos de facturación, gestión de cobros y contabilidad del sistema, y presenta una propuesta limpia, modular y profesional basada en los resultados de tu investigación.
```