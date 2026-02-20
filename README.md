# ExecutorBot

La capa de ejecución que consume el OrchestratorBot. Una librería Python independiente.

## Responsabilidad

Recibir una instrucción → ejecutarla → retornar resultado estructurado.
No planifica. No decide. Solo ejecuta.

## Instalación

```bash
pip install -e .
```

## Uso

```bash
# Modelo por defecto (razonador rápido)
sonika start

# Especificar modelo
sonika start --model gemini:gemini-2.5-flash      # rápido, razonamiento visible
sonika start --model gemini:gemini-2.5-pro        # potente, razonamiento visible
sonika start --model openai:gpt-4o
sonika start --model deepseek:deepseek-reasoner
```

## Comandos en sesión

| Comando | Descripción |
|---------|-------------|
| `/model` | Ver modelo actual |
| `/model gemini:gemini-2.5-pro` | Cambiar de modelo sin reiniciar |
| `/modelos` | Listar modelos disponibles |
| `/sesion` | Ver sesión activa |
| `/help` | Ver todos los comandos |
| `/exit` | Salir |

## Razonamiento en tiempo real

Los modelos con `2.5` o `pro-preview` en el nombre muestran el proceso de pensamiento
streameado en color tenue directamente en la terminal (scrollable).
El pensamiento más reciente siempre aparece en la parte inferior;
puedes subir con la rueda del ratón para ver el historial completo.
