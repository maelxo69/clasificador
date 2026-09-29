// static/menu.js  →  menú lateral (hamburguesa) para celular
// Crea solo el botón y el fondo oscuro: no hace falta tocar el HTML del navbar.
document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector(".navbar");
    const nav = header && header.querySelector("nav");
    if (!nav) return;

    nav.id = "menu-nav";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "menu-toggle";
    btn.setAttribute("aria-controls", "menu-nav");
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-label", "Abrir menú");
    btn.innerHTML = "<span></span><span></span><span></span>";

    const fondo = document.createElement("div");
    fondo.className = "nav-backdrop";

    header.append(fondo, btn);

    const abrir = (estado) => {
        document.body.classList.toggle("nav-open", estado);
        btn.setAttribute("aria-expanded", String(estado));
        btn.setAttribute("aria-label", estado ? "Cerrar menú" : "Abrir menú");
    };

    btn.addEventListener("click", () => abrir(!document.body.classList.contains("nav-open")));
    fondo.addEventListener("click", () => abrir(false));
    nav.querySelectorAll("a").forEach(a => a.addEventListener("click", () => abrir(false)));
    document.addEventListener("keydown", e => { if (e.key === "Escape") abrir(false); });
    window.matchMedia("(min-width: 901px)").addEventListener("change", e => { if (e.matches) abrir(false); });

    // Menú de usuario: en pantallas táctiles no existe "hover", así que se abre con toque
    const usuario = header.querySelector(".user-dropdown");
    if (usuario) {
        usuario.addEventListener("click", e => {
            if (e.target.closest(".dropdown-menu a")) return;
            usuario.classList.toggle("open");
        });
        document.addEventListener("click", e => {
            if (!usuario.contains(e.target)) usuario.classList.remove("open");
        });
    }
});