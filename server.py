import asyncio
import json
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from stupidArtnet import StupidArtnetServer

app = FastAPI()

# --- 1. MEMORIA DEL SISTEMA ---
all_connections = set()
active_users = {} 
user_list = []      # Lista de nombres para el Radar y mapeo DMX
winner_id = None
dmx_mode = False
last_sent_states = {} # <--- ERROR 1 CORREGIDO: Definido aquí

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

# --- 3. PUENTE ART-NET (RESOLUME) ---
ARTNET_UNIVERSE = 0
artnet_node = StupidArtnetServer()
main_loop = None

def artnet_to_ws_bridge():
    global dmx_mode, main_loop, last_sent_states # <--- ERROR 2 CORREGIDO: Añadido a global
    while True:
        if dmx_mode and main_loop and len(user_list) > 0:
            buffer = artnet_node.get_buffer(ARTNET_UNIVERSE)
            
            if len(buffer) >= 3:
                for i, u_id in enumerate(user_list):
                    base_ch = i * 3
                    if base_ch + 2 < len(buffer):
                        r, g, b = buffer[base_ch], buffer[base_ch+1], buffer[base_ch+2]
                        color_hex = f"#{r:02x}{g:02x}{b:02x}"
                        torch_on = (r + g + b) > 380 
                        
                        # --- DIRTY CHECK: Solo enviamos si el estado cambia ---
                        current_state = (color_hex, torch_on)
                        if last_sent_states.get(u_id) != current_state:
                            msg = json.dumps({"action": "dmx_live", "color": color_hex, "torch": torch_on})
                            ws = active_users.get(u_id)
                            if ws:
                                asyncio.run_coroutine_threadsafe(ws.send_text(msg), main_loop)
                            last_sent_states[u_id] = current_state
                        
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
            
            # Gestión de Presencia Mejorada
            if message.get("type") == "presence":
                current_id = u_id
                active_users[u_id] = websocket
                # Solo añadimos a la lista de DMX/Radar si no es el Admin
                if u_id != "ADMIN_PANEL" and u_id not in user_list:
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
                if not dmx_mode:
                    last_sent_states.clear() # Limpiamos memoria al apagar
                print(f"📡 MODO DMX: {dmx_mode}")
            
            # Lógica de Admin (Resets, etc) y Chat
            elif "action" in message or message.get("type") == "chat":
                if message.get("action") == "reset":
                    winner_id = None
                await broadcast(message)

    except WebSocketDisconnect:
        if websocket in all_connections:
            all_connections.remove(websocket)
        if current_id in active_users:
            del active_users[current_id]
        if current_id in user_list:
            user_list.remove(current_id)
        if current_id in last_sent_states:
            del last_sent_states[current_id]
        await broadcast_users()

async def broadcast_users():
    await broadcast({"action": "update_users", "users": user_list})

async def broadcast(message: dict):
    msg_str = json.dumps(message)
    for ws in list(all_connections):
        try:
            await ws.send_text(msg_str)
        except:
            if ws in all_connections: all_connections.remove(ws)