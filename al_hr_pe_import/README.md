# Planillas Perú — Importadores Excel

Cargas masivas desde Excel con plantilla descargable, proceso por lotes,
progreso en vivo y un informe de errores que dice fila por fila qué
corregir.

> **Versión** 2.20260722 · **Depende de** los cinco módulos `al_hr_pe_*` y
> de `openpyxl` · **Licencia** OPL-1

---

## 1. Qué se puede importar

| Plantilla | Para qué |
|---|---|
| **Inputs de boletas** | Novedades del mes de un lote, por documento y código de concepto |
| **Datos PE de la versión** | Los campos peruanos de la ficha laboral, para el alta inicial |
| **Récord vacacional** | Saldos iniciales al arrancar con el sistema |
| **Adelantos** | Altas masivas |
| **Asistencias** | Marcaciones con su zona horaria |
| **Reglas salariales** | Carga y ajuste masivo |

Es el módulo de **cierre** de la suite: sus plantillas cruzan todos los
dominios, y por eso depende de los cinco módulos anteriores.

## 2. Cómo está hecho

Un mixin (`al.import.payroll.mixin`) resuelve una vez lo que toda
importación necesita:

* **La plantilla la genera el sistema.** Se descarga desde el propio
  asistente con las columnas exactas que espera el importador: nadie tiene
  que adivinar el formato ni mantener un Excel de ejemplo aparte.
* **Proceso por lotes.** Se confirma por bloques en vez de todo al final:
  un archivo de diez mil filas no se pierde entero por un fallo en la
  última.
* **Progreso en vivo.** La carga corre en un hilo con su propio cursor y
  publica el avance con otro, así la barra se mueve de verdad mientras el
  proceso trabaja.
* **Errores con sugerencia.** Cada fila que falla se informa con su
  número, el motivo y qué habría que poner. El resultado se descarga como
  Excel.

Acepta `.xlsx` y `.xlsm`, con openpyxl — sin `xlrd` y sin instalar
paquetes en tiempo de ejecución.

## 3. Cómo se usa, paso a paso

1. **Abrir el importador** — *Planillas → Importaciones Excel* y elegir
   qué se va a cargar.
2. **Descargar la plantilla** — trae las columnas correctas y la fila de
   inicio esperada.
3. **Subir y procesar** — el avance se ve en pantalla.
4. **Revisar el informe** — *Planillas → Historial de importaciones* deja
   el registro de qué se cargó, cuándo y con qué errores. Se corrigen las
   filas señaladas y se vuelve a subir solo esas.

## 4. Tests

```bash
odoo-bin -d <bd> -u al_hr_pe_import --test-enable \
         --test-tags /al_hr_pe_import
```
