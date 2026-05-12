from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()
active_users = {} 
winner_id = None

@app.get("/")
async def root():
    return {"status": "OK", "conectados": list(active_users.keys()), "total": len(active_users)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    current_id = None
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            u_id = message.get("user_id")
            
            # Si hay un ID nuevo (y no es el Admin), lo registramos y AVISAMOS
            if u_id and u_id != "ADMIN_PANEL" and current_id is None:
                current_id = u_id
                active_users[u_id] = websocket
                # Avisamos a todos de la nueva lista real
                await broadcast({"action": "update_users", "users": list(active_users.keys())})

            if message.get("type") == "ping": continue

            # Lógica de Radar
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # Lógica de Admin (Reset, Linternas, Colores)
            elif "action" in message:
                if message["action"] == "reset":
                    winner_id = None
                await broadcast(message)
            else:
                await broadcast(message)

    except WebSocketDisconnect:
        # Si la conexión se cae, lo borramos y AVISAMOS
        if current_id in active_users:
            del active_users[current_id]
            # Enviar la lista actualizada sin el usuario caído
            await broadcast({"action": "update_users", "users": list(active_users.keys())})

async def broadcast(message: dict):
    msg_str = json.dumps(message)
    for uid in list(active_users.keys()):
        try:
            await active_users[uid].send_text(msg_str)
        except:
            if uid in active_users: del active_users[uid]