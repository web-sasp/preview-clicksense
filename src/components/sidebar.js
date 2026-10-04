export function renderSidebar(activeRoute = 'home') {
  // 1. Intentar obtener el usuario real logueado desde localStorage
  let discordUser = {
    displayName: "Invitado",
    username: "inicia_sesion",
    avatarUrl: ""
  };

  if (typeof window !== 'undefined') {
    const storedUser = localStorage.getItem('discord_user');
    if (storedUser) {
      try {
        discordUser = JSON.parse(storedUser);
      } catch (e) {
        console.error("Error al leer los datos del usuario:", e);
      }
    }
  }

  // 2. Verificar estado de Whitelist (Por defecto falso / Sin Whitelist)
  let isWhitelisted = false;
  if (typeof window !== 'undefined') {
    const whitelistStatus = localStorage.getItem('user_whitelisted');
    if (whitelistStatus === 'true' || (discordUser && discordUser.whitelisted)) {
      isWhitelisted = true;
    }
  }

  // 3. Definir cómo se verá el avatar
  const avatarContent = discordUser.avatarUrl 
    ? `<img src="${discordUser.avatarUrl}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%; pointer-events: none;">`
    : `CS`;

  // 4. Inicializador global de eventos para el botón de perfil y cierre de sesión
  if (typeof window !== 'undefined' && !window.__sidebarInitialized) {
    window.__sidebarInitialized = true;

    document.addEventListener('click', (e) => {
      const profileBtn = e.target.closest('#userProfileBtn');
      const logoutBtn = e.target.closest('#logoutBtn');

      if (profileBtn) {
        window.location.href = '/perfil.html';
        return;
      }

      if (logoutBtn) {
        localStorage.removeItem('discord_user');
        localStorage.removeItem('user_whitelisted');
        window.location.href = '/index.html';
        return;
      }
    });
  }

  // Función auxiliar para renderizar los ítems del menú con sus estilos activos
  const renderNavItem = (route, href, label, icon) => {
    const isActive = activeRoute === route;
    return `
      <li>
        <a href="${href}" data-link style="display: flex; align-items: center; gap: 12px; color: ${isActive ? '#f472b6' : '#d8b4fe'}; text-decoration: none; padding: 10px 14px; border-radius: 10px; font-size: 14px; font-weight: 500; background: ${isActive ? 'rgba(147, 51, 234, 0.2)' : 'transparent'}; border: 1px solid ${isActive ? 'rgba(244, 114, 182, 0.3)' : 'transparent'};">
          ${icon} ${label}
        </a>
      </li>
    `;
  };

  // 5. Construcción dinámica de los enlaces según el estado de Whitelist
  let navLinksHTML = `
    ${renderNavItem('home', '/home.html', 'Home', '🏠')}
    ${renderNavItem('equipo', '/equipo.html', 'Equipo', '👥')}
    ${renderNavItem('calendario', '/calendario.html', 'Calendario', '📅')}
    ${renderNavItem('whitelist', '/whitelist.html', 'Whitelist', '📋')}
    ${renderNavItem('tickets', '/tickets.html', 'Tickets', '🎫')}
  `;

  // Si el usuario cuenta con Whitelist autorizada, se añaden el resto de apartados
  if (isWhitelisted) {
    navLinksHTML += `
      ${renderNavItem('comercios', '/comercios.html', 'Comercios', '🏪')}
      ${renderNavItem('postulaciones', '/postulaciones-ilegales.html', 'Postulaciones ilegales', '💀')}
    `;
  }

  // 6. Estructura HTML final de la barra lateral
  return `
    <style>
      .sidebar-user-btn {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        padding: 10px;
        border-top: 1px solid #3b2354;
        border-radius: 10px;
        background: rgba(55, 35, 84, 0.2);
        border-left: none;
        border-right: none;
        border-bottom: none;
        cursor: pointer !important;
        transition: background 0.2s ease;
        text-align: left;
      }
      .sidebar-user-btn:hover {
        background: rgba(147, 51, 234, 0.4);
      }
      .sidebar-user-btn * {
        cursor: pointer !important;
      }
    </style>

    <aside style="width: 260px; background-color: #130b1c; border-right: 1px solid #3b2354; display: flex; flex-direction: column; justify-content: space-between; padding: 25px 20px; height: 100vh; position: fixed; top: 0; left: 0; z-index: 1000; box-sizing: border-box;">
      <div>
        <div style="font-size: 20px; font-weight: 800; background: linear-gradient(135deg, #f472b6 0%, #e879f9 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 40px; letter-spacing: -0.5px;">
          ClickSense
        </div>
        <ul style="list-style: none; display: flex; flex-direction: column; gap: 6px; padding: 0; margin: 0;">
          ${navLinksHTML}
        </ul>
      </div>

      <!-- Contenedor Inferior: Botón nativo interactivo para ir a perfil.html -->
      <div>
        <button id="userProfileBtn" class="sidebar-user-btn" type="button">
          <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
            <div style="width: 38px; height: 38px; border-radius: 50%; background: linear-gradient(135deg, #c084fc, #f472b6); display: flex; align-items: center; justify-content: center; font-weight: bold; color: #0b0710; overflow: hidden; flex-shrink: 0;">
              ${avatarContent}
            </div>
            <div style="overflow: hidden;">
              <div style="font-weight: bold; font-size: 12px; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${discordUser.displayName}</div>
              <div style="font-size: 10px; color: #a855f7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">@${discordUser.username}</div>
            </div>
          </div>
          <div style="color: #d8b4fe; font-size: 12px; padding-left: 4px; flex-shrink: 0;">
            ⚙️
          </div>
        </button>
      </div>
    </aside>
  `;
}