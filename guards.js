/* =====================================================================
   guards.js · Control de acceso de ClickSense RP
   1. Para entrar en cualquier página (salvo las públicas) hace falta tener
      la sesión de Discord iniciada. Sin sesión -> /login.html
   2. Si a la cuenta le faltan los datos del registro (Steam, nacionalidad
      y fecha de nacimiento) -> /login.html, que muestra el formulario.
   3. Sin whitelist aprobada (no enviada o suspendida) solo se ve el menú
      básico: Inicio, Servidor, Equipo, Calendario, Whitelist, Tienda,
      Mi perfil y Tickets. Con la whitelist aprobada se ve el resto.
   El estado real sale del servidor; el navegador solo guarda una copia
   para pintar el menú al instante.
   ===================================================================== */

// Páginas que se pueden abrir sin sesión
const GUARD_PUBLICAS = ['index.html', 'login.html', 'pol-privacidad.html', 'terminos.html'];

// Páginas que exigen la whitelist aprobada
const GUARD_RESTRINGIDAS = [
    'comercios.html',
    'mazebank.html',
    'postulaciones-ilegales.html',
    'postulaciones-playmaker.html',
    'postulaciones-staff.html',
    'lspd-academia.html',
    'lssd-academia.html',
    'codigo-penal.html',
    'organigrama.html',
    'defcon.html',
    'historias.html',
    'decretos.html',
    'comunicados-sajd.html',
    'sugerencias.html'
];

document.addEventListener('DOMContentLoaded', async () => {
    const currentPath = window.location.pathname;
    const pagina = (currentPath.split('/').pop() || 'index.html').toLowerCase();
    const esPublica = currentPath === '/' || currentPath === '' || GUARD_PUBLICAS.includes(pagina);

    let storedUser = {};
    try { storedUser = JSON.parse(localStorage.getItem('discord_user') || '{}') || {}; } catch (e) {}
    const userId = String(storedUser.id || '').trim();

    // Copia local del estado de la whitelist (solo para pintar el menú sin esperar al servidor)
    let isWhitelisted = localStorage.getItem('user_whitelisted') === 'true';

    // En las páginas públicas no se comprueba nada más
    if (esPublica) {
        guardPintarMenu(currentPath, isWhitelisted && !!userId);
        return;
    }

    // 1. Sesión de Discord obligatoria
    if (!userId) {
        window.location.replace('/login.html');
        return;
    }

    // 2. Sistema de baneo permanente (bloqueo global)
    try {
        const sancionesData = JSON.parse(localStorage.getItem('sanciones_data') || '[]');
        const activePermanentBan = sancionesData.find(s => {
            const isBanned = s.status && s.status.toLowerCase() === 'activa';
            const isPermanent = s.tipo && s.tipo.toLowerCase() === 'baneo permanente';
            const matchesUser = (
                (storedUser.id && s.discordId === storedUser.id) ||
                (storedUser.username && s.usuario && s.usuario.toLowerCase() === storedUser.username.toLowerCase())
            );
            return isBanned && isPermanent && matchesUser;
        });
        if (activePermanentBan) {
            renderBanScreen(activePermanentBan);
            return; // Detiene el resto para impedir el acceso
        }
    } catch (e) {
        console.error("Error comprobando baneo permanente:", e);
    }

    // 3. Menú al instante con lo que se sabe; después se confirma con el servidor
    const esRestringida = GUARD_RESTRINGIDAS.includes(pagina);
    guardPintarMenu(currentPath, isWhitelisted);

    // Página restringida sin whitelist en la copia local: se oculta hasta confirmar con el servidor
    const ocultar = esRestringida && !isWhitelisted;
    if (ocultar) document.documentElement.style.visibility = 'hidden';
    const mostrar = () => { document.documentElement.style.visibility = ''; };

    const [perfil, whitelist] = await Promise.all([
        guardFetch('/api/user-profile-data'),
        guardFetch('/api/whitelist')
    ]);

    // Sin sesión en el servidor: se limpia la sesión del navegador y se vuelve al login
    if (perfil.status === 401) {
        try {
            localStorage.removeItem('discord_user');
            localStorage.removeItem('user_whitelisted');
            localStorage.removeItem('whitelist_status');
        } catch (e) {}
        window.location.replace('/login.html');
        return;
    }

    // Registro sin terminar (faltan Steam, nacionalidad o fecha): login.html muestra el formulario
    if (perfil.ok && perfil.data && !(perfil.data.steam && perfil.data.country && perfil.data.birth)) {
        window.location.replace('/login.html');
        return;
    }

    // Estado real de la whitelist: aprobada si algún intento del usuario está "Aprobado"
    if (whitelist.ok && Array.isArray(whitelist.data)) {
        const aprobada = whitelist.data.some(i =>
            i && String(i.discordId || '') === userId && String(i.status || '').toLowerCase() === 'aprobado');
        try {
            if (aprobada) {
                localStorage.setItem('user_whitelisted', 'true');
                localStorage.setItem('whitelist_status', 'aprobado');
            } else {
                localStorage.removeItem('user_whitelisted');
                localStorage.removeItem('whitelist_status');
            }
            localStorage.removeItem('whitelist_data');   // restos de la versión antigua
        } catch (e) {}

        if (aprobada !== isWhitelisted) {
            isWhitelisted = aprobada;
            guardPintarMenu(currentPath, isWhitelisted);
        }
    }

    // Sin whitelist aprobada no se entra en las páginas restringidas
    if (esRestringida && !isWhitelisted) {
        window.location.replace('/whitelist.html');
        return;
    }
    mostrar();
});

