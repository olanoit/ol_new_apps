---
modulos: [al_industry_base]
---

# Industrias

Como los paquetes de industria de Odoo (por ejemplo **Pharmacy**), cada
paquete de la carpeta `OL-INDUSTRIES` instala de una vez las aplicaciones de
Odoo y los módulos de la suite que usa un rubro, y deja la base lista para
empezar: categorías, etiquetas, opciones de inventario, datos de demostración
y la actividad económica de la compañía.

| Industria | Para quién | CIIU |
|---|---|---|
| [Farmacia y botica](pharmacy.md) | Farmacias, boticas y droguerías minoristas | 4772 |
| [Constructora](construction.md) | Constructoras y contratistas generales | 4100 |
| [Mobiliario a medida](furniture.md) | Contratas que fabrican e instalan muebles en obra | 3100 |
| [Bodega y minimarket](retail.md) | Bodegas, minimarkets y tiendas de barrio | 4711 |
| [Restaurante](restaurant.md) | Restaurantes, cafeterías y pollerías | 5610 |
| [Tienda en línea](ecommerce.md) | Comercios con tienda web y pago en línea | 4791 |

## Industrias por compañía

**Ajustes ‣ Usuarios y compañías ‣ Industrias** lista los paquetes instalados,
su actividad CIIU y las compañías donde se aplicaron. Al instalarse, cada
paquete configura la compañía activa; para configurar otra:

1. Cámbiese a esa compañía.
2. Abra la industria y haga clic en **Aplicar a la compañía activa**.

Aplicar solo completa lo que falta: si la compañía ya tiene actividad
económica principal o perfil de vertical del planificador, se respeta.

!!! note "Nota"
    Las categorías, etiquetas y opciones de inventario son comunes a toda la
    base. Puede renombrarlas o archivarlas: al actualizar el módulo no se
    restauran.
