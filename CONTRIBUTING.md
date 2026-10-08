# Contribuir a LVS Gateway

LVS Gateway es el backend de voz del ecosistema LVS. Este repositorio es público en GitHub y actualmente no declara una licencia. Esta guía documenta el flujo de trabajo del proyecto; la publicación del código no concede permisos de uso adicionales a los que establezca una licencia.

## Alcance y recursos

- Repositorio: <https://github.com/estebangesto/lvs-gateway>
- Issues: <https://github.com/estebangesto/lvs-gateway/issues>
- Pull Requests: <https://github.com/estebangesto/lvs-gateway/pulls>
- Instalación, configuración y API: [README.md](README.md)

Las propuestas y correcciones se coordinan mediante issues. Antes de empezar un cambio, verificá que tenga objetivo, alcance y criterios de aceptación claros. Las contribuciones externas deben acordarse en una issue antes de abrir una Pull Request.

## Entorno de desarrollo

### Requisitos

- Python 3.13.
- Acceso al Gateway de OpenClaw para pruebas de integración.
- `lvs-stt` activo para pruebas que envíen audio.
- Credenciales de ElevenLabs sólo para las pruebas de síntesis real.

No copies ni publiques archivos `.env`, tokens, claves ni salidas que puedan contener secretos. Para desarrollo local, usá los nombres y valores de ejemplo de `.env.example` y las alternativas locales documentadas en el README.

### Instalación

Desde la raíz del repositorio:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Completá `.env` sólo con valores locales necesarios para tu entorno. No agregues ese archivo al repositorio.

### Verificaciones

La comprobación estática disponible es:

```bash
.venv/bin/python -m compileall -q app
.venv/bin/python -m unittest -v test_openclaw_session
# Ejecutar cuando el módulo esté presente en la rama:
.venv/bin/python -m unittest -v test_tts
```

`test_openclaw_session.py` contiene pruebas unitarias que no contactan servicios externos. Los scripts `test_openclaw_connection.py` y `test_voice_system.py` son diagnósticos de integración: requieren servicios y/o credenciales locales y pueden enviar solicitudes reales. Ejecutalos sólo cuando la prueba correspondiente esté preparada.

El workflow de GitHub Actions ejecuta estas verificaciones para los Pull Requests dirigidos a `develop` o `main`. No usa credenciales ni servicios externos. Los PR deben indicar las verificaciones ejecutadas y los riesgos.

## Issues y Pull Requests

1. Abrí o seleccioná una issue para cada cambio funcional, corrección o tarea de documentación relevante.
2. Creá una rama de trabajo desde `develop` con la convención indicada abajo.
3. Mantené los cambios acotados a la issue y agregá o actualizá verificaciones y documentación cuando corresponda.
4. Abrí una Pull Request hacia `develop`, con resumen, pruebas ejecutadas, riesgos y `Refs #N`.
5. Esperá la revisión aprobada, los checks requeridos y la resolución de las conversaciones antes de integrar.
6. Integrá ramas `feature` y `fix` mediante *squash merge*.

No integres directamente en `main`. No se debe asumir que una rama está protegida: las reglas de protección se verifican en GitHub y su configuración debe documentarse cuando se adopte.

## Ramas y releases

| Rama | Origen | Destino/uso |
|---|---|---|
| `main` | — | Historial publicado y versiones estables. |
| `develop` | `main` al adoptar el flujo | Integración de la próxima versión. |
| `feature/<issue>-<resumen>` | `develop` | Funcionalidad nueva; PR hacia `develop`. |
| `fix/<issue>-<resumen>` | `develop` | Corrección ordinaria; PR hacia `develop`. |
| `release/vX.Y.Z` | `develop` | Estabilización; PR hacia `main`. |
| `hotfix/vX.Y.Z` | `main` | Corrección crítica; PR hacia `main`. |

Usá Conventional Commits con el tipo normalizado en inglés y una descripción en español, por ejemplo `feat(tts): agregar proveedor seleccionable` o `docs: documentar el flujo de contribución`.

Las versiones estables siguen Semantic Versioning. Una funcionalidad compatible incrementa MINOR; una corrección compatible incrementa PATCH; un cambio incompatible incrementa MAJOR. Las versiones publicadas usan un tag anotado `vX.Y.Z` y una GitHub Release asociada.

### Publicación

1. Creá `release/vX.Y.Z` desde `develop` cuando el alcance esté completo.
2. Actualizá `CHANGELOG.md` con los cambios incluidos y la fecha de publicación.
3. Abrí un PR desde `release/vX.Y.Z` hacia `main`; vinculá las issues publicadas con `Closes #N`.
4. Integrá releases mediante *merge commit*, después de revisión y checks aprobados.
5. Creá y publicá el tag anotado y la GitHub Release sobre el commit integrado en `main`.
6. Abrí un PR de sincronización `main` → `develop` e integralo mediante *merge commit*.
7. Eliminá ramas temporales sólo después de verificar la integración y la sincronización.

Los hotfixes siguen el mismo procedimiento de publicación desde `main` y deben sincronizarse posteriormente hacia `develop`. No uses force-push, no descartes trabajo y no elimines ramas sin autorización explícita.

## Convenciones

- Escribí issues, PRs, commits y documentación del proyecto en español.
- No incluyas secretos, información personal ni logs crudos en issues o PRs.
- Actualizá documentación y changelog cuando el cambio afecte el uso, la configuración o la publicación.
- Mantené las pruebas automatizadas independientes de servicios externos; las integraciones reales deben quedar identificadas como tales.

## Estado de adopción

La versión publicada vigente al preparar esta guía es `v0.1.0`. Se inicializa `develop` desde `main` para el siguiente ciclo, cuyo objetivo declarado es `v0.2.0`. La existencia de una rama o workflow no implica por sí sola que GitHub tenga protecciones o checks requeridos configurados.
