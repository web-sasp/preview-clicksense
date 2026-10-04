// Configuración de Permisos y Validación con el Servidor de Pruebas de Discord (ClickSense RP)
const TEST_GUILD_ID = "845710322950209587";

// ID de Super Administrador absoluto (Acceso directo por ID de usuario solicitado)
const ABSOLUTE_SUPER_ADMIN_ID = "732650490588037160";

// Mapeo de IDs de Roles de Staff y Rangos del servidor
const STAFF_ROLES = {
    OWNER: "1541455303122485461",
    GAME_MASTER: "1541455305844588585",
    ADMINISTRADOR: "1541455306876256287",
    MODERADOR: "1541455307405008927",
    SOPORTE: "1541455308885463131",

    // Encargados de Áreas
    ENCARGADO_CK: "1541455309632176128",
    ENCARGADO_WL: "1541455425512415384",
    ENCARGADO_LOCALES: "1541455424631603261",
    ENCARGADO_FACC_LEGAL: "1541455425935904959",
    ENCARGADO_FACC_ILEGAL: "1541455604986675280",
    ENCARGADO_CREADORES: "1541455607893196800",
    ENCARGADO_PLAYMAKERS: "1541455310126977145",
    ENCARGADO_DONACIONES: "1541455423725633579",

    // Rol general que agrupa a todos los miembros del staff
    GENERAL_STAFF: "1541456197381656657"
};

/**
 * ------------------------------------------------------------------
 * Capa de datos: /api/staff
 * Es la misma fuente que usa admin/staff.html para leer y guardar
 * (discordId, rango, especialidad, status). Aquí la consultamos para
 * saber si el usuario está Activo/Inactivo y qué especialidad tiene,
 * algo que los roles de Discord por sí solos no nos dicen.
 * ------------------------------------------------------------------
 */
async function getStaffList() {
    try {
        const res = await fetch('/api/staff');
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
    } catch (e) {
        console.error("Error al obtener /api/staff:", e);
        return [];
    }
}

function findMyStaffRecord(staffList, discordUser) {
    if (!discordUser) return null;
    const myId = String(discordUser.id || '').trim();
    if (!myId) return null;
    return staffList.find(s => String(s.discordId || '').trim() === myId) || null;
}

/**
 * Función para comprobar si el usuario actual tiene permisos para ver el panel de administración.
 *
 * @param {string|string[]|null} requiredSpecialty - especialidad(es) del campo "especialidad"
 *   de admin/staff.html necesarias para este panel en concreto
 *   (ej: "Encargado de CK's", "Encargado de la facción legal"...).
 *   Si se omite o es null, basta con ser staff Activo (panel de acceso general).
 */
async function checkUserPermissions(requiredSpecialty = null) {
    const storedUser = localStorage.getItem('discord_user');
    if (!storedUser) {
        window.location.href = '/home.html'; // Redirigir si no hay sesión activa
        return false;
    }

    try {
        const discordUser = JSON.parse(storedUser);

        // 1. Validación estricta por ID de usuario absoluta (Owner principal) - acceso total siempre
        if (discordUser.id === ABSOLUTE_SUPER_ADMIN_ID) {
            return true;
        }

        // 2. Validación contra la base de datos real del staff (admin/staff.html -> /api/staff)
        const staffList = await getStaffList();
        const me = findMyStaffRecord(staffList, discordUser);

        if (me) {
            // Si está registrado pero Inactivo, se deniega SIEMPRE, sin excepciones de rol.
            const isActive = (me.status || 'Activo') === 'Activo';
            if (!isActive) return false;

            // Owner activo en la base de datos => acceso total a cualquier panel
            const rango = (me.rango || '').toLowerCase().trim();
            if (rango === 'owner') return true;

            // Panel sin especialidad concreta exigida => con estar Activo es suficiente
            if (!requiredSpecialty) return true;

            // Comprobar que su(s) especialidad(es) incluyen la requerida por este panel
            const misEspecialidades = (me.especialidad || '')
                .split(',')
                .map(e => e.trim().toLowerCase())
                .filter(Boolean);

            const requeridas = Array.isArray(requiredSpecialty) ? requiredSpecialty : [requiredSpecialty];
            return requeridas.some(req => misEspecialidades.includes(req.toLowerCase().trim()));
        }

        /*
          3. Fallback: Validación jerárquica de Roles del Servidor (compatibilidad con
          usuarios que aún no estén dados de alta en admin/staff.html).
          Solo sirve para conceder acceso GENERAL (sin especialidad exigida); si el
          panel pide una especialidad concreta y el usuario no tiene ficha en la
          base de datos, no hay forma de saber su especialidad, así que se deniega.
        */
        if (requiredSpecialty) return false;

        const userRolesFromDiscord = discordUser.roles || []; // Array de IDs de roles que trae el usuario
        const hasValidRole = userRolesFromDiscord.some(roleId => Object.values(STAFF_ROLES).includes(roleId));

        return hasValidRole;

    } catch (e) {
        console.error("Error al verificar los permisos del usuario:", e);
        return false;
    }
}