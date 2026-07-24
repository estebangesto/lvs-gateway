# Luc.ia Voice Service v3

Este es el servicio de backend de voz de tercera generación para el ecosistema Luc.ia. Actúa como un puente entre aplicaciones cliente, el agente de OpenClaw y los servicios de procesamiento de lenguaje natural (STT/TTS).

## Arquitectura

El servicio está diseñado para ser extremadamente ligero al delegar el procesamiento pesado a otros servicios especializados:

1.  **Speech-to-Text (STT):** Delega la transcripción al servicio `lucia-stt` a través de un Unix Socket (`/run/user/1000/lucia-stt.sock`), evitando cargar modelos de IA en este proceso.
2.  **Text-to-Speech (TTS):** Utiliza la API de ElevenLabs. El cliente HTTP se mantiene dentro del proceso para reutilizar conexiones.
3.  **Cerebro (OpenClaw):** Se comunica con el endpoint HTTP OpenResponses (`POST /v1/responses`) del Gateway, consumiendo su respuesta SSE internamente.

## Requisitos

*   Servicio `lucia-stt` activo y escuchando en el socket.
*   Conexión a internet y credenciales de ElevenLabs para TTS.
*   OpenClaw Gateway activo (por defecto en el puerto 18789).

## Instalación como Servicio de Linux

Para que el servicio se inicie automáticamente con el sistema:

```bash
# Copiar el archivo de servicio
sudo cp /opt/lucia-voice-service-v3/lucia-voice-v3.service /etc/systemd/system/

# Activar y arrancar
sudo systemctl daemon-reload
sudo systemctl enable lucia-voice-v3
sudo systemctl start lucia-voice-v3
```

## API Documentation

El servicio corre por defecto en el puerto **8001**.

### 1. Health Check
`GET /health`
Verifica si el servicio está arriba.

### 2. Procesar Voz/Texto
`POST /voice/process`

Envía audio o texto para obtener una respuesta del agente.

**Parámetros (Form-data):**
*   `audio` (opcional): Archivo de audio (wav, mp3, ogg).
*   `text` (opcional): Texto directo si no se envía audio.
*   `tts` (opcional): controla la síntesis. Por defecto, las solicitudes de texto no generan audio y las solicitudes de voz sí.

**Lógica de respuesta:**
*   Si envías **audio**: El sistema transcribe, envía a Luc.ia, y devuelve la respuesta en **texto y audio** (Base64).
*   Si envías **texto**: El sistema envía a Luc.ia y devuelve la respuesta solo en **texto**.

### 3. Transcribir antes de procesar
`POST /voice/transcribe`

Recibe `audio` y devuelve `{ "input_text": "..." }` sin llamar a OpenClaw ni
generar TTS. El cliente v8 lo usa para mostrar la transcripción antes de enviar
el mensaje al agente.

**Ejemplo de Respuesta JSON:**
```json
{
  "input_text": "Hola Lucía, ¿cómo estás?",
  "response_text": "¡Hola! Estoy muy bien, ¿en qué puedo ayudarte?",
  "response_audio_b64": "UklGRuS...",
  "format": "mp3"
}
```

## Ejemplo de uso con cURL

```bash
# Enviar un audio y recibir respuesta completa
curl -X POST http://localhost:8001/voice/process \
  -F "audio=@test_input.wav"
```

## Archivos de Utilidad
*   `test_voice_system.py`: Script para validar que el TTS y STT local funcionan.
*   `diag_rpc.py`: Herramienta de diagnóstico para la conexión WebSocket con OpenClaw.

## Configuración

Copiá `.env.example` a `.env` y completá los valores. No guardes tokens o claves en el código fuente. Por defecto, si `ELEVENLABS_API_KEY` queda vacío, el servicio reutiliza el almacén activo de secretos de OpenClaw indicado por `ELEVENLABS_SECRET_FILE`; así no se duplica la clave.

La configuración base usa la voz Malena (`p7AwDmKvTdoHTBuueGvP`) y `eleven_flash_v2_5`, elegidos para reducir latencia. Cambiá `ELEVENLABS_MODEL_ID` a `eleven_multilingual_v2` si priorizás estabilidad de voz por sobre velocidad.

El servicio usa el Gateway mediante `POST /v1/responses`, con `OPENCLAW_AGENT_ID` y `OPENCLAW_SESSION_KEY` para enrutar la conversación. El Gateway debe tener habilitado el endpoint HTTP compatible. Por defecto toma `GATEWAY_AUTH_TOKEN` del almacén activo de secretos de OpenClaw (`OPENCLAW_SECRET_FILE`), sin duplicarlo en `.env`; `OPENCLAW_API_TOKEN` queda como alternativa para un despliegue autónomo.
