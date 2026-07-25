/** @odoo-module **/

import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";

// Selectores de los elementos introducidos por al_pos_product_view.
const SwitchBtn = ".pos-view-switch__btn";
const ListRow = ".pos-product-list-row";
const ListRowName = `${ListRow} .pos-product-list-row__name`;
const InfoBtn = `${ListRow} .pos-product-list-row__info-btn`;
const GridCard = ".product-list article.product";

registry.category("web_tour.tours").add("al_pos_product_view_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            // Sin texto: la base puede correr en cualquier idioma («Abrir
            // caja» en es_419) y Dialog.confirm("Open Register") no lo
            // encontraría.
            Dialog.confirm(),

            // ----- Estado por defecto: vista de cuadrícula -----
            {
                content: "La vista por defecto es la cuadrícula",
                trigger: `${GridCard}:eq(0)`,
            },
            {
                content: "El contenedor del modo lista NO está presente aún",
                trigger: "body:not(:has(.product-list--rows))",
            },

            // ----- Cambio a vista de lista -----
            {
                content: "Clic en el botón conmutador de vista",
                trigger: SwitchBtn,
                run: "click",
            },
            {
                content: "La vista de lista está renderizada (contenedor de filas)",
                trigger: ".product-list--rows",
            },
            {
                content: "Al menos una fila de la lista es visible",
                trigger: `${ListRow}:eq(0)`,
            },
            {
                content: "Las tarjetas de la cuadrícula desaparecieron",
                trigger: "body:not(:has(.product-list .product-content))",
            },

            // ----- El botón de información abre el ProductInfoPopup nativo -----
            {
                content: "Clic en el botón de información de la primera fila",
                trigger: `${InfoBtn}:eq(0)`,
                run: "click",
            },
            {
                content: "El ProductInfoPopup está abierto (el modal tiene título de sección)",
                trigger: ".modal:not(.o_inactive_modal) .section-title",
            },
            {
                content: "Cerrar el popup",
                trigger: ".modal:not(.o_inactive_modal) .btn-close",
                run: "click",
            },
            {
                content: "El modal desapareció, la vista de lista sigue activa",
                trigger: ".product-list--rows:not(:has(.modal))",
            },

            // ----- Clic en una fila añade el producto al pedido -----
            {
                content: "Lee el nombre de producto de la primera fila en un slot compartido",
                trigger: `${ListRowName}:eq(0)`,
                run: function () {
                    // Guarda el nombre en un data-attr para que el siguiente paso lo lea.
                    const el = document.querySelector(ListRowName);
                    document.body.setAttribute(
                        "data-test-row-product",
                        el ? el.textContent.trim() : ""
                    );
                },
            },
            {
                content: "Clic en la primera fila de la lista",
                trigger: `${ListRow}:eq(0)`,
                run: "click",
            },
            {
                content: "El producto clicado aparece en el resumen del pedido",
                trigger: ".order-container .orderline .product-name",
            },

            // ----- Vuelta a la vista de cuadrícula -----
            {
                content: "Clic de nuevo en el botón conmutador de vista",
                trigger: SwitchBtn,
                run: "click",
            },
            {
                content: "La cuadrícula está de vuelta",
                trigger: `${GridCard}:eq(0)`,
            },
            {
                content: "El contenedor del modo lista desapareció de nuevo",
                trigger: "body:not(:has(.product-list--rows))",
            },
        ].flat(),
});
