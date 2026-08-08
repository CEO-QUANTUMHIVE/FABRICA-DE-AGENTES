# Motor de Voz — Plan de Implementación, Fases 0 a 4

> **Para agentes ejecutores:** SUB-SKILL REQUERIDA: usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para ejecutar tarea por tarea. Los pasos usan checkbox (`- [ ]`) para seguimiento.

**Goal:** Dejar funcionando una conversación de voz completa en el navegador — el usuario habla, el agente entiende, responde y se lo puede interrumpir — con LiveKit self-hosteado, Groq para STT y LLM, y Fish Audio para TTS.

**Architecture:** Monolito modular en Python con dos paquetes de frontera dura: `voice/` (LiveKit, proveedores, sesión) y `brain/` (prompt y, más adelante, contexto y tools). `brain/` tiene prohibido importar `livekit`, y un test lo hace cumplir. En estas fases el cerebro es un prompt fijo: no hay base de datos ni multi-tenant todavía.

**Tech Stack:** Python 3.14 (resuelto por `uv`) · `uv` · `livekit-agents ~1.6` · `livekit-plugins-groq` · `livekit-plugins-fishaudio` · `livekit-plugins-silero` · `livekit-server 1.13.5` (binario Windows) · pytest

---

## Alcance de este plan

Cubre las **Fases 0 a 4** del spec `docs/superpowers/specs/2026-08-08-motor-voz-design.md`. Al terminar, el motor habla. Es software funcionando y probable por sí solo.

**Fuera de este plan** (van en planes propios): Fase 5-8 Supabase y multi-tenant, Fase 9 tools, Fase 10 límites y degradación, Fase 11 modo asíncrono.

## Entorno verificado (2026-08-08)

| Herramienta | Versión presente |
|---|---|
| Python | 3.13.13 en el sistema; `uv` resuelve 3.14.0 para el proyecto |
| uv | 0.11.8 |
| Node / npm | 24.15.0 / 11.12.1 |
| Docker | no instalado (no hace falta) |
| `livekit-server` | release 1.13.5 con binario `windows_amd64` nativo |

Las claves de Groq, Fish y Supabase ya están cargadas en `.env` y verificadas contra los proveedores.

## API verificada de los proveedores

Leída del código fuente de los plugins en `livekit/agents@main`, no de memoria:

```python
groq.STT(model="whisper-large-v3-turbo", language="es", api_key=...)
# OJO: language default es "en". Sin forzar "es" transcribe mal el español.

groq.LLM(model="openai/gpt-oss-20b", api_key=...)
# OJO: model default es "llama-3.3-70b-versatile", no gpt-oss.
# El plugin aplica reasoning_effort="low" automáticamente a los gpt-oss.

fishaudio.TTS(model="s2.1-pro", voice_id=..., latency_mode="low", api_key=...)
# latency_mode default es "balanced". Para Live queremos "low".
```

Los tres leen su clave de la variable de entorno si no se pasa explícita: `GROQ_API_KEY` y `FISH_API_KEY`.

## Estructura de archivos

```text
MOTOR-DE-VOZ/
├── pyproject.toml                     Task 1
├── src/motor_voz/
│   ├── __init__.py                    Task 1
│   ├── config.py                      Task 3   carga y valida el entorno
│   ├── brain/
│   │   ├── __init__.py                Task 2
│   │   └── prompt.py                  Task 7   prompt fijo del agente
│   └── voice/
│       ├── __init__.py                Task 2
│       ├── agente.py                  Task 9   entrypoint del worker
│       └── providers/
│           ├── __init__.py            Task 5
│           ├── stt.py                 Task 5   Groq STT
│           ├── llm.py                 Task 6   Groq LLM
│           └── tts.py                 Task 8   Fish TTS
├── tests/
│   ├── __init__.py                    Task 1
│   ├── test_frontera.py               Task 2   brain/ no importa livekit
│   ├── test_config.py                 Task 3
│   ├── test_providers.py              Tasks 5, 6, 8
│   ├── test_prompt.py                 Task 7
│   ├── smoke/
│   │   ├── __init__.py                Task 5
│   │   ├── test_stt_real.py           Task 5
│   │   ├── test_llm_real.py           Task 6
│   │   └── test_tts_real.py           Task 8
│   └── fixtures/
│       └── hola_es.wav                Task 5   grabación tuya en español
├── scripts/
│   ├── token.py                       Task 4   emite token de LiveKit
│   └── livekit/                       Task 4   binario descargado (ignorado)
└── frontend/demo/                     Task 10  cliente mínimo
```

**Responsabilidad de cada archivo:** `config.py` es el único que lee variables de entorno. Los módulos de `providers/` son el único lugar que conoce a Groq y a Fish. `agente.py` solo cablea piezas: no tiene lógica de negocio. `brain/prompt.py` no sabe que existe la voz.

---

## FASE 0 — Esqueleto y frontera

### Task 1: Proyecto Python y pytest corriendo

**Files:**
- Create: `pyproject.toml`
- Create: `src/motor_voz/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_humo.py`

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "quantumhive-motor-voz"
version = "0.1.0"
description = "Motor de voz multi-tenant de QuantumHive"
requires-python = ">=3.10"
dependencies = [
    "livekit-agents[groq,fishaudio,silero]~=1.6",
    "livekit-api>=1.0",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/motor_voz"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "smoke: llama APIs reales y consume creditos. No corre por defecto.",
]
addopts = "-m 'not smoke'"
```

- [ ] **Step 2: Crear los paquetes vacíos**

`src/motor_voz/__init__.py`:

```python
"""Motor de voz de QuantumHive."""

__version__ = "0.1.0"
```

`tests/__init__.py`: archivo vacío, sin contenido.

- [ ] **Step 3: Escribir un test de humo**

`tests/test_humo.py`:

```python
import motor_voz


