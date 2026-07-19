[← Índice](README.md)

# Exportar PLE (wizard central)

**Menú:** Perú ▸ Libros PLE ▸ Exportar PLE · **Permiso:** Contabilidad /
Contador (`account.group_account_user`).

Es el punto único de generación de los TXT que produce este módulo. Se abre
como diálogo, se marcan los formatos deseados y el botón **Generar** deja el
archivo descargable en el propio wizard (un TXT si es un solo formato, un
ZIP si son varios).

## Parámetros

| Campo | Uso |
|---|---|
| **Compañía** | Multicompañía: cada compañía genera con su RUC. |
| **Ejercicio** | Año fiscal; único dato para los libros anuales (7 y 10). |
| **Mes** | Aparece al marcar un libro mensual (4.1, 9.x, simplificados). |
| **Indicador de operaciones** | `1` empresa operativa (valor normal); `2` cierre del libro; `0` baja de RUC. Forma parte del nombre del archivo. |
| **Fecha de los EEFF** | Solo Libro 3: fecha del balance (por defecto 31/12 del ejercicio); define el `AAAAMMDD` del nombre. |
| **Oportunidad (CC)** | Solo Libro 3: `01` al 31/12 (habitual) … `07` libre propósito. |
| **3.23 Notas (PDF)** | Adjuntar el PDF de notas a los EEFF: se incluye en el ZIP con el nombre oficial (no tiene estructura TXT). |
| **Incluir Excel** | Activada por defecto: además del TXT oficial genera un `.xlsx` de revisión por cada formato (mismos datos, encabezados del Anexo 2, formato heredado del módulo v18) dentro del ZIP. El TXT es el único archivo que se carga al PLE de SUNAT; el Excel es para revisión del contador. |

## Formatos disponibles

- **Libro 7 (anual):** 7.1, 7.3, 7.4 — ver [libro_7_activos_fijos.md](libro_7_activos_fijos.md).
- **Mensuales:** 4.1 ([retenciones_4_1.md](retenciones_4_1.md)),
  9.1/9.2 ([consignaciones_libro_9.md](consignaciones_libro_9.md)).
- **Libro 3 (a la fecha de EEFF):** 3.8 ([inversiones_3_8.md](inversiones_3_8.md)),
  3.9 (automático: activos con cuenta `34…`, ver más abajo),
  3.19 ([patrimonio_3_19.md](patrimonio_3_19.md)), 3.23 (PDF).
- **Libro 10 (anual):** 10.1–10.4 ([costos_libro_10.md](costos_libro_10.md)).
- **Simplificados (mensuales):** 5.2/5.4, 8.3, 14.2 — solo visibles con la
  bandera de Ajustes ([simplificados.md](simplificados.md)).

### 3.9 Intangibles (sin menú de captura)

No requiere captura: toma automáticamente los activos (`account.asset`)
cuya **cuenta contable empieza por 34** (PCGE) vigentes a la fecha de los
EEFF, con su amortización acumulada según los asientos de depreciación
publicados hasta esa fecha. Configuración: solo asegurar que el intangible
esté registrado como activo con la cuenta 34x correcta.

## Errores frecuentes

| Mensaje | Causa / solución |
|---|---|
| «…no tiene configurado un RUC válido…» | Completar el NIF de la compañía (11 dígitos). |
| «Indique el mes…» | Se marcó un libro mensual sin elegir mes. |
| «Los siguientes activos no tienen configurado…» | Falta un dato SUNAT en la pestaña PLE de los activos listados. |
| «Los formatos simplificados… Habilítelos en Ajustes» | Falta la bandera de régimen simplificado. |
