# Changelog

Todos los cambios relevantes de LVS Gateway se documentan en este archivo.

## [Unreleased]

## [0.2.0] - 2026-10-08

### Added

- Soporte seleccionable para ElevenLabs `eleven_v4`, mediante Text-to-Dialogue HTTP.
- Soporte para ElevenLabs `eleven_v4_turbo`, mediante Text-to-Dialogue WebSocket.
- Soporte seleccionable para Microsoft Edge TTS mediante `TTS_PROVIDER=edge`, con voz, idioma, velocidad y tono configurables.
- Configuración de Edge con Elena Neural (`es-AR-ElenaNeural`), locale `es-AR`, velocidad `+15%` y tono `+0Hz` como valores iniciales. El formato de Edge es MP3 fijo (`audio-24khz-48kbitrate-mono-mp3`).
- Pruebas unitarias aisladas de los proveedores y documentación de configuración por modelo.

### Changed

- La respuesta TTS identifica el formato y tipo MIME reales del audio producido.
- El README documenta las rutas, ajustes compatibles y selección de los modelos ElevenLabs 2.5, v4, v4 Turbo y Microsoft Edge TTS.