// Petición al servidor que nunca lanza error: { ok, status, data }
async function guardFetch(url) {
    try {
        const r = await fetch(url, { cache: 'no-store', credentials: 'same-origin' });
        let data = null;
        try { data = await r.json(); } catch (e) {}
        return { ok: r.ok, status: r.status, data };
    } catch (e) {
        return { ok: false, status: 0, data: null };   // sin conexión: no se expulsa a nadie por un fallo de red
    }
}

// Menú lateral. Sin whitelist: solo Inicio, Servidor, Equipo, Calendario, Whitelist, Tienda, Mi perfil y Tickets.
function guardPintarMenu(currentPath, isWhitelisted) {
    const sidebarNav = document.querySelector('.sidebar-nav');
    if (!sidebarNav) return;

    const activo = pagina => currentPath.includes(pagina) ? 'active' : '';
    const item = (href, icono, texto) =>
        `<a href="/${href}" class="nav-item ${activo(href)}"><i class="fa-solid ${icono}"></i> <span>${texto}</span></a>`;

    let html = `
        <div class="nav-category">General</div>
        ${item('home.html', 'fa-house', 'Inicio')}
        ${item('servidor.html', 'fa-server', 'Servidor')}
        ${item('equipo.html', 'fa-users', 'Equipo')}
        ${item('calendario.html', 'fa-calendar-days', 'Calendario')}`;

    if (isWhitelisted) {
        html += `
        ${item('sugerencias.html', 'fa-lightbulb', 'Sugerencias')}
        ${item('comercios.html', 'fa-store', 'Comercios')}
        ${item('mazebank.html', 'fa-building-columns', 'Maze Bank Foreclosures')}`;
    } else {
        // El botón de Whitelist solo se ve mientras NO está aprobada
        html += `
        ${item('whitelist.html', 'fa-clipboard-list', 'Whitelist')}`;
    }

    html += `
        ${item('tienda.html', 'fa-cart-shopping', 'Tienda')}`;

    if (isWhitelisted) {
        html += `
        <div class="nav-category">Postulaciones</div>
        ${item('postulaciones-ilegales.html', 'fa-skull', 'Postulaciones ilegales')}
        ${item('postulaciones-playmaker.html', 'fa-trophy', 'Postulaciones playmaker')}
        ${item('postulaciones-staff.html', 'fa-user-gear', 'Postulaciones staff')}`;
    }

    html += `
        <div class="nav-category">Mi Cuenta</div>
        ${item('perfil.html', 'fa-user', 'Mi perfil')}
        ${item('tickets.html', 'fa-ticket', 'Tickets')}`;

    if (isWhitelisted) {
        html += `
        <div class="nav-category">SAJD</div>
        ${item('decretos.html', 'fa-file-lines', 'Decretos')}
        ${item('comunicados-sajd.html', 'fa-bullhorn', 'Comunicados')}

        <div class="nav-category">SASP</div>
        ${item('lspd-academia.html', 'fa-shield-halved', 'LSPD')}
        ${item('lssd-academia.html', 'fa-shield-halved', 'LSSD')}
        ${item('defcon.html', 'fa-triangle-exclamation', 'Defcon')}
        ${item('codigo-penal.html', 'fa-scale-balanced', 'Código penal')}
        ${item('organigrama.html', 'fa-sitemap', 'Organigrama')}`;
    }

    sidebarNav.innerHTML = html;
}

// Función auxiliar para renderizar la pantalla de bloqueo permanente
function renderBanScreen(banData) {
    document.body.innerHTML = '';
    document.body.style.backgroundColor = '#0c0812';
    document.body.style.margin = '0';
    document.body.style.fontFamily = "'Plus Jakarta Sans', 'Inter', sans-serif";
    document.documentElement.style.overflow = 'hidden';

    const banOverlay = document.createElement('div');
    banOverlay.style.cssText = `
        position: fixed;
        inset: 0;
        background: #0c0812;
        background-image: linear-gradient(to right, rgba(239, 68, 68, 0.03) 1px, transparent 1px),
                          linear-gradient(to bottom, rgba(239, 68, 68, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 999999;
        padding: 20px;
    `;

    banOverlay.innerHTML = `
        <div style="
            background: #130d1e;
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 18px;
            max-width: 540px;
            width: 100%;
            padding: 35px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8), 0 0 30px rgba(239, 68, 68, 0.15);
            text-align: center;
            position: relative;
            overflow: hidden;
        ">
            <div style="position: absolute; top: 0; left: 0; width: 100%; height: 4px; background: linear-gradient(90deg, #ef4444, #f43f5e);"></div>

            <div style="
                width: 70px;
                height: 70px;
                background: rgba(239, 68, 68, 0.15);
                border: 2px solid rgba(239, 68, 68, 0.4);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #ef4444;
                font-size: 28px;
                margin: 0 auto 20px auto;
                box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
            ">
                <i class="fa-solid fa-user-lock"></i>
            </div>

            <h1 style="color: #fff; font-size: 22px; font-weight: 800; margin-bottom: 10px; letter-spacing: 0.5px;">
                Acceso denegado: Usuario Sancionado
            </h1>

            <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
                Has sido <strong style="color: #ef4444;">baneado permanentemente</strong> del servidor ClickSense RP. 
                Si consideras que se trata de un error, puedes proceder a apelar la sanción a través de nuestros canales oficiales de soporte.
            </p>

            <div style="display: flex; gap: 10px;">
                <a href="/index.html" style="
                    flex: 1;
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    color: #fff;
                    text-decoration: none;
                    padding: 12px;
                    border-radius: 8px;
                    font-size: 13.5px;
                    font-weight: 600;
                    display: inline-block;
                ">
                    Ir al Inicio (Index)
                </a>
            </div>
        </div>
    `;

    document.body.appendChild(banOverlay);
}