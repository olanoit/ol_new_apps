/**
 * Ancho real de la barra de scroll del navegador → `--alpt-scrollbar-w`.
 *
 * El resumen de beneficios Yapp (fuera del área con scroll del catálogo)
 * debe alinearse con las filas / tarjetas (dentro de esa área), cuyo borde
 * derecho queda corrido por la barra de scroll: 15px en Chrome de
 * escritorio con barras clásicas, 0 en tablets, teléfonos y macOS (barras
 * superpuestas). Se mide una vez al cargar el PdV en vez de fijar un número.
 */
function measureScrollbarWidth() {
    const probe = document.createElement("div");
    probe.style.cssText =
        "position:absolute;top:-9999px;width:100px;height:100px;overflow:scroll;";
    document.body.appendChild(probe);
    const width = probe.offsetWidth - probe.clientWidth;
    probe.remove();
    document.documentElement.style.setProperty("--alpt-scrollbar-w", `${width}px`);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", measureScrollbarWidth, { once: true });
} else {
    measureScrollbarWidth();
}
