import asyncio
import logging
import sys
from app.services.openclaw import OpenClawService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

async def test_openclaw():
    service = OpenClawService()
    print("Enviando mensaje de prueba a OpenClaw...")
    response = await service.send_message("Hola Lucía, ¿estás ahí?")
    print(f"Respuesta de OpenClaw: {response}")

if __name__ == "__main__":
    asyncio.run(test_openclaw())
