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
            print(f"Recibido: {message}") # Esto aparecerá en los logs de Render

            # 1. LÓGICA DEL RADAR: Si un jugador pulsa y no hay ganador aún
            if message.get("type") == "player_click" and winner_id is None:
                winner_id = message.get("user_id")
                await broadcast({"action": "winner_found", "winner_id": winner_id})
            
            # 2. LÓGICA DE ADMIN: Si envías una orden (prepare, tension, go o reset)
            elif "action" in message:
                if message["action"] == "reset":
                    winner_id = None
                await broadcast(message)
            
            # 3. LÓGICA VJ/DJ: Mensajes de notas o peticiones musicales
            # Se reenvían directamente a todos los conectados (incluyendo el Admin)
            else:
                await broadcast(message)

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("Conexión cerrada")

async def broadcast(message: dict):
    # Esta función envía el mensaje a ABSOLUTAMENTE TODOS los conectados
    for connection in active_connections:
        try:
            await connection.send_text(json.dumps(message))
        except:
            pass # Si alguna conexión falló, la ignoramos