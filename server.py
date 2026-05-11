from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()
active_users = {} 
winner_id = None

@app.get("/")
async def root():
    return {"status": "OK", "conectados": list(active_users.keys())}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    current_id = None
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            u_id = msg.get("user_id")
            if u_id and u_id != "ADMIN_PANEL":
                current_id = u_id
                active_users[u_id] = websocket

            if msg.get("type") == "ping":
                continue

            if msg.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            elif "action" in msg:
                if msg["action"] == "reset":
                    winner_id = None
                await broadcast(msg)
            else:
                await broadcast(msg)

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