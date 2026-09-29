// static/dashboard.js
document.addEventListener("DOMContentLoaded", () => {
    const $ = id => document.getElementById(id);
    if (!$("chart-general")) return;
    if (typeof Chart === "undefined") {
        console.error("Chart.js no cargó: revisa la conexión o el <script> del CDN.");
        document.querySelectorAll(".chart-box").forEach(b => (b.innerHTML = '<p class="chart-error">No se pudo cargar Chart.js</p>'));
        return;
    }

    // Mismos colores de contenedor que usa la detección
    const COLOR = { HDPE: "#2b6cb0", LDPE: "#3aab5f", PET: "#c81d34", PVC: "#f2a900" };
    const MATERIALES = Object.keys(COLOR);
    const ETIQUETAS = Array.from({ length: 10 }, (_, i) => (i === 9 ? "ahora" : `-${9 - i}m`));
    const ceros = () => Array(10).fill(0);

    Chart.defaults.font.family = "'Manrope', Arial, sans-serif";

    // ===== Gráfico general (4 materiales) =====
    const general = new Chart($("chart-general"), {
        type: "doughnut",
        data: {
            labels: MATERIALES,
            datasets: [{ data: [0, 0, 0, 0], backgroundColor: MATERIALES.map(m => COLOR[m]), borderColor: "#fffdf8", borderWidth: 3 }]
        },
        options: { maintainAspectRatio: false, cutout: "62%", plugins: { legend: { position: "bottom" } } }
    });

    // ===== Flujo en el tiempo (apilado) =====
    const tiempo = new Chart($("chart-tiempo"), {
        type: "bar",
        data: { labels: ETIQUETAS, datasets: MATERIALES.map(m => ({ label: m, data: ceros(), backgroundColor: COLOR[m] })) },
        options: {
            maintainAspectRatio: false,
            scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } },
            plugins: { legend: { position: "bottom" } }
        }
    });

    // ===== Un gráfico por material =====
    const minis = {};
    MATERIALES.forEach(m => {
        minis[m] = new Chart($("chart-" + m), {
            type: "line",
            data: { labels: ETIQUETAS, datasets: [{ data: ceros(), borderColor: COLOR[m], backgroundColor: COLOR[m] + "33", fill: true, tension: 0.35, pointRadius: 2 }] },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
            }
        });
    });

    // ===== Actualización desde la API =====
    async function actualizar() {
        try {
            const res = await fetch("/api/estadisticas");
            const d = await res.json();

            const vacio = d.total === 0;   // sin datos: anillo gris de referencia
            general.data.datasets[0].data = vacio ? [1, 0, 0, 0] : MATERIALES.map(m => d.totales[m]);
            general.data.datasets[0].backgroundColor = vacio ? ["#e4ddcd", "#e4ddcd", "#e4ddcd", "#e4ddcd"] : MATERIALES.map(m => COLOR[m]);
            general.options.plugins.tooltip.enabled = !vacio;
            general.update();

            tiempo.data.datasets.forEach((ds, i) => (ds.data = d.serie[MATERIALES[i]]));
            tiempo.update();

            MATERIALES.forEach(m => {
                minis[m].data.datasets[0].data = d.serie[m];
                minis[m].update();
                $("tot-" + m).textContent = d.totales[m];
            });

            $("kpi-total").textContent = d.total;
            $("kpi-minuto").textContent = d.por_minuto;
            $("kpi-conf").textContent = d.confianza_prom.toFixed(1) + "%";
            const top = MATERIALES.reduce((a, b) => (d.totales[b] > d.totales[a] ? b : a));
            $("kpi-top").textContent = d.total ? top : "--";
        } catch (e) {
            console.log("Esperando datos del servidor...");
        }
    }

    // ===== Reiniciar conteo =====
    const btnReiniciar = $("btn-reiniciar");
    if (btnReiniciar) {
        btnReiniciar.addEventListener("click", async () => {
            if (!confirm("¿Reiniciar el conteo de la banda?")) return;
            await fetch("/api/estadisticas/reiniciar", { method: "POST" });
            actualizar();
        });
    }

    actualizar();
    setInterval(actualizar, 1500);
});