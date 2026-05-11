from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

# Diccionario para mapear user_id -> WebSocket
# Esto nos permite saber exactamente quién está conectado
active_users = {} 
winner_id = None

@app.get("/")
async def root():
    return {"status": "T&T Super-Server Online", "msg": "Servidor con Gestión de Identidad Activo"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    
    current_user_id = None
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # REGISTRO: Lo primero que hace cualquier cliente al conectar
            if message.get("type") == "presence" or "user_id" in message:
                user_id = message.get("user_id")
                if user_id:
                    current_user_id = user_id
                    active_users[user_id] = websocket
                    # Notificamos al Admin que hay alguien nuevo
                    await broadcast({"type": "presence", "user_id": user_id, "count": len(active_users)})

            # 1. LÓGICA DEL RADAR
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = message.get("user_id")
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # 2. LÓGICA DE ADMIN
            elif "action" in message:
                if message["action"] == "reset":
                    winner_id = None
                
                if message["action"] == "stop_flashing" and "force_winner" in message:
                    winner_id = message["force_winner"]
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
                
                await broadcast(message)
            
            # 3. MENSAJES/NOTAS (VJ/DJ)
            else:
                # Reenviamos el mensaje a todos para que el Admin y DJ lo vean
                await broadcast(message)

    except WebSocketDisconnect:
        if current_user_id in active_users:
            del active_users[current_user_id]
        print(f"Usuario {current_user_id} desconectado")

async def broadcast(message: dict):
    # Enviamos a todos los que están en nuestro diccionario de activos
    message_str = json.dumps(message)
    # Hacemos una copia de las llaves para evitar errores si alguien se desconecta durante el loop
    for user_id in list(active_users.keys()):
        try:
            ws = active_users[user_id]
            await ws.send_text(message_str)
        except:
            # Si falla, limpiamos ese usuario
            if user_id in active_users:
                del active_users[user_id]