def test_el_paquete_se_importa():
    assert motor_voz.__version__ == "0.1.0"
```

- [ ] **Step 4: Instalar el entorno**

```bash
uv sync
```

Esperado: crea `.venv/` e instala livekit-agents con los tres plugins.

Si falla por la version de Python, crear el entorno con 3.12 y reintentar:

```bash
uv venv --python 3.12
```

- [ ] **Step 5: Correr el test**

```bash
uv run pytest -v
```

Esperado: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/motor_voz/__init__.py tests/__init__.py tests/test_humo.py
git commit -m "feat(fase0): esqueleto del proyecto Python con pytest"
```

---

### Task 2: Test de frontera entre brain/ y voice/

Este es el test más importante del proyecto. Impide que el cerebro se acople al transporte de audio, que es lo que permitirá reusar el motor en WhatsApp, Telegram y el asistente de escritorio.

**Files:**
- Create: `tests/test_frontera.py`
- Create: `src/motor_voz/brain/__init__.py`
- Create: `src/motor_voz/voice/__init__.py`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_frontera.py`:

```python
"""La frontera dura del motor.

brain/ contiene el cerebro: contexto, prompts, tools y datos del negocio.
voice/ contiene el canal: LiveKit, STT, TTS y la sesion de audio.

brain/ NO puede depender de voice/ ni de livekit. Si lo hiciera, el modo
asincrono (WhatsApp, Telegram) y el asistente de escritorio no podrian
reusar el cerebro, porque esos canales no pasan por LiveKit.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BRAIN = RAIZ / "src" / "motor_voz" / "brain"
PROHIBIDOS = ("livekit", "motor_voz.voice")


def modulos_del_brain() -> list[pathlib.Path]:
    return sorted(BRAIN.rglob("*.py"))


def imports_de(ruta: pathlib.Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.append(nodo.module)
    return nombres


def test_el_paquete_brain_existe_y_tiene_modulos():
    """Sin esta guarda, el test de abajo pasaria sin revisar nada."""
    assert BRAIN.is_dir(), f"No existe el paquete brain en {BRAIN}"
    assert modulos_del_brain(), "brain/ no tiene ningun modulo .py para revisar"


@pytest.mark.parametrize("ruta", modulos_del_brain(), ids=lambda p: p.name)
def test_brain_no_importa_livekit_ni_voice(ruta: pathlib.Path):
    for nombre in imports_de(ruta):
        for prohibido in PROHIBIDOS:
            assert not (nombre == prohibido or nombre.startswith(prohibido + ".")), (
                f"{ruta.relative_to(RAIZ)} importa '{nombre}'.\n"
                f"brain/ no puede depender de '{prohibido}'. "
                f"Si el cerebro necesita algo del canal, se pasa como argumento."
            )
```

- [ ] **Step 2: Correr el test para verificar que falla**

```bash
uv run pytest tests/test_frontera.py -v
```

Esperado: FALLA en `test_el_paquete_brain_existe_y_tiene_modulos` con "No existe el paquete brain".

- [ ] **Step 3: Crear los dos paquetes**

`src/motor_voz/brain/__init__.py`:

```python
"""Cerebro del motor: contexto, prompts, tools y datos del negocio.

REGLA: este paquete no importa livekit ni motor_voz.voice.
La hace cumplir tests/test_frontera.py.
"""
```

`src/motor_voz/voice/__init__.py`:

```python
"""Canal de voz: LiveKit, proveedores de STT y TTS, sesion de audio."""
```

- [ ] **Step 4: Correr el test para verificar que pasa**

```bash
uv run pytest tests/test_frontera.py -v
```

Esperado: `2 passed`.

- [ ] **Step 5: Verificar que el test realmente atrapa violaciones**

Agregar temporalmente al final de `src/motor_voz/brain/__init__.py`:

```python
import livekit  # PRUEBA TEMPORAL - borrar
```

Correr `uv run pytest tests/test_frontera.py -v`.

Esperado: FALLA con "brain/__init__.py importa 'livekit'".

**Borrar esa línea** y volver a correr. Esperado: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_frontera.py src/motor_voz/brain/__init__.py src/motor_voz/voice/__init__.py
git commit -m "feat(fase0): frontera dura brain/ vs voice/ con test que la hace cumplir"
```

---

### Task 3: Configuración validada

**Files:**
- Create: `src/motor_voz/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_config.py`:

```python
import pytest

from motor_voz.config import Config, ConfigInvalida, cargar

ENTORNO_COMPLETO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secret",
}


def test_carga_un_entorno_completo():
    config = cargar(ENTORNO_COMPLETO)
    assert isinstance(config, Config)
    assert config.groq_api_key == "gsk_falsa"
    assert config.livekit_url == "ws://localhost:7880"


def test_aplica_los_defaults_del_spec():
    config = cargar(ENTORNO_COMPLETO)
    assert config.stt_model == "whisper-large-v3-turbo"
    assert config.llm_model == "openai/gpt-oss-20b"
    assert config.fish_model == "s2.1-pro"
    assert config.fish_latency_mode == "low"
    assert config.idioma == "es"
    assert config.max_session_seconds == 240


def test_permite_pisar_los_defaults():
    entorno = ENTORNO_COMPLETO | {"FISH_MODEL": "s2.1-pro-free", "IDIOMA": "en"}
    config = cargar(entorno)
    assert config.fish_model == "s2.1-pro-free"
    assert config.idioma == "en"


def test_falla_y_nombra_todas_las_variables_faltantes():
    entorno = {"GROQ_API_KEY": "gsk_falsa"}
    with pytest.raises(ConfigInvalida) as error:
        cargar(entorno)
    mensaje = str(error.value)
    assert "FISH_API_KEY" in mensaje
    assert "LIVEKIT_URL" in mensaje
    assert "GROQ_API_KEY" not in mensaje


def test_una_variable_vacia_cuenta_como_faltante():
    entorno = ENTORNO_COMPLETO | {"FISH_API_KEY": "   "}
    with pytest.raises(ConfigInvalida) as error:
        cargar(entorno)
    assert "FISH_API_KEY" in str(error.value)


def test_la_config_es_inmutable():
    config = cargar(ENTORNO_COMPLETO)
    with pytest.raises(Exception):
        config.groq_api_key = "otra"  # type: ignore[misc]
```

- [ ] **Step 2: Correr para verificar que fallan**

```bash
uv run pytest tests/test_config.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.config'`.

- [ ] **Step 3: Implementar `config.py`**

`src/motor_voz/config.py`:

```python
"""Unico punto del motor que lee variables de entorno.

