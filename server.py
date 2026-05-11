from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

# Lista para guardar todos los teléfonos y ordenadores conectados
active_connections = []
winner_id = None

@app.get("/")
async def root():
    # Esto es lo que ves al entrar en tapapp.onrender.com
    return {"status": "T&T Super-Server Online", "msg": "Servidor de Concurso y VJ Activo"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global winner_id
    await websocket.accept()
    active_connections.append(websocket)
    print(f"Nueva conexión. Total: {len(active_connections)}")
    
    try:
        while True:
            # Recibimos mensajes de cualquier cliente (Admin o Móvil)
            data = await websocket.receive_text()
            message = json.loads(data)
            print(f"Recibido: {message}") 

            # 1. LÓGICA DEL RADAR: El primero que pulsa gana si no hay ganador
            if message.get("type") == "player_click":
                if winner_id is None:
                    winner_id = message.get("user_id")
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # 2. LÓGICA DE ADMIN: Órdenes de control
            elif "action" in message:
                if message["action"] == "reset":
                    winner_id = None
                
                # SORTEO DE LUCES: Si el admin detiene el parpadeo y envía un ganador forzado
                if message["action"] == "stop_flashing" and "force_winner" in message:
                    winner_id = message["force_winner"]
                    # Avisamos oficialmente a todos quién es el ganador
                    await broadcast({"action": "winner_found", "winner_id": winner_id})
                
                # Reenviamos la orden original (prepare, stop_flashing, etc.) a todos
                await broadcast(message)
            
            # 3. LÓGICA VJ/DJ Y OTROS: Peticiones musicales, etc.
            else:
                await broadcast(message)

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
        print("Conexión cerrada")

async def broadcast(message: dict):
    # Esta función envía el mensaje a ABSOLUTAMENTE TODOS los conectados
    for connection in active_connections:
        try:
            await connection.send_text(json.dumps(message))
        except:
            pass # Si alguna conexión falló, la ignoramos