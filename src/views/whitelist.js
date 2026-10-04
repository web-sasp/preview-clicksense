import { renderSidebar } from '../components/Sidebar.js';

export function renderWhitelist() {
  const isWhitelisted = localStorage.getItem('user_whitelisted') === 'true';

  return `
    <div style="display: flex; height: 100vh; overflow: hidden; width: 100vw; background: radial-gradient(circle at top right, #180d28 0%, #0b0710 60%);">
      ${renderSidebar('whitelist')}
      <main style="margin-left: 260px; flex-grow: 1; height: 100vh; overflow-y: auto; padding: 40px; color: #f3e8ff;">
        <h1 style="font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 30px;">Gestión de Whitelist</h1>
        <div style="background-color: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 30px; max-width: 700px;">
          <h3 style="color: #e879f9; font-size: 18px; margin-bottom: 15px;">Estado de tu Solicitud</h3>
          <p style="color: #d8b4fe; margin-bottom: 20px;">Tu cuenta está vinculada correctamente con Discord. El acceso al servidor de rol serio requiere completar el cuestionario técnico.</p>
          
          <div style="background: rgba(232, 121, 249, 0.1); border: 1px solid #e879f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; color: #fbcfe8;">
            ✔ Cuestionario Teórico: <strong>Aprobado</strong><br>
            ${isWhitelisted 
              ? '🎉 Estado Global: <strong style="color: #22c55e;">WHITELIST APROBADA</strong> (Tienes acceso completo al servidor y apartados)' 
              : '⏳ Entrevista Oral / Estado: <strong style="color: #f59e0b;">Pendiente de autorización por administración</strong>'}
          </div>

          ${isWhitelisted 
            ? '<div style="background: rgba(34, 197, 94, 0.1); border: 1px solid #22c55e; padding: 15px; border-radius: 8px; color: #86efac; font-weight: 500;">¡Enhorabuena! Ya puedes acceder a Comercios, Postulaciones Ilegales y el resto de secciones desde el menú lateral.</div>' 
            : '<button style="background: linear-gradient(135deg, #9333ea 0%, #f472b6 100%); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer;">Ver Horarios de Entrevista</button>'}
        </div>
      </main>
    </div>
  `;
}