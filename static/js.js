<!-- ================= SCRIPT DEL MENÚ DESPLEGABLE ================= -->
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const botonPerfil = document.querySelector('.user-trigger');
            const menuDesplegable = document.querySelector('.dropdown-menu');

            if (botonPerfil && menuDesplegable) {
                // Abre o cierra el menú al tocar la bolita
                botonPerfil.addEventListener('click', function(evento) {
                    evento.stopPropagation(); // Evita que el clic se propague
                    menuDesplegable.classList.toggle('mostrar');
                });

                // Cierra el menú automáticamente si tocas cualquier otra parte de la pantalla
                document.addEventListener('click', function(evento) {
                    if (!botonPerfil.contains(evento.target) && !menuDesplegable.contains(evento.target)) {
                        menuDesplegable.classList.remove('mostrar');
                    }
                });
            }
        });
    </script>
</body>
</html>