# Sonika

Agente CLI autónomo con herramientas de sistema, archivos, web, bases de datos y gestión de tareas programadas.

## Instalación

```bash
pip install -e .
```

## Uso

```bash
# Lanzar la CLI
sonika

# Pasar un prompt inicial directamente
sonika "lista los archivos del directorio actual"
```

## Interfaz

Interfaz estilo Claude Code usando Rich + prompt_toolkit. Terminal normal sin pantalla alternativa — scroll nativo, copy/paste nativo.

- Prompt con `❯` y badge de modo
- Respuestas renderizadas como Markdown
- Tools con estado (▸ pendiente, ✓ éxito, ✗ error)
- Línea de estado en vivo durante streaming (fase, tiempo, tokens, modelo)
- Thinking visible en panel colapsado al finalizar
- Stats del último response en el toolbar del input
- Pickers interactivos con flechas ↑↓
- Aprobación con navegación ← → entre Sí/No
- Banner de bienvenida con mascota ASCII

## Comandos disponibles

| Comando                        | Descripción                          |
| ------------------------------ | ------------------------------------ |
| `/model`                       | Abrir selector de modelos            |
| `/session`                     | Abrir selector de sesiones anteriores|
| `/new` o `/n`                  | Crear nueva sesión                   |
| `/key <proveedor> <clave>`     | Configurar API key (ej. `/key google AIza...`) |
| `/mode`                        | Cambiar modo (ask/auto/plan)         |
| `/help`                        | Ver todos los comandos               |
| `/exit`                        | Salir                                |
| `Tab`                          | Cambiar modo                         |

## Modelos soportados

| Proveedor | Modelos                                              |
| --------- | ---------------------------------------------------- |
| Google    | gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash-thinking-exp |
| OpenAI    | o4-mini, o3-mini, o3, o1, o1-mini                    |
| DeepSeek  | deepseek-reasoner                                    |

## Herramientas disponibles

### Core
| Herramienta     | Descripción                            |
| --------------- | -------------------------------------- |
| RunBashTool     | Ejecutar comandos de shell             |
| BashSafeTool    | Bash con restricciones de seguridad    |
| ReadFileTool    | Leer archivos                          |
| WriteFileTool   | Escribir archivos                      |
| ListDirTool     | Listar directorios                     |
| DeleteFileTool  | Eliminar archivos                      |
| FindFileTool    | Buscar archivos por patrón             |
| CallApiTool     | Hacer peticiones HTTP                  |
| SearchWebTool   | Buscar en la web                       |
| FetchWebPageTool| Obtener contenido de una URL           |
| RunPythonTool   | Ejecutar código Python                 |
| GetDateTimeTool | Obtener fecha/hora actual              |
| EmailSMTPTool   | Enviar emails via SMTP                 |
| SQLiteTool      | Consultas SQLite                       |
| PostgreSQLTool  | Consultas PostgreSQL                   |
| MySQLTool       | Consultas MySQL                        |
| RedisTool       | Comandos Redis                         |

### Scheduler
| Herramienta | Acciones                                                    |
| ----------- | ----------------------------------------------------------- |
| CronTool    | `list`, `add`, `remove`, `validate`, `generate_plist`       |

## Ejemplos de uso — Crontab

```
# Listar tareas programadas actuales
"muéstrame mis crontabs"

# Validar una expresión
"valida la expresión '0 9 * * 1-5'"

# Agregar una tarea diaria
"agrega un cron que ejecute /scripts/backup.sh todos los días a las 3am"

# Eliminar una tarea
"elimina el cron que ejecuta /scripts/old-task.sh"

# Generar launchd plist para macOS
"genera un launchd plist para ejecutar /scripts/sync.sh cada hora en macOS"
```

## Arquitectura

```
sonika/cli/
  __init__.py              # Entry point
  app.py                   # SonikaCLI — loop principal, renderer-agnostic
  config.py                # Config — API keys, modelo activo
  models_catalog.py        # Catálogo de modelos con precios
  session_manager.py       # Persistencia de sesiones
  renderers/
    __init__.py            # BaseRenderer ABC
    claude_style.py        # Renderer Claude Code-style (Rich + prompt_toolkit)
```

## Almacenamiento persistente

```
~/.sonika/
├── config.json           # API keys, proveedor/modelo activo
├── sessions/
│   └── {id}.json         # Historial de chat, tokens y costo estimado
└── memory/
    └── {session_id}/     # Memoria interna del OrchestratorBot
```

## Configuración

```json
{
  "keys": {
    "openai": "sk-...",
    "google": "AIza...",
    "deepseek": "sk-..."
  },
  "active_provider": "google",
  "active_model": "gemini-2.5-flash"
}
```

## Extensibilidad (SonikaAppConfig)

```python
from sonika.config_schema import SonikaAppConfig

config = SonikaAppConfig(
    app_name="MiApp",
    app_title="MI APP",
    system_instructions="...",
    extra_commands={"ping": handler},
    extra_tool_groups={"custom": loader},
    extra_tools=[mi_tool],
)
```

## Razonamiento en tiempo real

Los modelos con `2.5` o `pro` en el nombre muestran el proceso de pensamiento en tiempo real, visible como un panel colapsado con las primeras y últimas líneas del razonamiento.

## Licencia

MIT — ver [LICENSE](LICENSE).

## Contributor

- Erley
