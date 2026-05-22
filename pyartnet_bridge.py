import asyncio

class ArtNetListener(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print("📡 Escuchando Art-Net nativo en el puerto 6454...")
        print("Mueve un fader en Resolume/Chamsys...")

    def datagram_received(self, data, addr):
        # 1. Comprobamos que el paquete que llega es realmente de Art-Net
        if data[:8] == b'Art-Net\x00':
            # 2. Leemos el OpCode (Nos interesa el 0x5000 que es ArtDmx - Datos de luces)
            opcode = data[8] + (data[9] << 8)
            
            if opcode == 0x5000:
                # 3. Leemos a qué universo va dirigido
                universe = data[14] + (data[15] << 8)
                
                # 4. Los valores de los 512 canales DMX empiezan en el byte 18
                dmx_data = data[18:]
                
                # Extraemos los canales 1, 2 y 3 (RGB)
                colores = list(dmx_data[:3]) 
                
                # Para no saturar la consola, solo imprimimos el universo 0
                if universe == 0:
                    print(f"✅ Recibido Universo {universe} de {addr[0]} | RGB: {colores}")

async def start_listener():
    loop = asyncio.get_running_loop()
    
    # Creamos un servidor UDP en el puerto 6454 (El puerto oficial de Art-Net)
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ArtNetListener(),
        local_addr=('0.0.0.0', 6454)
    )

    try:
        # Mantenemos el programa corriendo eternamente
        await asyncio.sleep(360000)
    finally:
        transport.close()

if __name__ == "__main__":
    try:
        asyncio.run(start_listener())
    except KeyboardInterrupt:
        print("\n🛑 Escucha detenida.")