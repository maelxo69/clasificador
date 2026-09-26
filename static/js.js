document.addEventListener("DOMContentLoaded", () => {
    // ================= 1. ELEMENTOS DE LA INTERFAZ =================
    const uiMaterial = document.getElementById("ui-material");
    const uiConfidence = document.getElementById("ui-confidence");
    const uiDestination = document.getElementById("ui-destination");
    const uiHistory = document.getElementById("ui-history");
    
    // Elementos de los botones de la banda
    const btnIniciar = document.getElementById('btn-iniciar');
    const btnDetener = document.getElementById('btn-detener');
    const estadoBandaTexto = document.getElementById('estado-banda');

    const destinos = {
        'HDPE': 'Contenedor Azul (Soplado / Envases Rígidos)',
        'LDPE': 'Contenedor Verde (Bolsas / Empaques Flexibles)',
        'PET':  'Contenedor Rojo (Botellas / Tereftalato)',
        'PVC':  'Contenedor Amarillo (Tuberías / Perfiles)'
    };

    let ultimoMaterial = "";

    // ================= 2. CONTROL DE LA BANDA TRANSPORTADORA =================
    
    if (btnIniciar) {
        btnIniciar.addEventListener('click', () => {
            fetch('/api/banda/iniciar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(res => res.json())
            .then(data => {
                console.log(data.mensaje);
                if (estadoBandaTexto) {
                    estadoBandaTexto.textContent = 'En movimiento';
                    estadoBandaTexto.className = 'badge bg-success'; // Ajusta la clase CSS si usas Bootstrap
                }
            })
            .catch(err => console.error('Error al iniciar la banda:', err));
        });
    }

    if (btnDetener) {
        btnDetener.addEventListener('click', () => {
            fetch('/api/banda/detener', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(res => res.json())
            .then(data => {
                console.log(data.mensaje);
                if (estadoBandaTexto) {
                    estadoBandaTexto.textContent = 'Detenida';
                    estadoBandaTexto.className = 'badge bg-danger'; // Ajusta la clase CSS si usas Bootstrap
                }
            })
            .catch(err => console.error('Error al detener la banda:', err));
        });
    }

    // ================= 3. LECTURA DE IA Y ACTUALIZACIÓN DEL DOM =================

    function consultarUltimaDeteccion() {
        fetch('/api/ultima_deteccion')
            .then(res => res.json())
            .then(data => {
                if (data.material && data.material !== "--") {
                    if (uiMaterial) uiMaterial.textContent = data.material;
                    if (uiConfidence) uiConfidence.textContent = `${data.confianza.toFixed(1)}%`;
                    
                    const destinoTexto = destinos[data.material] || 'Destino no asignado';
                    if (uiDestination) uiDestination.textContent = destinoTexto;

                    if (data.material !== ultimoMaterial) {
                        agregarAlHistorial(data.material, data.confianza);
                        ultimoMaterial = data.material;
                    }
                }
            })
            .catch(err => console.log("Esperando datos de la cámara..."));
    }

    function agregarAlHistorial(material, confianza) {
        if (!uiHistory) return;

        const emptyMsg = uiHistory.querySelector(".history-empty");
        if (emptyMsg) emptyMsg.remove();

        const hora = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        const li = document.createElement("li");
        li.style.cssText = "display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; font-size: 13px;";
        li.innerHTML = `
            <span><strong>${material}</strong> (${confianza.toFixed(1)}%)</span>
            <span style="color: #8b8e84; font-size: 11px;">${hora}</span>
        `;

        uiHistory.prepend(li);

        if (uiHistory.children.length > 5) {
            uiHistory.removeChild(uiHistory.lastChild);
        }
    }

    // Consulta la API cada 800 milisegundos
    setInterval(consultarUltimaDeteccion, 800);
});