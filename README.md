# LVS Gateway

Este es el servicio de backend de voz para el ecosistema LVS. Actúa como un puente entre aplicaciones cliente, el agente de OpenClaw y los servicios de procesamiento de lenguaje natural (STT/TTS).

## Arquitectura

El servicio está diseñado para ser extremadamente ligero al delegar el procesamiento pesado a otros servicios especializados:

1.  **Speech-to-Text (STT):** Delega la transcripción al servicio `lvs-stt` a través de un Unix Socket (`/run/user/1000/lvs-stt.sock`), evitando cargar modelos de IA en este proceso.
2.  **Text-to-Speech (TTS):** Utiliza la API de ElevenLabs. El cliente HTTP se mantiene dentro del proceso para reutilizar conexiones.
3.  **Cerebro (OpenClaw):** Se comunica con el endpoint HTTP OpenResponses (`POST /v1/responses`) del Gateway, consumiendo su respuesta SSE internamente.

## Requisitos

*   Servicio `lvs-stt` activo y escuchando en el socket.
*   Conexión a internet y credenciales de ElevenLabs para TTS.
*   OpenClaw Gateway activo (por defecto en el puerto 18789).
*   Python 3.13.

## Instalación y despliegue

El servicio se ejecuta desde `/opt/lvs-gateway` y utiliza una unidad
de **systemd de usuario**. No copies ni muevas el virtualenv de una instalación
anterior: los virtualenvs contienen rutas absolutas y no son portables.

### 1. Preparar el checkout y el entorno virtual

```bash
git clone git@gitlab-lucia:egesto/lvs-gateway.git /opt/lvs-gateway
cd /opt/lvs-gateway

python3.13 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m compileall -q app
```

Las dependencias están fijadas en `requirements.txt`. No uses un `pip freeze`
del entorno histórico: puede incluir componentes de STT local que este backend
ya no utiliza.

### 2. Configurar el entorno local

```bash
cp .env.example .env
```

Editá `.env` sólo con valores propios del despliegue. No se versionan `.env`,
tokens ni claves. Por defecto, el servicio reutiliza los secretos activos de
OpenClaw para el Gateway y ElevenLabs; `OPENCLAW_API_TOKEN` y
`ELEVENLABS_API_KEY` se reservan para despliegues autónomos.

`OPENCLAW_SESSION_KEY` identifica la conversación persistente a la que el
Gateway enruta las solicitudes de voz. Usá una clave estable y distinta para
cada cliente que deba conservar contexto independiente.

### 3. Instalar y administrar la unidad de usuario

```bash
# Copiar o actualizar la unidad de usuario
mkdir -p ~/.config/systemd/user
cp /opt/lvs-gateway/lvs-gateway.service ~/.config/systemd/user/

# Recargar, activar y arrancar
systemctl --user daemon-reload
systemctl --user enable --now lvs-gateway

# Verificar estado y consultar logs
systemctl --user status lvs-gateway
journalctl --user -u lvs-gateway -f
```

Para actualizar el servicio, obtené la versión deseada del repositorio,
reinstalá las dependencias si cambió `requirements.txt`, copiá de nuevo la
unidad si cambió y luego recargá systemd antes de reiniciar el servicio.

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
*   Si envías **audio**: El sistema transcribe, envía el texto al agente configurado y devuelve la respuesta en **texto y audio** (Base64).
*   Si envías **texto**: El sistema envía el texto al agente configurado y devuelve la respuesta solo en **texto**.

### 3. Transcribir antes de procesar
`POST /voice/transcribe`

Recibe `audio` y devuelve `{ "input_text": "..." }` sin llamar a OpenClaw ni
generar TTS. El cliente v8 lo usa para mostrar la transcripción antes de enviar
el mensaje al agente.

**Ejemplo de Respuesta JSON:**
```json
{
  "input_text": "Hola, ¿cómo estás?",
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
