from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()
# Guardamos todos los sockets conectados para avisarles de todo
all_connections = set()
# Guardamos nombre -> socket solo para la lógica de juego
active_users = {} 
winner_id = None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    all_connections.add(websocket) # <--- El Admin ahora entra aquí
    current_id = None
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            message = json.loads(raw_data)
            u_id = message.get("user_id")
            
            # Registro de jugador
            if u_id and u_id != "ADMIN_PANEL" and current_id is None:
                current_id = u_id
                active_users[u_id] = websocket
                await broadcast_users()

            if message.get("type") == "ping": continue

            # Al recibir un click, el ganador se anuncia a TODOS (incluido Admin)
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # Lógica de Admin
            elif "action" in message:
                if message["action"] == "reset":
                    winner_id = None
                await broadcast(message)

    except WebSocketDisconnect:
        all_connections.remove(websocket)
        if current_id in active_users:
            del active_users[current_id]
            await broadcast_users()

async def broadcast_users():
    """Envía la lista de nombres real a todo el mundo"""
    await broadcast({"action": "update_users", "users": list(active_users.keys())})

async def broadcast(message: dict):
    """Envía un mensaje a ABSOLUTAMENTE TODOS los conectados"""
    msg_str = json.dumps(message)
    # Copiamos la lista para evitar errores si alguien se desconecta justo ahora
    for ws in list(all_connections):
        try:
            await ws.send_text(msg_str)
        except:
            if ws in all_connections:
                all_connections.remove(ws)