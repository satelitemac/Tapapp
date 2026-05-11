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
            if u_id and u_id != "ADMIN_PANEL":
                current_id = u_id
                active_users[u_id] = websocket

            if message.get("type") == "ping": continue

            # LÓGICA DE RADAR (Pulsar el botón)
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # LÓGICA DE ADMIN (Acciones de luces y control)
            elif "action" in message:
                if message["action"] == "reset":
                    winner_id = None
                
                # Para las linternas, el admin puede forzar un ganador aleatorio
                if message["action"] == "stop_flashing" and "force_winner" in message:
                    winner_id = message["force_winner"]
                    await broadcast({
                        "action": "light_winner_found", 
                        "winner_id": winner_id,
                        "color": message.get("color", "#ffffff")
                    })
                else:
                    await broadcast(message)
            else:
                await broadcast(message)

    except WebSocketDisconnect:
        if current_id in active_users:
            del active_users[current_id]

async def broadcast(message: dict):
    msg_str = json.dumps(message)
    for uid in list(active_users.keys()):
        try:
            await active_users[uid].send_text(msg_str)
        except:
            if uid in active_users: del active_users[uid]