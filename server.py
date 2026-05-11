from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

# Diccionario real: user_id -> WebSocket
active_users = {} 
winner_id = None

@app.get("/")
async def root():
    # Si entras aquí con el navegador, verás quién está conectado de verdad
    return {
        "status": "Servidor T&T Activo",
        "conectados": list(active_users.keys()),
        "total": len(active_users)
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    current_id = None
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # --- AUTO-REGISTRO ---
            # Si el mensaje trae un user_id, lo registramos inmediatamente si no estaba
            u_id = message.get("user_id")
            if u_id:
                current_id = u_id
                if u_id not in active_users:
                    print(f"✨ Registrando nuevo usuario: {u_id}")
                active_users[u_id] = websocket

            # LÓGICA DE RADAR
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # LÓGICA DE ADMIN
            elif "action" in message:
                if message["action"] == "reset": winner_id = None
                if message["action"] == "stop_flashing" and "force_winner" in message:
                    winner_id = message["force_winner"]
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
                await broadcast(message)
            
            # PETICIONES Y OTROS
            else:
                await broadcast(message)

    except WebSocketDisconnect:
        if current_id in active_users:
            del active_users[current_id]
        print(f"❌ Desconectado: {current_id}")

async def broadcast(message: dict):
    msg_str = json.dumps(message)
    for uid in list(active_users.keys()):
        try:
            await active_users[uid].send_text(msg_str)
        except:
            if uid in active_users: del active_users[uid]