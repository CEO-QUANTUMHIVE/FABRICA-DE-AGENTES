# Probar un tenant a oído

El gate de las Fases 5-8 tiene cinco puntos y cuatro los cubren los tests. El
quinto —que cada negocio hable con **su** voz— no se puede automatizar: hay
que escucharlo.

## Levantar todo en local

```bash
cd "C:\Users\sergio\Desktop\FABRICA-DE-AGENTES"; .\arrancar.ps1
```

Abre cuatro ventanas y el navegador en `localhost:5173`. Los errores salen en
la ventana **AGENTE**.

## Escuchar cada tenant

| Quién | URL |
|---|---|
| QuantumHive | `http://localhost:5173/` |
| Barbería demo | `http://localhost:5173/?tenant=demo_capilar` |

Sin parámetro el backend usa `quantumhive`, que es el default.

## Tiene que ser el NIVEL 1

**Esto es lo que más confunde.** La voz del tenant es la clonada de Fish, y
esa solo la usa el pipeline. Gemini y OpenAI hablan con una voz de su propio
catálogo, elegida en el selector — el tenant no la toca.

Si probás en nivel 2 o 3 vas a escuchar la misma voz en los dos negocios y va
a parecer que el aislamiento está roto. **No lo está: estás probando mal.**

## Qué escuchar

- **QuantumHive** saluda como QuantumHive y ofrece web inteligente y empleado
  virtual. Nunca menciona cortes de pelo.
- **La barbería** saluda como barbería y ofrece corte clásico y afeitado a
  navaja. Nunca menciona a QuantumHive como negocio propio.
- **Las dos voces suenan distintas.** Si suenan igual, el `voice_id` de alguno
  no existe en Fish y el motor cayó a la voz por defecto. Revisá
  `voice_profiles` en Supabase contra el catálogo real de Fish.

## Por qué no se puede en producción

La VM corre lo que se desplegó por última vez. Hasta que no salga el deploy de
las Fases 5-8, la API y el agente de producción no saben que existen los
tenants. Ver [desplegar.md](desplegar.md).
