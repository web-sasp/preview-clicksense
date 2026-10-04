import { renderHome } from './views/home.js';
import { renderWhitelist } from './views/whitelist.js';
import { renderMDT } from './views/mdt.js';
import { renderFacciones } from './views/facciones.js';
import { renderTienda } from './views/tienda.js';

const routes = {
  '/dashboard': renderHome,
  '/whitelist': renderWhitelist,
  '/mdt': renderMDT,
  '/facciones': renderFacciones,
  '/tienda': renderTienda
};

// Rutas o archivos que requieren Whitelist obligatoria para poder verlos
const restrictedPaths = [
  'comercios.html',
  'postulaciones-ilegales.html',
  'grupos.html',
  'documentos.html',
  'lspd-academia.html',
  'lssd-academia.html'
];

function checkRouteGuard(path) {
  const isWhitelisted = localStorage.getItem('user_whitelisted') === 'true';
  const isRestricted = restrictedPaths.some(restricted => path.includes(restricted));
  
  if (isRestricted && !isWhitelisted) {
    alert('Acceso restringido: Debes tener la Whitelist autorizada para entrar en este apartado.');
    return false;
  }
  return true;
}

function router() {
  const path = window.location.pathname;
  const appElement = document.getElementById('app');

  // Validar si la ruta requiere permisos antes de renderizar
  if (!checkRouteGuard(path)) {
    window.location.href = '/home.html';
    return;
  }

  if (path === '/' || path === '') {
    if (appElement) appElement.innerHTML = '';
    return;
  }

  const render = routes[path] || renderHome;
  if (appElement) {
    appElement.innerHTML = render();
  }
}

window.addEventListener('popstate', router);

document.addEventListener('click', (e) => {
  const target = e.target.closest('[data-link]');
  if (target) {
    e.preventDefault();
    const href = target.getAttribute('href');

    // Comprobar permisos antes de permitir la navegación por SPA
    if (!checkRouteGuard(href)) {
      return;
    }

    history.pushState(null, '', href);
    router();
  }
});

window.addEventListener('DOMContentLoaded', () => {
  // Comprobar permisos al cargar la URL directamente en el navegador
  if (!checkRouteGuard(window.location.pathname)) {
    window.location.href = '/home.html';
    return;
  }
  router();
});