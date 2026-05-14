import asyncio
import json
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from stupidArtnet import StupidArtnetServer

app = FastAPI()

# --- 1. MEMORIA DEL SISTEMA (LO QUE YA TENÍAS) ---
all_connections = set()
active_users = {} 
winner_id = None
user_list = [] # Nueva: necesaria para que Resolume sepa el orden de los móviles

# --- 2. LÓGICA DE PORTADAS (STREAMLIT / RENDER.COM) ---
class CoverData(BaseModel):
    url: str
    artist: str = ""
    track: str = ""

@app.post("/update_cover")
async def post_cover(data: CoverData):
    await broadcast({
        "action": "update_cover", 
        "url": data.url, 
        "artist": data.artist, 
        "track": data.track
    })
    return {"status": "ok"}

# --- 3. NUEVO: PUENTE ART-NET (RESOLUME) ---
ARTNET_UNIVERSE = 0
dmx_mode = False
artnet_node = StupidArtnetServer()
main_loop = None

def artnet_to_ws_bridge():
    """Hilo independiente para las luces"""
    global dmx_mode, main_loop
    while True:
        if dmx_mode and main_loop and len(user_list) > 0:
            buffer = artnet_node.get_buffer(ARTNET_UNIVERSE)
            for i, u_id in enumerate(user_list):
                base_ch = i * 3
                if base_ch + 2 < len(buffer):
                    r, g, b = buffer[base_ch], buffer[base_ch+1], buffer[base_ch+2]
                    color_hex = f"#{r:02x}{g:02x}{b:02x}"
                    # Encendemos flash si el brillo promedio es alto
                    torch_on = (r + g + b) > 380 
                    
                    msg = json.dumps({"action": "dmx_live", "color": color_hex, "torch": torch_on})
                    ws = active_users.get(u_id)
                    if ws:
                        asyncio.run_coroutine_threadsafe(ws.send_text(msg), main_loop)
        time.sleep(0.04) # 25 FPS

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    threading.Thread(target=artnet_to_ws_bridge, daemon=True).start()

# --- 4. EL WEBSOCKET (CONCURSO + CHAT + DMX) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id, dmx_mode, user_list
    await websocket.accept()
    all_connections.add(websocket)
    current_id = None
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            message = json.loads(raw_data)
            u_id = message.get("user_id")
            
            # Registro de usuario (Radar)
            if u_id and u_id != "ADMIN_PANEL" and current_id is None:
                current_id = u_id
                active_users[u_id] = websocket
                if u_id not in user_list:
                    user_list.append(u_id)
                await broadcast_users()

            if message.get("type") == "ping": continue

            # Lógica del Pulsador (Juego)
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # Control DMX desde Admin
            elif message.get("action") == "toggle_dmx":
                dmx_mode = message.get("value", False)
                print(f"📡 MODO DMX: {dmx_mode}")
            
            # Lógica de Admin (Resets, etc) y Chat
            elif "action" in message or message.get("type") == "chat":
                if message.get("action") == "reset":
                    winner_id = None
                await broadcast(message)

    except WebSocketDisconnect:
        all_connections.remove(websocket)
        if current_id in active_users:
            del active_users[current_id]
            if current_id in user_list:
                user_list.remove(current_id)
            await broadcast_users()

async def broadcast_users():
    """Mantiene la lista de nombres actualizada para el Radar"""
    await broadcast({"action": "update_users", "users": user_list})

async def broadcast(message: dict):
    """Envía a todos (incluido Render.com y Admin)"""
    msg_str = json.dumps(message)
    for ws in list(all_connections):
        try:
            await ws.send_text(msg_str)
        except:
            if ws in all_connections: all_connections.remove(ws)