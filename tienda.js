import { renderSidebar } from '../components/Sidebar.js';

export function renderTienda() {
  return `
    <div style="display: flex; height: 100vh; overflow: hidden;">
      ${renderSidebar('tienda')}
      <main style="flex-grow: 1; overflow-y: auto; padding: 40px; background: radial-gradient(circle at top right, #180d28 0%, #0b0710 60%); color: #f3e8ff;">
        <h1 style="font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 30px;">Tienda VIP y Beneficios</h1>
        <div style="background: #1c112a; border: 1px solid #3b2354; border-radius: 16px; padding: 25px; max-width: 600px;">
          <h3 style="color: #e879f9; margin-bottom: 10px;">Rango VIP Clicksenserp</h3>
          <p style="color: #d8b4fe; font-size: 14.5px; margin-bottom: 20px;">Incluye prioridad alta en cola de acceso, PEDs personalizados exclusivos, acceso anticipado a propiedades MLO rurales y soporte prioritario.</p>
          <button style="background: linear-gradient(135deg, #9333ea 0%, #f472b6 100%); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer;">Adquirir Suscripción</button>
        </div>
      </main>
    </div>
  `;
}