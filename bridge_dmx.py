import asyncio
import json
import websockets
from stupidArtnet import StupidArtnetServer

# CONFIGURACIÓN
RENDER_URL = "wss://tapapp.onrender.com/ws"
ARTNET_UNIVERSE = 0
user_list = []

async def artnet_bridge():
    global user_list
    artnet_node = StupidArtnetServer()
    
    print(f"🚀 Puente iniciado. Conectando a {RENDER_URL}...")
    
    async with websockets.connect(RENDER_URL) as websocket:
        # 1. Identificarse como el puente
        await websocket.send(json.dumps({"type": "presence", "user_id": "ARTNET_BRIDGE"}))
        
        while True:
            try:
                # Escuchar actualizaciones de usuarios desde Render
                msg = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                data = json.loads(msg)
                if data.get("action") == "update_users":
                    user_list = data.get("users", [])
            except: pass

            # 2. Leer Art-Net y enviar a Render
            buffer = artnet_node.get_buffer(ARTNET_UNIVERSE)
            if len(buffer) >= 3 and len(user_list) > 0:
                for i, u_id in enumerate(user_list):
                    base_ch = i * 3
                    if base_ch + 2 < len(buffer):
                        r, g, b = buffer[base_ch], buffer[base_ch+1], buffer[base_ch+2]
                        color_hex = f"#{r:02x}{g:02x}{b:02x}"
                        torch_on = (r + g + b) > 380
                        
                        # Enviamos la orden de luz a Render
                        await websocket.send(json.dumps({
                            "action": "dmx_live",
                            "target_id": u_id, # Enviamos a quién va dirigido
                            "color": color_hex,
                            "torch": torch_on
                        }))
            await asyncio.sleep(0.05) # ~20 FPS para no saturar el 5G

asyncio.run(artnet_bridge())