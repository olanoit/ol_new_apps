import { patch } from "@web/core/utils/patch";
import { ProductInfoPopup } from "@point_of_sale/app/components/popups/product_info_popup/product_info_popup";

patch(ProductInfoPopup.prototype, {
    /**
     * Cambia el producto de la ficha por el equivalente elegido: quita sus
     * líneas del pedido y agrega el equivalente con la misma cantidad en
     * unidades. Si el producto no estaba en el pedido, solo agrega el
     * equivalente. La receta y la presentación se piden como siempre.
     */
    async replaceWithPharmacyEquivalent(equivalent) {
        const template = this.pos.models["product.template"].get(equivalent.id);
        if (!template) {
            // No está cargado en la caja: se busca en el servidor.
            return this.searchProduct(equivalent.name);
        }
        const original = this.props.productTemplate;
        const order = this.pos.getOrder();
        this.props.close();
        const lines = (order?.lines || []).filter(
            (line) => line.product_id?.product_tmpl_id?.id === original.id
        );
        const qty = lines.reduce((sum, line) => sum + line.getQuantity(), 0);
        const newLine = await this.pos.addLineToCurrentOrder(
            { product_tmpl_id: template },
            { pharmacyAlternativeChosen: true }
        );
        if (!newLine) {
            return; // Cancelado (receta, presentación): el pedido queda como estaba.
        }
        for (const line of lines) {
            this.pos.getOrder().removeOrderline(line);
        }
        if (qty > 1 && !newLine.pharmacy_presentation_id) {
            // Se agregó 1 unidad (quizá sumada a una línea que ya estaba): se completa.
            newLine.setQuantity(newLine.getQuantity() - 1 + qty);
        }
        this.pos.getOrder().selectOrderline(newLine);
    },
});
