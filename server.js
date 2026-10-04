const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'public')));
app.use('/src', express.static(path.join(__dirname, 'src')));

// Ruta que intercepta el código de autorización de Discord
app.get('/auth/discord/callback', async (req, res) => {
    const code = req.query.code;
    if (!code) return res.redirect('/index.html');

    try {
        // 1. Intercambiamos el código por el token de acceso de Discord
        const tokenResponse = await fetch('https://discord.com/api/oauth2/token', {
            method: 'POST',
            body: new URLSearchParams({
                client_id: '1541119489758859315',
                client_secret: 'JkByq1rJFvOeRRo3i6Jk0PDmEw2GeZVJ', // <--- Reemplaza esto con tu Client Secret real del Developer Portal
                grant_type: 'authorization_code',
                code: code,
                redirect_uri: 'http://localhost:3000/auth/discord/callback',
            }),
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });

        const tokenData = await tokenResponse.json();
        if (!tokenData.access_token) return res.redirect('/index.html');

        // 2. Solicitamos los datos del perfil del usuario a la API de Discord
        const userResponse = await fetch('https://discord.com/api/users/@me', {
            headers: { authorization: `${tokenData.token_type} ${tokenData.access_token}` },
        });
        const userData = await userResponse.json();

        // 3. Construimos la URL de su foto de perfil real de Discord
        const avatarUrl = userData.avatar 
            ? `https://cdn.discordapp.com/avatars/${userData.id}/${userData.avatar}.png` 
            : null;

        // 4. Empaquetamos la información del usuario
        const discordUser = {
            id: userData.id,
            displayName: userData.global_name || userData.username,
            username: userData.username,
            avatarUrl: avatarUrl
        };

        // 5. Guardamos en el navegador del usuario y redirigimos a home.html
        res.send(`
            <script>
                localStorage.setItem('discord_user', JSON.stringify(${JSON.stringify(discordUser)}));
                window.location.href = '/home.html';
            </script>
        `);
    } catch (error) {
        console.error("Error al procesar la autenticación con Discord:", error);
        res.redirect('/index.html');
    }
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`[Clicksenserp] Servidor web listo en http://localhost:${PORT}`);
});