Ningun otro modulo debe llamar a os.environ. Todo recibe un Config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

OBLIGATORIAS = (
    "GROQ_API_KEY",
    "FISH_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
)


class ConfigInvalida(RuntimeError):
    """El entorno no tiene lo minimo para arrancar el motor."""


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    fish_api_key: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    stt_model: str
    llm_model: str
    fish_model: str
    fish_latency_mode: str
    fish_voice_id: str
    idioma: str
    max_session_seconds: int


def cargar(entorno: dict[str, str] | None = None) -> Config:
    e = dict(os.environ) if entorno is None else entorno

    faltantes = [n for n in OBLIGATORIAS if not (e.get(n) or "").strip()]
    if faltantes:
        raise ConfigInvalida(
            "Faltan variables de entorno obligatorias: "
            + ", ".join(faltantes)
            + ". Copiar .env.example a .env y completarlas."
        )

    return Config(
        groq_api_key=e["GROQ_API_KEY"].strip(),
        fish_api_key=e["FISH_API_KEY"].strip(),
        livekit_url=e["LIVEKIT_URL"].strip(),
        livekit_api_key=e["LIVEKIT_API_KEY"].strip(),
        livekit_api_secret=e["LIVEKIT_API_SECRET"].strip(),
        stt_model=e.get("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
        llm_model=e.get("GROQ_LLM_MODEL", "openai/gpt-oss-20b"),
        fish_model=e.get("FISH_MODEL", "s2.1-pro"),
        fish_latency_mode=e.get("FISH_LATENCY_MODE", "low"),
        fish_voice_id=e.get("FISH_VOICE_ID", ""),
        idioma=e.get("IDIOMA", "es"),
        max_session_seconds=int(e.get("MAX_SESSION_SECONDS", "240")),
    )
```

- [ ] **Step 4: Correr para verificar que pasan**

```bash
uv run pytest tests/test_config.py -v
```

Esperado: `6 passed`.

- [ ] **Step 5: Agregar las variables nuevas a `.env.example`**

Agregar debajo del bloque de Fish en `.env.example`:

```bash
FISH_VOICE_ID=
IDIOMA=es
```

- [ ] **Step 6: Commit**

```bash
git add src/motor_voz/config.py tests/test_config.py .env.example
git commit -m "feat(fase0): config validada con defaults del spec"
```

---

## FASE 1 — LiveKit self-hosteado corriendo

### Task 4: Servidor LiveKit local y emisión de tokens

**Files:**
- Create: `scripts/emitir_token.py`
- Create: `scripts/arrancar-livekit.md`
- Modify: `.env` (local, no se commitea)

- [ ] **Step 1: Descargar el binario de LiveKit**

En PowerShell, desde la raíz del repo:

```powershell
New-Item -ItemType Directory -Force scripts\livekit
Invoke-WebRequest -Uri "https://github.com/livekit/livekit/releases/download/v1.13.5/livekit_1.13.5_windows_amd64.zip" -OutFile "scripts\livekit\livekit.zip"
Expand-Archive -Path "scripts\livekit\livekit.zip" -DestinationPath "scripts\livekit" -Force
```

Verificar:

```powershell
.\scripts\livekit\livekit-server.exe --version
```

Esperado: imprime `livekit-server version 1.13.5`.

`scripts/livekit/` ya está cubierto por `.gitignore` a través de la regla de artefactos; confirmar con `git status` que no aparece. Si aparece, agregar `scripts/livekit/` al `.gitignore`.

- [ ] **Step 2: Arrancar el servidor en modo desarrollo**

En una terminal aparte, que queda abierta:

```powershell
.\scripts\livekit\livekit-server.exe --dev
```

Esperado: arranca en el puerto 7880 e imprime las credenciales de desarrollo, que son fijas:

```text
API Key: devkey
API Secret: secret
```

- [ ] **Step 3: Cargar esas credenciales en `.env`**

Completar en el `.env` local:

```bash
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

- [ ] **Step 4: Escribir el script que emite tokens**

`scripts/emitir_token.py`:

```python
"""Emite un token de acceso a una sala de LiveKit.

En produccion esto vive en un endpoint del backend que ademas valida el
tenant y aplica los limites. Para desarrollo alcanza con este script.

Uso:
    uv run python scripts/emitir_token.py sala-demo visitante
"""

from __future__ import annotations

import sys

from livekit import api

from motor_voz.config import cargar


def emitir(sala: str, identidad: str) -> str:
    config = cargar()
    concesion = api.VideoGrants(room_join=True, room=sala, can_publish=True, can_subscribe=True)
    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identidad)
        .with_name(identidad)
        .with_grants(concesion)
    )
    return token.to_jwt()


if __name__ == "__main__":
    sala = sys.argv[1] if len(sys.argv) > 1 else "sala-demo"
    identidad = sys.argv[2] if len(sys.argv) > 2 else "visitante"
    print(emitir(sala, identidad))
```

- [ ] **Step 5: Verificar que emite un token**

```bash
uv run python scripts/emitir_token.py sala-demo visitante
```

Esperado: imprime un JWT largo que empieza con `eyJ`.

- [ ] **Step 6: Documentar el arranque**

`scripts/arrancar-livekit.md`:

```markdown
# Arrancar LiveKit en desarrollo

1. Terminal 1 — servidor de medios:

       .\scripts\livekit\livekit-server.exe --dev

   Queda escuchando en ws://localhost:7880 con credenciales fijas
   devkey / secret.

2. Terminal 2 — agente:

       uv run python -m motor_voz.voice.agente dev

3. Terminal 3 — frontend demo:

       cd frontend/demo && npm run dev

El servidor en modo --dev no persiste nada y no usa TLS. Para produccion
va el mismo binario en un VPS con dominio, certificado y puertos UDP
abiertos para el media WebRTC.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/emitir_token.py scripts/arrancar-livekit.md
git commit -m "feat(fase1): livekit-server local y emision de tokens"
```

**Gate de la Fase 1:** el servidor arranca, `--version` responde 1.13.5, y el script emite un JWT válido.

---

## FASE 2 — Groq STT en español

### Task 5: Proveedor de STT

**Files:**
- Create: `src/motor_voz/voice/providers/__init__.py`
- Create: `src/motor_voz/voice/providers/stt.py`
- Create: `tests/test_providers.py`
- Create: `tests/smoke/__init__.py`
- Create: `tests/smoke/test_stt_real.py`
- Create: `tests/fixtures/hola_es.wav`

- [ ] **Step 1: Grabar el audio de prueba**

Grabar **10 a 15 segundos** de tu propia voz, en un ambiente silencioso, diciendo exactamente:

> "Hola, ¿cómo andás? Mirá, para el sábado tenemos lugar a las cuatro y media, ¿te sirve? Si querés te lo reservo ahora y listo."

Guardarlo como `tests/fixtures/hola_es.wav`, formato WAV mono 16 kHz si es posible.

Esta grabación cumple dos funciones: es el fixture del test de transcripción, y va a ser la **muestra de referencia para clonar tu acento rioplatense** cuando llegue esa etapa. Vale la pena que salga limpia.

- [ ] **Step 2: Escribir el test unitario que falla**

`tests/test_providers.py`:

```python
from motor_voz.config import cargar
from motor_voz.voice.providers import stt

ENTORNO = {
    "GROQ_API_KEY": "gsk_falsa",
    "FISH_API_KEY": "sk-falsa",
    "LIVEKIT_URL": "ws://localhost:7880",
    "LIVEKIT_API_KEY": "devkey",
    "LIVEKIT_API_SECRET": "secret",
}


def test_opciones_stt_fuerzan_espanol():
    """El default del plugin es 'en'. Si no lo forzamos, transcribe mal."""
    opciones = stt.opciones(cargar(ENTORNO))
    assert opciones["language"] == "es"


def test_opciones_stt_usan_el_modelo_del_spec():
    opciones = stt.opciones(cargar(ENTORNO))
    assert opciones["model"] == "whisper-large-v3-turbo"


def test_opciones_stt_pasan_la_clave():
    opciones = stt.opciones(cargar(ENTORNO))
    assert opciones["api_key"] == "gsk_falsa"


def test_crear_stt_devuelve_un_stt_de_groq():
    from livekit.plugins import groq

    assert isinstance(stt.crear(cargar(ENTORNO)), groq.STT)
```

- [ ] **Step 3: Correr para verificar que falla**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.voice.providers'`.

- [ ] **Step 4: Implementar el proveedor**

`src/motor_voz/voice/providers/__init__.py`:

```python
"""Proveedores externos del canal de voz.

Unico lugar del motor que conoce a Groq y a Fish Audio. Cada modulo expone
`opciones(config)` — puro y testeable sin red — y `crear(config)`, que
construye el objeto del plugin.
"""
```

`src/motor_voz/voice/providers/stt.py`:

```python
"""Transcripcion con Groq Whisper."""

from __future__ import annotations

from typing import Any

from livekit.plugins import groq

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El plugin trae language='en' por defecto: hay que forzar el idioma."""
    return {
        "model": config.stt_model,
        "language": config.idioma,
        "api_key": config.groq_api_key,
    }


def crear(config: Config) -> groq.STT:
    return groq.STT(**opciones(config))
```

- [ ] **Step 5: Correr para verificar que pasa**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: `4 passed`.

- [ ] **Step 6: Escribir el smoke test contra la API real**

`tests/smoke/__init__.py`: archivo vacío.

`tests/smoke/test_stt_real.py`:

```python
"""Llama a la API real de Groq. Cuesta fracciones de centavo.

Correr con:  uv run pytest -m smoke tests/smoke/test_stt_real.py -v -s
"""

from __future__ import annotations

import pathlib
import wave

import pytest

from livekit import rtc

from motor_voz.config import cargar
from motor_voz.voice.providers import stt

FIXTURE = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "hola_es.wav"


def cargar_wav(ruta: pathlib.Path) -> rtc.AudioFrame:
    """Lee un wav con la stdlib y arma un AudioFrame, sin helpers del SDK."""
    with wave.open(str(ruta), "rb") as w:
        assert w.getsampwidth() == 2, "El wav tiene que ser PCM de 16 bits"
        canales = w.getnchannels()
        frecuencia = w.getframerate()
        cantidad = w.getnframes()
        datos = w.readframes(cantidad)
    return rtc.AudioFrame(
        data=datos,
        sample_rate=frecuencia,
        num_channels=canales,
        samples_per_channel=cantidad,
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_transcribe_espanol_rioplatense():
    assert FIXTURE.exists(), f"Falta la grabacion de prueba en {FIXTURE}"

    motor = stt.crear(cargar())
    evento = await motor.recognize(cargar_wav(FIXTURE))
    texto = " ".join(alt.text for alt in evento.alternatives).lower()
    print(f"\nTranscripcion: {texto}\n")

    assert texto.strip(), "Groq devolvio texto vacio"
    assert "sabado" in texto or "sábado" in texto, f"No reconocio 'sabado' en: {texto}"
    assert "reservo" in texto, f"No reconocio 'reservo' en: {texto}"
```

- [ ] **Step 7: Correr el smoke test**

```bash
uv run pytest -m smoke tests/smoke/test_stt_real.py -v -s
```

Esperado: imprime la transcripción y pasa. Si el helper de carga de audio no coincide con la versión instalada, el test hace `skip` con un mensaje claro: ajustar la carga del wav según `livekit.agents.utils` de la versión instalada y volver a correr hasta que pase.

**Leer la transcripción impresa.** Si el voseo ("andás", "querés") sale mal, anotarlo: es un dato para la Fase 4.

- [ ] **Step 8: Commit**

```bash
git add src/motor_voz/voice/providers tests/test_providers.py tests/smoke tests/fixtures/hola_es.wav
git commit -m "feat(fase2): Groq STT en espanol con smoke test real"
```

**Gate de la Fase 2:** la transcripción del audio en español es correcta y reconoce el voseo.

---

## FASE 3 — Groq LLM

### Task 6: Proveedor de LLM

**Files:**
- Create: `src/motor_voz/voice/providers/llm.py`
- Modify: `tests/test_providers.py`
- Create: `tests/smoke/test_llm_real.py`

- [ ] **Step 1: Agregar los tests que fallan**

Agregar al final de `tests/test_providers.py`:

```python
from motor_voz.voice.providers import llm


def test_opciones_llm_usan_gpt_oss_y_no_el_default_del_plugin():
    """El default del plugin es llama-3.3-70b-versatile."""
    opciones = llm.opciones(cargar(ENTORNO))
    assert opciones["model"] == "openai/gpt-oss-20b"


def test_opciones_llm_pasan_la_clave():
    opciones = llm.opciones(cargar(ENTORNO))
    assert opciones["api_key"] == "gsk_falsa"


def test_crear_llm_devuelve_un_llm_de_groq():
    from livekit.plugins import groq

    assert isinstance(llm.crear(cargar(ENTORNO)), groq.LLM)
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: FALLA con `ImportError: cannot import name 'llm'`.

- [ ] **Step 3: Implementar el proveedor**

`src/motor_voz/voice/providers/llm.py`:

```python
"""Generacion de respuestas con Groq.

El plugin aplica reasoning_effort='low' automaticamente a los modelos
gpt-oss, lo que reduce el consumo de tokens.
"""

from __future__ import annotations

from typing import Any

from livekit.plugins import groq

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El default del plugin es llama-3.3: hay que pedir gpt-oss explicito."""
    return {
        "model": config.llm_model,
        "api_key": config.groq_api_key,
    }


def crear(config: Config) -> groq.LLM:
    return groq.LLM(**opciones(config))
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: `7 passed`.

- [ ] **Step 5: Escribir el smoke test**

`tests/smoke/test_llm_real.py`:

```python
"""Llama a la API real de Groq.

Correr con:  uv run pytest -m smoke tests/smoke/test_llm_real.py -v -s
"""

from __future__ import annotations

import pytest

from motor_voz.config import cargar
from motor_voz.voice.providers import llm


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_responde_en_espanol_y_breve():
    from livekit.agents.llm import ChatContext

    modelo = llm.crear(cargar())
    contexto = ChatContext()
    contexto.add_message(
        role="system",
        content="Sos el asistente de QuantumHive. Respondes en espanol rioplatense, "
        "en una sola oracion corta, sin emojis ni markdown.",
    )
    contexto.add_message(role="user", content="Hola, que hacen ustedes?")

    partes: list[str] = []
    async with modelo.chat(chat_ctx=contexto) as stream:
        async for fragmento in stream:
            if fragmento.delta and fragmento.delta.content:
                partes.append(fragmento.delta.content)

    respuesta = "".join(partes).strip()
    print(f"\nRespuesta: {respuesta}\n")

    assert respuesta, "El modelo devolvio texto vacio"
    assert len(respuesta) < 400, f"Demasiado largo para voz ({len(respuesta)} chars)"
    assert "*" not in respuesta, "Devolvio markdown, que no se puede hablar"
```

- [ ] **Step 6: Correr el smoke test**

```bash
uv run pytest -m smoke tests/smoke/test_llm_real.py -v -s
```

Esperado: imprime una respuesta breve en español y pasa.

- [ ] **Step 7: Commit**

```bash
git add src/motor_voz/voice/providers/llm.py tests/test_providers.py tests/smoke/test_llm_real.py
git commit -m "feat(fase3): Groq LLM con gpt-oss-20b y smoke test real"
```

---

### Task 7: Prompt fijo del agente en brain/

**Files:**
- Create: `src/motor_voz/brain/prompt.py`
- Create: `tests/test_prompt.py`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_prompt.py`:

```python
from motor_voz.brain.prompt import PROMPT_QUANTUMHIVE, construir


def test_el_prompt_pide_respuestas_habladas_y_breves():
    texto = construir().lower()
    assert "breve" in texto or "corta" in texto
    assert "voz" in texto or "hablado" in texto


def test_el_prompt_prohibe_markdown_y_emojis():
    texto = construir().lower()
    assert "markdown" in texto
    assert "emoji" in texto


def test_el_prompt_prohibe_inventar_datos():
    texto = construir().lower()
    assert "invent" in texto


def test_el_prompt_es_compacto():
    """El costo por conversacion sube con cada token del system prompt."""
    assert len(construir()) < 1600, "El prompt fijo crecio demasiado"


def test_construir_permite_agregar_contexto():
    texto = construir("El visitante viene de la campana de Instagram.")
    assert "Instagram" in texto
    assert PROMPT_QUANTUMHIVE in texto
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_prompt.py -v
```

Esperado: FALLA con `ModuleNotFoundError: No module named 'motor_voz.brain.prompt'`.

- [ ] **Step 3: Implementar el prompt**

`src/motor_voz/brain/prompt.py`:

```python
"""Prompt fijo del agente receptor de QuantumHive.

En las fases 5 a 7 esto se reemplaza por un contexto armado desde Supabase
con el perfil del rubro y los datos del tenant. Por ahora es fijo.

Este modulo no sabe que existe la voz ni LiveKit: solo produce texto.
"""

from __future__ import annotations

PROMPT_QUANTUMHIVE = (
    "Sos el asistente virtual de QuantumHive, una empresa argentina que le da "
    "vida digital a los negocios: les hace la web, les arma un empleado virtual "
    "que atiende clientes, les da voz, avatar y un catalogo que vende.\n"
    "\n"
    "Hablas espanol rioplatense, de vos, natural y cercano. Nunca de tu ni de usted.\n"
    "\n"
    "Tus respuestas se van a convertir en voz, asi que:\n"
    "- Responde breve, una o dos oraciones. Nunca listas largas.\n"
    "- No uses markdown, asteriscos, emojis ni simbolos que no se puedan hablar.\n"
    "- Escribi los numeros como se pronuncian.\n"
    "\n"
    "Nunca inventes precios, plazos ni datos del negocio. Si no lo sabes, decilo "
    "y ofrece que un humano lo contacte.\n"
    "\n"
    "Tu objetivo es entender que necesita el visitante y despertarle ganas de "
    "tener su propio negocio digital vivo."
)


def construir(contexto_extra: str = "") -> str:
    """Arma el system prompt final.

    Args:
        contexto_extra: informacion adicional de la sesion. Vacio por defecto.
    """
    if not contexto_extra.strip():
        return PROMPT_QUANTUMHIVE
    return f"{PROMPT_QUANTUMHIVE}\n\nContexto de esta conversacion:\n{contexto_extra.strip()}"
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_prompt.py -v
```

Esperado: `5 passed`.

- [ ] **Step 5: Verificar que la frontera sigue en pie**

```bash
uv run pytest tests/test_frontera.py -v
```

Esperado: `3 passed` — ahora revisa también `prompt.py`.

- [ ] **Step 6: Commit**

```bash
git add src/motor_voz/brain/prompt.py tests/test_prompt.py
git commit -m "feat(fase3): prompt fijo del agente receptor en brain/"
```

**Gate de la Fase 3:** el LLM responde en español rioplatense, breve y sin markdown.

---

## FASE 4 — Fish TTS y conversación completa

### Task 8: Proveedor de TTS

**Files:**
- Create: `src/motor_voz/voice/providers/tts.py`
- Modify: `tests/test_providers.py`
- Create: `tests/smoke/test_tts_real.py`

- [ ] **Step 1: Agregar los tests que fallan**

Agregar al final de `tests/test_providers.py`:

```python
from motor_voz.voice.providers import tts


def test_opciones_tts_usan_latencia_baja():
    """El default del plugin es 'balanced'. Para Live queremos 'low'."""
    opciones = tts.opciones(cargar(ENTORNO))
    assert opciones["latency_mode"] == "low"


def test_opciones_tts_usan_el_modelo_del_spec():
    opciones = tts.opciones(cargar(ENTORNO))
    assert opciones["model"] == "s2.1-pro"


def test_opciones_tts_omiten_voice_id_si_no_esta_configurado():
    """Sin voice_id, el plugin usa su voz por defecto en vez de romper."""
    opciones = tts.opciones(cargar(ENTORNO))
    assert "voice_id" not in opciones


def test_opciones_tts_incluyen_voice_id_si_esta_configurado():
    opciones = tts.opciones(cargar(ENTORNO | {"FISH_VOICE_ID": "voz-argentina-01"}))
    assert opciones["voice_id"] == "voz-argentina-01"


def test_crear_tts_devuelve_un_tts_de_fishaudio():
    from livekit.plugins import fishaudio

    assert isinstance(tts.crear(cargar(ENTORNO)), fishaudio.TTS)
```

- [ ] **Step 2: Correr para verificar que falla**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: FALLA con `ImportError: cannot import name 'tts'`.

- [ ] **Step 3: Implementar el proveedor**

`src/motor_voz/voice/providers/tts.py`:

```python
"""Sintesis de voz con Fish Audio.

Este modulo es el unico punto que conoce a Fish. Cuando se agregue el pool
de proveedores del spec, el router vive aca y el resto del motor no se entera.
"""

from __future__ import annotations

from typing import Any

from livekit.plugins import fishaudio

from motor_voz.config import Config


def opciones(config: Config) -> dict[str, Any]:
    """El default de latency_mode es 'balanced'; para Live queremos 'low'."""
    opts: dict[str, Any] = {
        "model": config.fish_model,
        "latency_mode": config.fish_latency_mode,
        "api_key": config.fish_api_key,
    }
    if config.fish_voice_id.strip():
        opts["voice_id"] = config.fish_voice_id.strip()
    return opts


def crear(config: Config) -> fishaudio.TTS:
    return fishaudio.TTS(**opciones(config))
```

- [ ] **Step 4: Correr para verificar que pasa**

```bash
uv run pytest tests/test_providers.py -v
```

Esperado: `12 passed`.

- [ ] **Step 5: Escribir el smoke test que genera audio**

`tests/smoke/test_tts_real.py`:

```python
"""Llama a la API real de Fish Audio y deja un wav para escuchar.

Correr con:  uv run pytest -m smoke tests/smoke/test_tts_real.py -v -s
"""

from __future__ import annotations

import pathlib

import pytest

from motor_voz.config import cargar
from motor_voz.voice.providers import tts

FRASE = (
    "Hola, como andas? Mira, para el sabado tenemos lugar a las cuatro y media, "
    "te sirve? Si queres te lo reservo ahora y listo."
)
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "salida_tts.wav"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_sintetiza_la_frase_de_prueba():
    motor = tts.crear(cargar())

    trozos: list[bytes] = []
    async with motor.synthesize(FRASE) as stream:
        async for evento in stream:
            trozos.append(evento.frame.data.tobytes())

    audio = b"".join(trozos)
    assert audio, "Fish devolvio audio vacio"

    SALIDA.write_bytes(audio)
    print(f"\nAudio generado en {SALIDA} ({len(audio)} bytes)\n")
    print(f"Bytes de texto facturados: {len(FRASE.encode('utf-8'))}")
```

- [ ] **Step 6: Correr el smoke test y ESCUCHAR el resultado**

```bash
uv run pytest -m smoke tests/smoke/test_tts_real.py -v -s
```

Esperado: genera `tests/fixtures/salida_tts.wav`.

**Abrir el archivo y escucharlo.** Evaluar:

- ¿Suena natural o robótico?
- ¿Dice "andás" y "querés" con entonación argentina, o lo lee como español neutro?
- ¿La "ll" y la "y" suenan rioplatenses?
- ¿Las pausas entre frases son naturales?

Si el acento no convence, probar con un `FISH_VOICE_ID` clonado a partir de `tests/fixtures/hola_es.wav`. **Esta evaluación es el gate de la fase, no un detalle.**

- [ ] **Step 7: Commit**

```bash
git add src/motor_voz/voice/providers/tts.py tests/test_providers.py tests/smoke/test_tts_real.py
git commit -m "feat(fase4): Fish Audio TTS con latencia baja y smoke test audible"
```

---

### Task 9: El agente completo

**Files:**
- Create: `src/motor_voz/voice/agente.py`

- [ ] **Step 1: Implementar el agente**

`src/motor_voz/voice/agente.py`:

```python
"""Worker de LiveKit: cablea el cerebro con el canal de voz.

Este archivo no tiene logica de negocio. Solo arma la sesion con los
proveedores y arranca. Todo lo que el agente sabe viene de brain/.
"""

from __future__ import annotations

import logging

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.plugins import silero

from motor_voz.brain.prompt import construir
from motor_voz.config import cargar
from motor_voz.voice.providers import llm as proveedor_llm
from motor_voz.voice.providers import stt as proveedor_stt
from motor_voz.voice.providers import tts as proveedor_tts

logger = logging.getLogger("motor-voz")


class Receptor(Agent):
    """Agente receptor de QuantumHive."""

    def __init__(self) -> None:
        super().__init__(instructions=construir())

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Saluda al visitante en una sola oracion corta y "
            "pregunta en que lo podes ayudar."
        )


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    config = cargar()
    ctx.log_context_fields = {"room": ctx.room.name}

    session: AgentSession = AgentSession(
        stt=proveedor_stt.crear(config),
        llm=proveedor_llm.crear(config),
        tts=proveedor_tts.crear(config),
        # Groq Whisper no hace endpointing: sin VAD el agente no sabe
        # cuando terminaste de hablar, y sin eso no hay interrupcion.
        vad=silero.VAD.load(),
    )

    @session.on("metrics_collected")
    def _metricas(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)

    async def registrar_uso() -> None:
        logger.info(f"Uso de la sesion: {session.usage}")

    ctx.add_shutdown_callback(registrar_uso)

    await session.start(
        agent=Receptor(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)
```

- [ ] **Step 2: Verificar que el módulo importa sin errores**

```bash
uv run python -c "import motor_voz.voice.agente; print('importa OK')"
```

Esperado: imprime `importa OK`. Si falla por un nombre que no existe en `livekit.agents`, ajustar el import según la versión instalada:

```bash
uv run python -c "import livekit.agents as a; print([n for n in dir(a) if not n.startswith('_')])"
```

- [ ] **Step 3: Verificar que la frontera sigue intacta**

```bash
uv run pytest -v
```

Esperado: todos los tests pasan, incluida la frontera. `agente.py` está en `voice/`, así que puede importar livekit; `brain/` sigue limpio.

- [ ] **Step 4: Arrancar el agente contra el servidor local**

Con `livekit-server --dev` corriendo en otra terminal:

```bash
uv run python -m motor_voz.voice.agente dev
```

Esperado: el worker se registra contra `ws://localhost:7880` y queda esperando sesiones.

- [ ] **Step 5: Commit**

```bash
git add src/motor_voz/voice/agente.py
git commit -m "feat(fase4): agente completo cableando brain/ con los proveedores"
```

---

### Task 10: Frontend demo mínimo

**Files:**
- Create: `frontend/demo/package.json`
- Create: `frontend/demo/index.html`
- Create: `frontend/demo/main.js`

- [ ] **Step 1: Crear el `package.json`**

`frontend/demo/package.json`:

```json
{
  "name": "motor-voz-demo",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite"
  },
  "dependencies": {
    "livekit-client": "^2.7.0"
  },
  "devDependencies": {
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: Crear el HTML**

`frontend/demo/index.html`:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Motor de Voz — Demo</title>
    <style>
      body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem; }
      button { font-size: 1rem; padding: 0.6rem 1.2rem; margin-right: 0.5rem; }
      #estado { margin-top: 1.5rem; font-size: 1.1rem; }
      input { width: 100%; padding: 0.5rem; font-family: monospace; font-size: 0.8rem; }
    </style>
  </head>
  <body>
    <h1>Motor de Voz — Demo</h1>
    <p>Pegá el token generado con <code>uv run python scripts/emitir_token.py</code>:</p>
    <input id="token" placeholder="eyJ..." />
    <p>
      <button id="conectar">Conectar</button>
      <button id="silenciar" disabled>Silenciar micrófono</button>
      <button id="cortar" disabled>Finalizar</button>
    </p>
    <div id="estado">desconectado</div>
    <script type="module" src="./main.js"></script>
  </body>
</html>
```

- [ ] **Step 3: Crear el cliente**

`frontend/demo/main.js`:

```javascript
import { Room, RoomEvent, Track } from 'livekit-client';

const URL_LIVEKIT = 'ws://localhost:7880';

const $ = (id) => document.getElementById(id);
const estado = (texto) => { $('estado').textContent = texto; };

let sala = null;

$('conectar').onclick = async () => {
  const token = $('token').value.trim();
  if (!token) { estado('falta el token'); return; }

  sala = new Room();

  sala.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === Track.Kind.Audio) {
      track.attach().play();
      estado('conectado — hablá');
    }
  });
  sala.on(RoomEvent.Disconnected, () => estado('desconectado'));

  estado('conectando...');
  await sala.connect(URL_LIVEKIT, token);
  await sala.localParticipant.setMicrophoneEnabled(true);
  estado('conectado — hablá');

  $('silenciar').disabled = false;
  $('cortar').disabled = false;
};

$('silenciar').onclick = async () => {
  const activo = sala.localParticipant.isMicrophoneEnabled;
  await sala.localParticipant.setMicrophoneEnabled(!activo);
  $('silenciar').textContent = activo ? 'Activar micrófono' : 'Silenciar micrófono';
};

$('cortar').onclick = async () => {
  await sala.disconnect();
  $('silenciar').disabled = true;
  $('cortar').disabled = true;
};
```

- [ ] **Step 4: Instalar y arrancar**

```bash
cd frontend/demo && npm install && npm run dev
```

Esperado: vite sirve en `http://localhost:5173`.

- [ ] **Step 5: Commit**

```bash
git add frontend/demo/package.json frontend/demo/index.html frontend/demo/main.js
git commit -m "feat(fase4): frontend demo minimo con livekit-client"
```

---

### Task 11: Prueba end-to-end y gate de la Fase 4

**Files:** ninguno — es verificación manual.

- [ ] **Step 1: Levantar las tres piezas**

Tres terminales:

```bash
# 1
.\scripts\livekit\livekit-server.exe --dev

# 2
uv run python -m motor_voz.voice.agente dev

# 3
cd frontend/demo && npm run dev
```

- [ ] **Step 2: Generar un token y conectarse**

```bash
uv run python scripts/emitir_token.py sala-demo visitante
```

Copiar el JWT, abrir `http://localhost:5173`, pegarlo y apretar Conectar. Dar permiso de micrófono.

- [ ] **Step 3: Verificar los seis criterios del gate**

- [ ] El agente saluda solo al entrar, sin que hables primero.
- [ ] Le hablás y entiende lo que dijiste en español.
- [ ] Responde algo coherente sobre QuantumHive.
- [ ] La respuesta se escucha con voz, no aparece solo como texto.
- [ ] **Lo interrumpís mientras habla y frena.** Este es el criterio decisivo.
- [ ] El acento es rioplatense, no español neutro.

- [ ] **Step 4: Registrar los tiempos**

En la terminal del agente, las métricas muestran latencias de STT, LLM y TTS. Anotarlas: son la línea de base para el resto del proyecto y la referencia de qué modo de Fish conviene.

- [ ] **Step 5: Documentar el resultado**

Crear `docs/resultados/fase4-primera-conversacion.md` con los tiempos medidos, la evaluación del acento y cualquier problema encontrado.

- [ ] **Step 6: Commit**

```bash
git add docs/resultados/
git commit -m "docs(fase4): resultados de la primera conversacion end-to-end"
```

**Gate de la Fase 4 — no se avanza a la Fase 5 sin esto:** el usuario habla, el agente entiende, responde, se lo escucha y **se lo puede interrumpir**.

---

## Qué sigue

Con las fases 0 a 4 cerradas, el motor habla con un prompt fijo. El plan siguiente cubre las fases 5 a 8: Supabase, tenants, resolver, capa única de repositorios, context builder dinámico y voz por tenant. El test de aislamiento multi-tenant de ese plan es bloqueante.

## Riesgos de este plan

| Riesgo | Señal temprana | Qué hacer |
|---|---|---|
| La version de Python que resuelva `uv` sin soporte en algun plugin | `uv sync` falla al resolver | `uv venv --python 3.12` y reintentar |
| Nombres de la API de `livekit.agents` cambiados en 1.6.x | El import de `agente.py` falla | Listar `dir(livekit.agents)` y ajustar; la estructura del ejemplo oficial `voice_agents/basic_agent.py` es la referencia |
| `silero.VAD.load()` tarda en arrancar | El worker demora unos segundos al primer arranque | Es esperado: descarga el modelo una vez. Si molesta, moverlo a un hook de prewarm |
| Acento neutro en el TTS | Se nota en el paso 6 de la Task 8 | Clonar voz con `hola_es.wav` y configurar `FISH_VOICE_ID` |
| El helper de carga de wav no coincide con la versión | El smoke test de STT hace skip | Ajustar según `livekit.agents.utils` instalado |
