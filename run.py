import threading
import traceback
import uvicorn
from dotenv import load_dotenv

load_dotenv()

def iniciar_bot():
    """Inicia el Bot de Discord en segundo plano y muestra el error real"""
    try:
        from bot import bot, TOKEN 
        if TOKEN:
            print("🤖 [DISCORD] Iniciando conexión del Bot...")
            bot.run(TOKEN)
        else:
            print("⚠️ [DISCORD] No se encontró el TOKEN del bot en el archivo .env")
    except Exception as e:
        print(f"❌ [DISCORD] Error detallado al importar o iniciar el bot:")
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 [SISTEMA] Iniciando ClickSense RP (Web + Bot)...")

    # 1. Lanzamos el Bot de Discord en un hilo secundario
    hilo_bot = threading.Thread(target=iniciar_bot, daemon=True)
    hilo_bot.start()

    # 2. Ejecutamos Uvicorn en el hilo principal
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)