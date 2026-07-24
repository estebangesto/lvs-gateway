import asyncio
import io
import os
import sys
from app.services.tts import TextToSpeech
from app.services.stt import SpeechToText

async def run_test():
    print("--- Iniciando Prueba de Integración de Voz ---")
    
    # 1. Inicializar servicios
    tts = TextToSpeech()
    stt = SpeechToText()
    
    test_text = "Hola, soy Lucía. Esta es una prueba para verificar que el sistema de voz y transcripción funciona correctamente."
    temp_audio = "test_integration.mp3"
    
    try:
        # 2. Probar TTS (Generar Audio)
        print(f"\n[1/2] Generando TTS para: '{test_text}'")
        await tts.synthesize(test_text, temp_audio)
        
        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
            print(f"OK: Audio generado exitosamente ({os.path.getsize(temp_audio)} bytes)")
        else:
            print("ERROR: No se pudo generar el archivo de audio.")
            return

        # 3. Probar STT (Transcribir el audio generado)
        print(f"\n[2/2] Enviando audio al servicio STT (vía socket)...")
        with open(temp_audio, "rb") as f:
            audio_data = io.BytesIO(f.read())
        
        transcript = await stt.transcribe_stream(audio_data)
        
        if transcript:
            print(f"OK: Transcripción recibida: '{transcript}'")
            print("\n--- Resultado Final: ÉXITO ---")
        else:
            print("ERROR: La transcripción volvió vacía o falló la conexión al socket.")
            
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
    finally:
        # Limpieza
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
            print(f"\n(Archivo temporal {temp_audio} eliminado)")

if __name__ == "__main__":
    # Asegurarnos de que el path de la app esté disponible
    sys.path.append(os.getcwd())
    asyncio.run(run_test())
