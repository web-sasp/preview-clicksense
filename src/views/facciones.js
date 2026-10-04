import { renderSidebar } from '../components/Sidebar.js';

export function renderFacciones() {
  return `
    <div style="display: flex; height: 100vh; overflow: hidden;">
      ${renderSidebar('facciones')}
      <main style="flex-grow: 1; overflow-y: auto; padding: 40px; background: radial-gradient(circle at top right, #180d28 0%, #0b0710 60%); color: #f3e8ff;">
        <h1 style="font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 30px;">Directorio de Facciones</h1>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
          <div style="background: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 25px;"><h3 style="color: #e879f9; margin-bottom: 10px;">LSPD (Policía Metropolitana)</h3><p style="color: #d8b4fe; font-size: 14px; margin-bottom: 15px;">Cuerpo encargado de la seguridad ciudadana y el orden público en Los Santos.</p><button style="background: transparent; border: 1px solid #f472b6; color: #f472b6; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold;">Ver Requisitos</button></div>
          <div style="background: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 25px;"><h3 style="color: #e879f9; margin-bottom: 10px;">SAED (Servicios Médicos)</h3><p style="color: #d8b4fe; font-size: 14px; margin-bottom: 15px;">Equipo de urgencias médicas y paramédicos profesionales del condado.</p><button style="background: transparent; border: 1px solid #f472b6; color: #f472b6; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold;">Ver Requisitos</button></div>
        </div>
      </main>
    </div>
  `;
}