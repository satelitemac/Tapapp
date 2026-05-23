import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

app = FastAPI()

# --- 1. MEMORIA DEL SISTEMA (LA NUBE) ---
all_connections = set()
active_users = {}   # Diccionario de móviles en pista { "id_usuario": websocket }
user_list = []      # Lista ordenada para el mapeo DMX
winner_id = None
dmx_mode = False    # Interruptor Maestro del Admin

# Memoria de la canción actual
current_track_info = {
    "url": "",
    "artist": "ESPERANDO...",
    "track": "MÚSICA"
}

# --- 2. LÓGICA DE PORTADAS (REST API) ---
class CoverData(BaseModel):
    url: str
    artist: str = ""
    track: str = ""

@app.post("/update_cover")
async def post_cover(data: CoverData):
    global current_track_info
    current_track_info.update({"url": data.url, "artist": data.artist, "track": data.track})
    await broadcast({"action": "update_cover", **current_track_info})
    return {"status": "ok"}

@app.get("/current_status")
async def get_current_status():
    return {"status": "ok", "info": current_track_info}


# --- 3. WEBSOCKETS (MÓVILES, ADMIN Y BRIDGE) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    all_connections.add(websocket)
    current_id = None
    global winner_id, dmx_mode, user_list

    # 1. Al entrar, le damos la portada actual
    if current_track_info["url"]:
        await websocket.send_text(json.dumps({"action": "update_cover", **current_track_info}))

    # Función segura para disparar luces por 4G sin bloquear
    async def safe_send(socket, mensaje):
        try:
            await socket.send_text(mensaje)
        except:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # --- GESTIÓN DE PRESENCIA ---
            if message.get("type") == "presence":
                u_id = message.get("user_id")
                current_id = u_id
                
                # Si no es ni el Admin ni el Bridge local, es un móvil de la pista
                if u_id not in ["ADMIN_PANEL", "ARTNET_BRIDGE"]:
                    active_users[u_id] = websocket
                    if u_id not in user_list:
                        user_list.append(u_id)
                await broadcast_users()
            
            elif message.get("type") == "ping": continue
            
            # --- LA MAGIA: EL ENRUTADOR DMX ---
            # El Bridge local nos envía un paquete de luz destinado a un móvil concreto
            elif message.get("action") in ["flash", "clear_flash", "dmx_live"]:
                if dmx_mode: # Solo obedecemos si el Admin ha encendido el DMX
                    target = message.get("target_id")
                    if target and target in active_users:
                        # Reenviamos la orden de luz exacta al móvil destinatario
                        msg_out = {"action": message.get("action")}
                        if "color" in message:
                            msg_out["color"] = message["color"]
                        # Enviamos solo a ese usuario
                        await active_users[target].send_text(json.dumps(msg_out))
                    else:
                        # Si no hay target específico, hacemos broadcast a todos
                        await broadcast(message)

            # --- JUEGO RULETA ---
            elif message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = current_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # --- CONTROL DMX DESDE ADMIN ---
            elif message.get("action") == "toggle_dmx":
                dmx_mode = message.get("value", False)
                if not dmx_mode:
                    await broadcast({"action": "clear_flash"}) # Apaga todo al desactivar
                print(f"📡 MODO DMX: {'ON' if dmx_mode else 'OFF'}")
            
            # --- BOTONES DE ADMIN / CHAT ---
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
        await broadcast_users()

async def broadcast_users():
    # Avisamos a todos (especialmente al Bridge) de quiénes están en pista
    await broadcast({"action": "update_users", "users": user_list})

async def broadcast(message: dict):
    msg_str = json.dumps(message)
    for ws in list(all_connections):
        try:
            await ws.send_text(msg_str)
        except:
            if ws in all_connections:
                all_connections.remove(ws)