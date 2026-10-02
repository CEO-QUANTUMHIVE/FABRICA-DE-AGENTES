# Entrar a la VM de Oracle

**Cuándo:** cualquier operación sobre la infra que corre en Oracle Cloud —
contenedores `qh-*`, túneles, rebuild del motor.

## Los datos

| | |
|---|---|
| Host | `150.136.89.118` (Oracle Cloud, Ampere A1, Always Free) |
| Usuario | `ubuntu` |
| Hostname | `quantumhive` |
| Ubuntu | 24.04.4 LTS |

`opc` no funciona: Oracle responde *"Please login as the user ubuntu"*.

## Camino 1 — SSH (el que usan los agentes)

```powershell
ssh -i "C:\Users\sergio\.ssh\quantumcore_oracle" ubuntu@150.136.89.118
```

- La clave `quantumcore_oracle` está instalada en `~/.ssh/authorized_keys`
  de la VM desde el 2026-09-27. Antes de esa fecha **no entraba** y el error
  era `Permission denied (publickey)`: no es que la clave esté mal, es que
  la clave pública no estaba en la VM.
- Si OpenSSH se queja de permisos en Windows
  (`UNPROTECTED PRIVATE KEY FILE`), arreglarlo con:

  ```powershell
  icacls "C:\Users\sergio\.ssh\quantumcore_oracle" /inheritance:r /grant:r "${env:USERNAME}:F"
  ```

- Alternativa con otra clave (también válida):
  `C:\Users\sergio\Desktop\QUANTUMHIVE FEDERADO\.tmp-perfilador-oracle.key`

## Camino 2 — Escritorio remoto (RDP)

1. Doble click en `C:\Users\sergio\Desktop\CONECTAR-ESCRITORIO-ORACLE.bat`
   (abre un túnel SSH `-L 3390:localhost:3389`; **no cerrar la ventana**).
2. `Win + R` → `mstsc` → Equipo: `localhost:3390` → usuario `ubuntu`.
3. La clave RDP la tiene Sergio. **No está escrita en ningún archivo del
   repo** (el repo es público); si se comparte en un chat, rotarla.

## Qué hay corriendo ahí

- `qh-motor-voz-api-canary` — API del motor (solo `127.0.0.1:18081`).
- `qh-motor-voz-agent-canary` — agente LiveKit.
- `qh-motor-voz-worker` — worker de colas WhatsApp (`inbox`/`outbox`).
- `qh-landing-*`, `qh-webs-*`, `qh-scrap-*`, `qh-biblioteca-*` — canarios.
- Todos los `*-tunel` son **quick tunnels** de cloudflared: hostname
  `*.trycloudflare.com` efímero, sirve para probar, **nunca** para webhook
  de producción. La URL estable es un tunnel con nombre (ver
  [`webhook-de-meta.md`](webhook-de-meta.md)).

## Reglas

- Las imágenes del motor se buildean en la VM desde el repo público:
  `docker build -t quantumhive/motor-voz:<tag> .` en
  `/home/ubuntu/quantumhive/fabrica-de-agentes`.
- Al recrear contenedores: **renombrar el viejo como `respaldo-*` y pararlo,
  nunca borrarlo** hasta confirmar el nuevo en verde.
- La VM vieja de Google (`104.196.130.90`, proyecto `bubbly-stone-502214-u7`)
  quedó sin facturación y apagada; `voz.quantumhive.com.ar` apuntaba ahí.
