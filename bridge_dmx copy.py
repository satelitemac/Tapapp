import asyncio
import json
import websockets
import socket

# CONFIGURACIÓN
RENDER_URL = "wss://tapapp.onrender.com/ws"
PUERTOS = [6453, 6454] # Escuchamos en ambos

async def bridge():
    sockets = []
    
    # 1. Abrimos una "oreja" por cada puerto
    for puerto in PUERTOS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setblocking(False)
            s.bind(("0.0.0.0", puerto))
            sockets.append(s)
            print(f"📡 Escuchando Art-Net en el puerto {puerto}...")
        except Exception as e:
            print(f"⚠️ No pude abrir el puerto {puerto}: {e}")

    if not sockets:
        print("❌ No hay puertos disponibles. Aborta.")
        return

    print(f"🚀 PUENTE MULTI-PUERTO ACTIVADO")
    print(f"🔗 Conectando a Render: {RENDER_URL}")

    async with websockets.connect(RENDER_URL) as ws:
        await ws.send(json.dumps({"type": "presence", "user_id": "ARTNET_BRIDGE"}))
        
        user_list = []
        has_signal = False

        while True:
            # 2. Ver usuarios nuevos
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.001)
                data = json.loads(msg)
                if data.get("action") == "update_users":
                    user_list = data.get("users", [])
                    print(f"👥 Usuarios activos: {len(user_list)}")
            except: pass

            # 3. Revisar TODOS los puertos abiertos
            for s in sockets:
                try:
                    data, addr = s.recvfrom(1024)
                    dmx = data[18:] # Saltamos la cabecera Art-Net
                    
                    if not has_signal and len(dmx) > 0:
                        print(f"✅ ¡SEÑAL DETECTADA en puerto {s.getsockname()[1]}! Viene de {addr}")
                        has_signal = True

                    if len(user_list) > 0 and len(dmx) >= 3:
                        for i, u_id in enumerate(user_list):
                            base = i * 3
                            if base + 2 < len(dmx):
                                r, g, b = dmx[base], dmx[base+1], dmx[base+2]
                                if r > 0 or g > 0 or b > 0:
                                    await ws.send(json.dumps({
                                        "action": "dmx_live",
                                        "target_id": u_id,
                                        "color": f"#{r:02x}{g:02x}{b:02x}",
                                        "torch": (r + g + b) > 380
                                    }))
                except BlockingIOError:
                    continue # Este puerto no tiene datos ahora, probamos el siguiente

            await asyncio.sleep(0.02) # 50 FPS para máxima suavidad

if __name__ == "__main__":
    try:
        asyncio.run(bridge())
    except KeyboardInterrupt:
        print("\n🛑 Puente detenido.")