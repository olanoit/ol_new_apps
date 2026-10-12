/** Portal de obra: ubicación del celular en el registro de avance (v1.5, P-24). */
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#o_construction_progress_form, #o_construction_kiosk_form");
    if (!form || !navigator.geolocation) {
        return;
    }
    const status = form.querySelector(".o_construction_geo_status");
    navigator.geolocation.getCurrentPosition(
        (position) => {
            form.querySelector("input[name='latitude']").value = position.coords.latitude;
            form.querySelector("input[name='longitude']").value = position.coords.longitude;
            if (status) {
                status.textContent = status.dataset.ok;
            }
        },
        () => {
            if (status) {
                status.textContent = status.dataset.ko;
            }
        },
        { enableHighAccuracy: true, timeout: 15000 }
    );
});
