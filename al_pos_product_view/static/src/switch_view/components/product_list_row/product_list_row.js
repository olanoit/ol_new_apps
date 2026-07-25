/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * Fila individual usada por la vista "lista" del catálogo de productos del TPV.
 *
 * La fila es clicable en su totalidad (añade el producto al pedido actual)
 * salvo el pequeño botón de información de la derecha, que abre el
 * `ProductInfoPopup` nativo vía `pos.onProductInfoClick(...)`.
 */
export class ProductListRow extends Component {
    static template = "al_pos_product_view.ProductListRow";
    static props = {
        product: Object,
        name: String,
        priceLabel: { type: String, optional: true },
        imageUrl: [String, Boolean],
        productCartQty: { type: [Number, undefined], optional: true },
        onClick: { type: Function, optional: true },
        onInfoClick: { type: Function, optional: true },
    };
    static defaultProps = {
        priceLabel: "",
        productCartQty: 0,
        onClick: () => {},
        onInfoClick: () => {},
    };

    get barcode() {
        return this.props.product?.barcode || "";
    }

    get sku() {
        return this.props.product?.default_code || "";
    }

    get uom() {
        return this.props.product?.uom_id?.name || "";
    }

    // Etiquetas a nivel de plantilla: `product_tag_ids` forma parte de la
    // carga estándar de product.template en el TPV.
    get productTags() {
        return this.props.product?.product_tag_ids || [];
    }

    // product.tag `color` es un HEX Char (p.ej. "#3C3C3C"), usado como punto
    // de color junto al nombre — misma convención que los chips del filtro.
    tagDotStyle(tag) {
        return `background-color: ${tag.color || "#3C3C3C"};`;
    }

    // Solo los productos almacenables tienen un `qty_available` con
    // significado; los servicios y consumibles no almacenables siempre
    // reportan 0, que sería engañoso mostrar como "sin stock".
    get showStock() {
        return !!this.props.product?.is_storable;
    }

    get stockQty() {
        return this.env.utils.formatProductQty(this.props.product?.qty_available ?? 0, false);
    }

    get outOfStock() {
        return this.showStock && (this.props.product?.qty_available ?? 0) <= 0;
    }

    // aria-labels / titles traducidos — se computan aquí para que el
    // extractor de i18n detecte `_t` (las cadenas interpoladas en atributos
    // `t-attf-` se evalúan como JS crudo y NO se extraerían).
    get addLabel() {
        return _t("Añadir %s al pedido", this.props.name);
    }

    get infoLabel() {
        return _t("Más información sobre %s", this.props.name);
    }

    onInfoClick(ev) {
        // Evita el handler de clic de la fila (que añadiría el producto al pedido).
        ev.stopPropagation();
        this.props.onInfoClick();
    }
}
