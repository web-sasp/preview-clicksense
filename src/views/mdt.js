import { renderSidebar } from '../components/Sidebar.js';

export function renderMDT() {
  return `
    <div style="display: flex; height: 100vh; overflow: hidden;">
      ${renderSidebar('mdt')}
      <main style="flex-grow: 1; overflow-y: auto; padding: 40px; background: radial-gradient(circle at top right, #180d28 0%, #0b0710 60%); color: #f3e8ff;">
        <h1 style="font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 30px;">MDT / CAD Policial (Terminal Interna)</h1>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px;">
          <div style="background: #1c112a; border: 1px solid #3b2354; padding: 20px; border-radius: 12px;"><h4 style="color: #f472b6; margin-bottom: 8px;">Órdenes Activas</h4><p style="font-size: 24px; font-weight: bold; color: #fff; margin: 0;">14</p></div>
          <div style="background: #1c112a; border: 1px solid #3b2354; padding: 20px; border-radius: 12px;"><h4 style="color: #f472b6; margin-bottom: 8px;">Unidades en Patrulla</h4><p style="font-size: 24px; font-weight: bold; color: #fff; margin: 0;">8</p></div>
          <div style="background: #1c112a; border: 1px solid #3b2354; padding: 20px; border-radius: 12px;"><h4 style="color: #f472b6; margin-bottom: 8px;">Incidentes 24h</h4><p style="font-size: 24px; font-weight: bold; color: #fff; margin: 0;">32</p></div>
        </div>
        <div style="background-color: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 25px;">
          <h3 style="color: #e879f9; margin-bottom: 15px;">Búsqueda de Ciudadanos y Vehículos</h3>
          <input type="text" placeholder="Introduce nombre o DNI..." style="width: 100%; background: #130b1c; border: 1px solid #3b2354; padding: 12px; border-radius: 8px; color: #fff; font-size: 14px; outline: none;" />
        </div>
      </main>
    </div>
  `;
}