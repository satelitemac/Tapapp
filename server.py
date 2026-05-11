from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
import json

app = FastAPI()
active_users = {} 
winner_id = None

# Almacén de la canción actual para que los que entren tarde la vean
current_track = {
    "title": "Esperando música...",
    "artist": "T&T DJ",
    "image": "https://images.unsplash.com/photo-1603048588665-791ca8aea617?q=80&w=1000"
}

@app.get("/")
async def root():
    return {"status": "OK", "conectados": list(active_users.keys()), "track": current_track}

# Nuevo endpoint para que el panel de Neo4j actualice la portada
@app.post("/update-track")
async def update_track(request: Request):
    global current_track
    data = await request.json()
    current_track = {
        "title": data.get("title", "Desconocido"),
        "artist": data.get("artist", "Desconocido"),
        "image": data.get("image", "")
    }
    await broadcast({"action": "update_track", "track": current_track})
    return {"status": "success"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    current_id = None
    
    # Al conectar, enviamos la canción actual inmediatamente
    await websocket.send_text(json.dumps({"action": "update_track", "track": current_track}))
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            u_id = msg.get("user_id")
            if u_id and u_id != "ADMIN_PANEL":
                current_id = u_id
                active_users[u_id] = websocket

            if msg.get("type") == "ping": continue

            if msg.get("type") == "player_click":
                if winner_id is None:
                    winner_id = u_id
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            elif "action" in msg:
                if msg["action"] == "reset": winner_id = None
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