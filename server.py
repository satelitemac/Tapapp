import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

app = FastAPI()

# --- 1. MEMORIA DEL SISTEMA ---
all_connections = set()
active_users = {} 
user_list = []      # Lista de nombres para el Radar y mapeo DMX
winner_id = None
dmx_mode = False
last_sent_states = {} # Memoria de colores para no saturar el WiFi

# Memoria para el despertador de portadas
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
    current_track_info["url"] = data.url
    current_track_info["artist"] = data.artist
    current_track_info["track"] = data.track

    await broadcast({
        "action": "update_cover", 
        "url": data.url, 
        "artist": data.artist, 
        "track": data.track
    })
    return {"status": "ok"}

@app.get("/current_status")
async def get_current_status():
    return {"status": "ok", "info": current_track_info}


# --- 3. RECEPTOR ART-NET NATIVO (EL CORAZÓN DMX) ---
class NativeArtNetListener(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print("📡 Receptor Art-Net NATIVO activo en el puerto 6454")

    def datagram_received(self, data, addr):
        global dmx_mode, active_users, user_list, last_sent_states
        
        # Si el Admin no ha activado el DMX, ignoramos la red
        if not dmx_mode:
            return
            
        # Confirmamos que el paquete es ArtDmx (0x5000)
        if data[:8] == b'Art-Net\x00' and (data[8] + (data[9] << 8)) == 0x5000:
            universe = data[14] + (data[15] << 8)
            
            # Escuchamos solo el Universo 0
            if universe == 0:
                dmx_data = data[18:]
                
                # REPARTO DE CANALES: Cada usuario conectado es un foco RGB de 3 canales
                for index, user_id in enumerate(user_list):
                    if user_id not in active_users:
                        continue
                        
                    ws = active_users[user_id]
                    start_chan = index * 3  # Ej: User0->Ch0, User1->Ch3, User2->Ch6
                    
                    if start_chan + 2 < len(dmx_data):
                        r = dmx_data[start_chan]
                        g = dmx_data[start_chan + 1]
                        b = dmx_data[start_chan + 2]
                        
                        # OPTIMIZACIÓN: Solo enviar si el color cambia
                        last_state = last_sent_states.get(user_id)
                        if last_state != (r, g, b):
                            last_sent_states[user_id] = (r, g, b)
                            
                            # Si es negro (0,0,0) limpiamos. Si no, encendemos flash.
                            if r == 0 and g == 0 and b == 0:
                                msg = json.dumps({"action": "clear_flash"})
                            else:
                                msg = json.dumps({"action": "flash", "color": f"rgb({r},{g},{b})"})
                            
                            # 🟢 AQUÍ ESTÁ LA MEJORA DE SEGURIDAD (safe_send)
                            async def safe_send(socket, mensaje):
                                try:
                                    await socket.send_text(mensaje)
                                except:
                                    pass # Si se acaba de desconectar, lo ignoramos para no bloquear el servidor

                            asyncio.create_task(safe_send(ws, msg))

# Arrancamos el receptor UDP automáticamente cuando arranca FastAPI
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        lambda: NativeArtNetListener(),
        local_addr=('0.0.0.0', 6454)
    )


# --- 4. WEBSOCKETS (LOS MÓVILES Y EL ADMIN) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    all_connections.add(websocket)
    current_id = None
    global winner_id, dmx_mode, user_list

    # Mandar estado actual de portadas al que acaba de entrar
    if current_track_info["url"]:
        await websocket.send_text(json.dumps({
            "action": "update_cover",
            "url": current_track_info["url"],
            "artist": current_track_info["artist"],
            "track": current_track_info["track"]
        }))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "presence":
                u_id = message.get("user_id")
                current_id = u_id
                
                if u_id != "ADMIN_PANEL":
                    active_users[u_id] = websocket
                    if u_id not in user_list:
                        user_list.append(u_id)
                await broadcast_users()
            
            elif message.get("type") == "ping": continue
            
            # Click del Jugador (Ruleta)
            elif message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = current_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # Control DMX desde Admin
            elif message.get("action") == "toggle_dmx":
                dmx_mode = message.get("value", False)
                if not dmx_mode:
                    last_sent_states.clear() 
                    await broadcast({"action": "clear_flash"})
                print(f"📡 MODO DMX: {'ON' if dmx_mode else 'OFF'}")
            
            # Botones del Admin y Chat
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
            if ws in all_connections:
                all_connections.remove(ws)