// Lógica principal del panel de administración y control de acceso visual
document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('adminContentContainer');
    const welcomeBanner = document.getElementById('welcomeBannerCard');
    const breadcrumb = document.querySelector('.breadcrumb'); // Seleccionamos la barra de migas/título superior
    
    if (!container) return;

    // Cambiar el texto de la cabecera superior por "Panel de administración"
    if (breadcrumb) {
        breadcrumb.textContent = "Panel de administración";
    }

    // Comprobamos permisos mediante la función checkUserPermissions()
    const hasAccess = typeof checkUserPermissions === 'function' ? await checkUserPermissions() : false;

    if (!hasAccess) {
        if (welcomeBanner) {
            welcomeBanner.style.display = 'none';
        }

        // Pantalla completa de acceso denegado
        container.innerHTML = `
            <div class="access-denied-fullscreen">
                <div class="denied-card-content">
                    <div class="denied-icon-box">
                        <i class="fa-solid fa-ban"></i>
                    </div>
                    <h2>Acceso Denegado</h2>
                    <p>No tienes los roles necesarios en el servidor de pruebas de Discord para visualizar este panel.</p>
                    <a href="/home.html" class="top-btn denied-back-btn">
                        <i class="fa-solid fa-arrow-left"></i> Volver a la Web
                    </a>
                </div>
            </div>
        `;
        return;
    }

    // Si tiene acceso autorizado, mostramos el panel con las tarjetas enlazadas a sus respectivas rutas
    container.innerHTML = `
        <div class="admin-dashboard-grid">
            
            <!-- Tarjeta: Gestionar STAFF -->
            <div class="dashboard-card" onclick="window.location.href='/admin/staff.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-users-gear"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar STAFF</h4>
                    <p>Administra los permisos, rangos y accesos del equipo de staff.</p>
                </div>
            </div>

            <!-- Tarjeta: Gestionar Calendario -->
            <div class="dashboard-card" onclick="window.location.href='/admin/calendario.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-calendar-check"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar calendario</h4>
                    <p>Organiza los eventos, reuniones y fechas clave del servidor.</p>
                </div>
            </div>

            <!-- Tarjeta 1: Comercios -->
            <div class="dashboard-card" onclick="window.location.href='/admin/comercios.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-store"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar comercios</h4>
                    <p>Regulación de negocios, tiendas y licencias comerciales.</p>
                </div>
            </div>

            <!-- Tarjeta 2: Organizaciones Ilegales -->
            <div class="dashboard-card" onclick="window.location.href='/admin/organizaciones-ilegal.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-skull-crossbones"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar organizaciones ilegales</h4>
                    <p>Normas, bandas, mafias y control de territorios.</p>
                </div>
            </div>

            <!-- Tarjeta 3: WhiteList -->
            <div class="dashboard-card" onclick="window.location.href='/admin/whitelist.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-id-card-clip"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar WhiteList</h4>
                    <p>Revisiones, entrevistas y accesos iniciales al servidor.</p>
                </div>
            </div>

            <!-- Tarjeta 4: Sanciones -->
            <div class="dashboard-card" onclick="window.location.href='/admin/sanciones.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-gavel"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar sanciones</h4>
                    <p>Historial de baneos, advertencias y reportes activos.</p>
                </div>
            </div>

            <!-- Tarjeta 5: Facciones Legales -->
            <div class="dashboard-card" onclick="window.location.href='/admin/facciones-legales.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-shield-halved"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar facciones legales</h4>
                    <p>Control de cuerpos policiales, EMS y gobierno.</p>
                </div>
            </div>

            <!-- Tarjeta 6: Creadores -->
            <div class="dashboard-card" onclick="window.location.href='/admin/creadores.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-video"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar creadores</h4>
                    <p>Streamers, content creators y alianzas de difusión.</p>
                </div>
            </div>

            <!-- Tarjeta 7: Playmakers -->
            <div class="dashboard-card" onclick="window.location.href='/admin/playmakers.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-masks-theater"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar playmakers</h4>
                    <p>Coordinación de eventos especiales y tramas de rol.</p>
                </div>
            </div>

            <!-- Tarjeta 8: Donaciones -->
            <div class="dashboard-card" onclick="window.location.href='/admin/donaciones.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-gem"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar donaciones</h4>
                    <p>Ventajas VIP, vehículos exclusivos y transacciones.</p>
                </div>
            </div>

            <!-- Tarjeta 9: CK -->
            <div class="dashboard-card" onclick="window.location.href='/admin/ck.html'">
                <div class="card-media-banner">
                    <i class="fa-solid fa-user-slash"></i>
                </div>
                <div class="card-info-content">
                    <h4>Gestionar CK</h4>
                    <p>Autorizaciones de muertes definitivas de personajes.</p>
                </div>
            </div>

        </div>
    `;
});