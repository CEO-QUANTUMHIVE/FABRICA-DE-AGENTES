# Fábrica de Agentes — QuantumHive

Acá vive **quién es** cada agente: su identidad, sus datos, su voz y lo que
puede hacer. Un negocio, un agente.

**Este repo no es el motor de voz.** Trae una copia adentro, pero lo que lo
define es la parte multi-negocio: los tenants, sus prompts, sus servicios, sus
voces y sus herramientas.

> **Si venís a usar el motor de voz para otro producto, no es acá.**
> Es [`SOLO-MOTOR-DE-VOZ-`](https://github.com/CEO-QUANTUMHIVE/SOLO-MOTOR-DE-VOZ-),
> que tiene el motor aislado, con sus recetas y sus trampas.

## Cómo se reparte

```
QuantumCore          orquesta y recuerda. No habla.
     ↓
FÁBRICA DE AGENTES   este repo. Quién es el agente, qué sabe, qué puede hacer.
     ↓
MOTOR DE VOZ         sostiene la conversación. No sabe de negocios.
```

## Qué hay adentro

| | |
|---|---|
| `brain/` | El cerebro: prompt, contexto, tenants y tools. **No importa livekit** |
| `voice/` | El canal: los tres motores, la sesión de LiveKit |
| `api/` | Reparte los tokens y resuelve de qué negocio es cada visitante |
| `frontend/widget/` | Lo que se pega en la landing de un cliente |
| `supabase/migrations/` | El esquema |

## Arrancar

```bash
.\arrancar.ps1
```

## Leé esto antes de tocar nada

| | |
|---|---|
| **[CLAUDE.md](CLAUDE.md)** | Las reglas. La 0 dice qué está en producción y cómo agregar un producto sin romperlo |
| **[docs/CONTINUAR-ACA.md](docs/CONTINUAR-ACA.md)** | El estado, qué falta y en qué orden |
| **[docs/procesos/](docs/procesos/README.md)** | Cómo se hace cada cosa. Cada runbook existe porque eso costó horas |

## Tests

```bash
uv run pytest
```

252 que no llaman a ninguna API. Los que sí gastan van con `-m smoke` o
`-m integracion` y no corren por defecto.
