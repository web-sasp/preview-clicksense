import { renderSidebar } from '../components/Sidebar.js';

export function renderHome() {
  return `
    <div style="display: flex; height: 100vh; overflow: hidden; width: 100vw; background: radial-gradient(circle at top right, #180d28 0%, #0b0710 60%);">
      ${renderSidebar('dashboard')}
      <main style="margin-left: 260px; flex-grow: 1; height: 100vh; overflow-y: auto; padding: 40px; color: #f3e8ff;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
          <h1 style="font-size: 26px; font-weight: 800; color: #fff; margin:0;">Dashboard Principal</h1>
          <div style="background: rgba(244, 114, 182, 0.15); color: #f472b6; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; border: 1px solid rgba(244, 114, 182, 0.4);">SERVIDOR ACTIVO • 112 / 128</div>
        </div>
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 25px;">
          <div>
            <div style="background-color: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 25px; margin-bottom: 25px;">
              <h3 style="color: #e879f9; font-size: 18px; margin-bottom: 12px;">Bienvenido a Clicksenserp</h3>
              <p style="color: #d8b4fe; font-size: 14.5px; line-height: 1.5; margin-bottom: 20px;">Tu plataforma centralizada de rol serio en FiveM. Administra tus expedientes, revisa el estado de tu whitelist y mantente al tanto de las novedades de la ciudad.</p>
              <a href="/whitelist" data-link style="background: linear-gradient(135deg, #9333ea 0%, #f472b6 100%); color: #fff; font-weight: 700; border: none; padding: 10px 20px; border-radius: 8px; text-decoration: none; display: inline-block;">Ver Whitelist</a>
            </div>
          </div>
          <div>
            <div style="background-color: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 25px; text-align: center;">
              <h3 style="color: #e879f9; font-size: 18px; margin-bottom: 12px;">Conexión Rápida</h3>
              <p style="font-size: 13px; color: #d8b4fe; margin-bottom: 15px;">Entra directamente al servidor o accede al canal oficial de Discord.</p>
              <button style="width: 100%; background: linear-gradient(135deg, #9333ea 0%, #f472b6 100%); color: #fff; border: none; padding: 10px; border-radius: 8px; font-weight: bold; cursor: pointer; margin-bottom: 10px;">Conectar a FiveM</button>
              <button style="width: 100%; background: transparent; border: 1px solid #7c3aed; color: #fbcfe8; padding: 10px; border-radius: 8px; font-weight: bold; cursor: pointer;">Discord</button>
            </div>
          </div>
        </div>
      </main>
    </div>
  `;
}