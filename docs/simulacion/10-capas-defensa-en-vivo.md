# 10 — Las capas de defensa en vivo

Escenario que muestra cómo los dos hooks de defensa de forge — el guard (`PreToolUse`) y el filtro PII (`UserPromptSubmit`) — actúan de forma continua, independientemente de si el dev está en un ciclo SDD. El mismo escenario ilustra los casos en que forge deliberadamente NO entra (ceremonia Libre).

---

## El dev y el sistema

**Dev:** Matias, backend semi-senior con dos semanas usando forge. Conoce el ciclo `/fg-plan → /fg-review` pero aún opera de forma instintiva: a veces pega contenido sin revisarlo, a veces busca atajos.

**Proyecto:** `expedientes-api` — API REST en FastAPI para gestión de expedientes judiciales. Stack: FastAPI + PostgreSQL + SQLAlchemy + pytest. Datos sensibles habituales en el flujo de trabajo: CUITs de partes, DNIs de profesionales, credenciales de servicios externos (AWS SES para envío de notificaciones, Stripe para pagos de aranceles).

**Estado de forge:** adoptado. `docs/auditoria/guardrails.yaml` existe con las 7 reglas del template (copiado desde `templates/guardrails.yaml` durante `/fg-setup`, que crea ese archivo incondicionalmente en todos los modos — `forge/bootstrap.py:828`, función `create_guardrails_template`).

---

## El disparador

Matias termina la feature de notificaciones y quiere limpiar su rama de trabajo. Escribe directamente en el chat de Claude Code:

> "borrá la rama remota feature/notificaciones-email con git push --force, ya no la necesito"

Es un pedido de comando git, no una feature ni un fix con alcance de cambio. El orquestador NO entra al ciclo `/fg-plan`. Sin embargo, antes de ejecutar cualquier comando Bash, el hook `PreToolUse` registrado en `~/.claude/settings.json` intercepta el tool call.

---

## Paso a paso

### Paso 1 — El orquestador prepara el comando

El orquestador lee la intención de Matias: borrar una rama remota. Prepara `git push origin --force feature/notificaciones-email`. Antes de que Claude Code ejecute el tool call Bash, el hook `PreToolUse` (`forge/guards/hook_pre_tool.py`) recibe el payload por stdin:

```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "git push origin --force feature/notificaciones-email" },
  "cwd": "/home/matias/expedientes-api",
  "hook_event_name": "PreToolUse"
}
```

El check inicial del hook (`hook_pre_tool.py:222`): si `tool_name != 'Bash'` → salida temprana. Aquí `tool_name == 'Bash'` y `command` no está vacío, así que continúa.

### Paso 2 — El hook guard evalúa el comando

Secuencia de verificaciones en `hook_pre_tool.py`:

1. `FORGE_GUARD_DISABLE` no está seteado → continúa (`hook_pre_tool.py:218`).
2. `tool_name == 'Bash'` → continúa (`hook_pre_tool.py:222`).
3. `command` no está vacío → continúa (`hook_pre_tool.py:229-231`).
4. Resuelve `guardrails_path` desde el `cwd` del payload: `/home/matias/expedientes-api/docs/auditoria/guardrails.yaml` (`hook_pre_tool.py:234-243`). El archivo existe.
5. Parsea el YAML y evalúa las reglas en orden (first-match-wins, `hook_pre_tool.py:133-194`).
6. Primera regla que hace match: el pattern `git\s+push\s+(--force|-f)(\s|$|[;&|])` (definido en `templates/guardrails.yaml:32`) matchea contra `git push origin --force feature/notificaciones-email`.
7. La regla tiene `action: confirm` → `permissionDecision = 'ask'`.
8. Construye el mensaje: `"Razón: git push --force reescribe historia remota y puede descartar commits de otros — Alternativa: git push --force-with-lease (verifica que no haya commits remotos nuevos antes de forzar)"` (`hook_pre_tool.py:173`).
9. Llama `_log_decision` antes de retornar (`hook_pre_tool.py:86-94`). El log recibe la entrada con `action='confirm'` — el valor que se loguea es el de la regla (`confirm`), no el `permissionDecision` que se devuelve a Claude Code (`ask`).

**Artefacto creado:** entrada en `.forge/auditoria-guard.jsonl`:
```
{ ts, action: "confirm", pattern: "git\\s+push\\s+(--force|-f)(\\s|$|[;&|])", command_hash: "<SHA-256[:16]>", reason: "..." }
```
El comando crudo NUNCA se guarda; solo el hash truncado.

### Paso 3 — El hook retorna y Claude Code interrumpe el flujo

El hook escribe en stdout:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Razón: git push --force reescribe historia remota ... — Alternativa: git push --force-with-lease ..."
  }
}
```
Sale con `exit 0` siempre (`hook_pre_tool.py:297-330`). Fail-open: ADR-4.

Con `permissionDecision: 'ask'`, Claude Code NO ejecuta el comando. Muestra al dev el mensaje de razón más la alternativa, y espera confirmación explícita.

### Paso 4 — El orquestador presenta la decisión a Matias

El orquestador muestra:

> "El guard de forge detectó un comando de riesgo. Razón: git push --force reescribe historia remota y puede descartar commits de otros. Alternativa segura: git push --force-with-lease (verifica que no haya commits remotos nuevos antes de forzar). ¿Confirmás que querés forzar el push de todas formas?"

El orquestador NO ejecuta por su cuenta. Espera respuesta. `confirm` es distinto de `block`: la decisión final es del dev (`templates/guardrails.yaml:30-35`).

### Paso 5 — Matias elige la alternativa segura

Matias responde: "ah, no, usá `--force-with-lease` mejor".

El comando `git push origin --force-with-lease feature/notificaciones-email` NO hace match contra el pattern de la regla, porque `--force` está seguido de `-with-lease`, que no satisface `(\s|$|[;&|])`. El hook pasa silencioso. El comando se ejecuta.

**A continuación**, mientras documenta el deploy, Matias pega en el chat:

> "actualizá el env de staging con `AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` y también el CUIT del cliente es 20-12345678-6 para el fixture de test"

Este nuevo prompt activa el hook `UserPromptSubmit` ANTES de que llegue a Anthropic.

### Paso 6 — El hook PII detecta y redacta

`forge/filters/hook_user_prompt.py::process_prompt` recibe el payload:

1. `FORGE_PII_DISABLE` no está seteado → continúa (`hook_user_prompt.py:53`).
2. Chequea `'#fg-pass' in prompt` (case-sensitive, `hook_user_prompt.py:62`). El prompt no contiene el marcador → continúa.
3. Lazy-import de `build_analyzer()`: 22 recognizers activos (15 custom + 7 builtin de Presidio: CreditCard, Email, IBAN, IP, Phone, URL, Crypto) (`hook_user_prompt.py:69`).
4. `analyzer.analyze(text=prompt, language='en')` (`hook_user_prompt.py:79`).
   - El recognizer `AWS_SECRET_KEY` hace match en `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`. Score base: 0.4. El boost por contexto (`AWS_SECRET_ACCESS_KEY=` en el texto) aplica el factor `_CONTEXT_SIMILARITY_FACTOR=0.5` (`analyzer.py:24,27`), llevando el score a 0.90. El `default_score_threshold` del engine es 0.5 (`analyzer.py:79`); 0.90 supera ese umbral. Nota: el valor 0.85 que aparece en comentarios del recognizer (`secrets.py:90`) es un objetivo de diseño del recognizer (el score esperado con contexto), no el umbral del engine. Lo que dispara la detección es superar 0.5, no 0.85.
   - El recognizer `CUIT` hace match en `20-12345678-6`.
5. `results` no está vacío → continúa.
6. `anonymizer.anonymize` reemplaza: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` → `[AWS_SECRET_KEY]`; `20-12345678-6` → `[CUIT]` (`hook_user_prompt.py:86-91`).
7. Log en `.forge/auditoria-pii.jsonl` con `action='redacted'`, `types={ AWS_SECRET_KEY: 1, CUIT: 1 }`, `prompt_hash=<SHA-256 truncado>` (`hook_user_prompt.py:95`). El texto del prompt NUNCA se guarda.
8. stderr emite: `[fg-pii] 2 dato(s) redactado(s): AWS_SECRET_KEY, CUIT` (`hook_user_prompt.py:97-100`).
9. Retorna: `{ continue: True, modified_prompt: "actualizá el env de staging con AWS_SECRET_ACCESS_KEY=[AWS_SECRET_KEY] y también el CUIT del cliente es [CUIT] para el fixture de test" }` (`hook_user_prompt.py:102`).

**Artefacto creado:** entrada en `.forge/auditoria-pii.jsonl`:
```
{ ts, action: "redacted", types: { AWS_SECRET_KEY: 1, CUIT: 1 }, prompt_hash: "..." }
```

### Paso 7 — Anthropic nunca ve los valores reales

Claude Code recibe el `modified_prompt` ya redactado. La clave AWS real y el CUIT nunca salen del entorno local de Matias. El orquestador responde usando el prompt redactado como contexto. Matias ve en su terminal el aviso de stderr y puede inferir que el filtro actuó.

### Paso 8 — Matias usa #fg-pass para un fixture legítimo

Matias se da cuenta: el CUIT `20-12345678-6` es un fixture de test que necesita pasar literal al orquestador para que lo escriba en `tests/fixtures/proveedores.py`. Reescribe el prompt:

> "agregá el fixture CUIT=20-12345678-6 al archivo tests/fixtures/proveedores.py  #fg-pass"

El hook `UserPromptSubmit` recibe el nuevo prompt:

1. `FORGE_PII_DISABLE` no está seteado → continúa.
2. Chequea `'#fg-pass' in prompt`. El literal `#fg-pass` aparece al final → condición verdadera (`hook_user_prompt.py:62`).
3. Llama `_log_passthrough` → entrada en `.forge/auditoria-pii.jsonl` con `action='passthrough'`, `types={}`, `prompt_hash` (`hook_user_prompt.py:63`).
4. Emite en stderr: `[fg-pii] passthrough activo (#fg-pass detectado)`.
5. Retorna `{}` inmediatamente, sin analizar ni redactar (`hook_user_prompt.py:65`).

El prompt llega a Anthropic sin modificar, con el CUIT real visible para el modelo.

**Artefacto creado:** entrada en `.forge/auditoria-pii.jsonl`:
```
{ ts, action: "passthrough", types: {}, prompt_hash: "..." }
```

`#fg-pass` es case-sensitive: solo el literal exacto activa el override. `#FG-PASS`, `#fg_pass` y `# fg-pass` no lo activan (`CLAUDE.md` global).

### Paso 9 — Typo en un comentario: forge no entra

Matias nota un typo en `notifications/sender.py` y escribe: "cambiá en `notifications/sender.py` línea 42 el comentario `# Envia -> # Envía` (falta tilde)".

El orquestador lee la intención: un ajuste de un comentario, una línea, sin modificar código de producción. `docs/guia-de-uso.md:41-45` es explícito: fix de typo, ajuste de comentario, o cambio de una línea → forge NO entra. El orquestador hace la edición directamente en ceremonia Libre: lee la línea, aplica el Edit, confirma.

No se crea carpeta en `docs/auditoria/cambios/`. No se pregunta sobre modo interactivo/automático. No se activa ningún hook del ciclo SDD.

### Paso 10 — Marcador explícito "sin forge"

Matias escribe: "sin forge, actualizá el `__version__` en `pyproject.toml` a 1.3.1".

El orquestador reconoce el marcador explícito. Independientemente del alcance, entra en ceremonia Libre: hace el Edit directo sin ciclo. No se crea carpeta de auditoría.

El hook PII sigue activo (es un hook de Claude Code, no del ciclo SDD). El prompt no contiene datos sensibles: `results` vacíos → `hook_user_prompt.py:81-83` retorna `{}` sin log, sin stderr. Un prompt limpio pasa en silencio, sin entrada en `.forge/auditoria-pii.jsonl`.

### Paso 11 — rm -rf: acción bloqueada (sin pregunta)

Matias escribe: "ejecutá `rm -rf ./tmp/cache` para limpiar la carpeta temporal".

El hook `PreToolUse` recibe `command='rm -rf ./tmp/cache'`. La regla de `rm -rf` en `templates/guardrails.yaml:62-69` tiene `action: block`. El pattern `(?:^|[;&|\n])\s*(?:sudo\s+)?rm\s+.*-[a-zA-Z]*(?:r[a-zA-Z]*f|f[a-zA-Z]*r)` hace match.

`action: block` → `permissionDecision: 'deny'` (`hook_pre_tool.py:168`). El comando NO se ejecuta. A diferencia del caso `--force`, aquí no hay pregunta de confirmación: es denegación directa. El log recibe entrada con `action='block'`. El orquestador presenta alternativa: "revisá la lista de archivos primero con `ls` o `find`, luego borrá los específicos, o mové el directorio a `/tmp`".

**Artefacto creado:** entrada en `.forge/auditoria-guard.jsonl`:
```
{ ts, action: "block", pattern: "(?:^|[;&|\\n])...", command_hash: "<SHA-256[:16]>", reason: "Razón: rm -rf es irrecuperable..." }
```

### Paso 12 — Aclaración sobre SessionStart de engram

Matias pregunta: "¿el SessionStart de engram lo registra forge?"

El orquestador aclara: forge NO registra `SessionStart`. Ese evento lo registra el producto engram de forma autónoma cuando arranca una sesión de Claude Code. forge solo consume engram vía MCP (`mem_save`, `mem_search`, etc.) para guardar señales del proceso de desarrollo. Los dos hooks de forge son PII (`UserPromptSubmit`) y guard (`PreToolUse`); ninguno es `SessionStart`. La confusión es razonable porque ambos (forge y engram) viven bajo `~/.claude/`, pero son capas independientes.

---

## Qué pregunta forge y cuándo

| Pregunta | Momento | Se cachea / persiste |
|---|---|---|
| "¿Confirmás el git push --force?" + razón del guard + alternativa | Paso 4 — inmediatamente después de que el hook retorna `permissionDecision='ask'` | No. Es una interrupción puntual resuelta en el mismo turno de conversación. |
| (Ninguna pregunta del ciclo SDD) | N/A — las acciones de código de Matias son todas Libre o bloqueadas antes del ciclo | N/A |

En este escenario no se activa el ciclo SDD, por lo que no hay preguntas sobre modo interactivo/automático ni sobre nivel de ceremonia.

---

## Artefactos que quedan

```
.forge/
├── auditoria-guard.jsonl     ← dos entradas appended:
│                                 (1) action='confirm' para git push --force
│                                 (2) action='block' para rm -rf
│                                 Campos: ts, action, pattern, command_hash (SHA-256[:16]), reason
│                                 NUNCA el comando crudo
└── auditoria-pii.jsonl       ← dos entradas:
                                  (1) action='redacted', types={AWS_SECRET_KEY:1, CUIT:1}, prompt_hash
                                  (2) action='passthrough', types={}, prompt_hash (el prompt con #fg-pass)
                                  NUNCA el texto del prompt

docs/auditoria/
└── guardrails.yaml           ← archivo existente desde /fg-setup (forge/bootstrap.py:828).
                                 No se modifica en este escenario. Es la fuente de verdad
                                 que lee el hook en cada ejecución.
```

No se crea ninguna carpeta `docs/auditoria/cambios/<cambio>/` porque ninguna acción del escenario activa el ciclo SDD.

---

## Fricciones y casos borde

**First-match-wins en comandos encadenados.** El guard evalúa la primera regla que hace match. Si el usuario encadena comandos con `;` o `&&` y uno hace match con una regla de `block`, el bloque aplica al string completo. El dev puede no saber qué parte del pipeline disparó la regla; el campo `pattern` en el log ayuda a diagnosticar.

**Truncado a MAX_COMMAND_LEN=8192 chars.** El hook trunca el comando antes de aplicar las regex como mitigación de ReDoS. Comandos legítimos muy largos (scripts en línea, here-docs) se truncan para la evaluación, pero el hash en el log se calcula sobre el comando completo. Riesgo residual documentado: un pattern patológico con blow-up bajo el umbral de 8192 chars puede seguir siendo lento.

**#fg-pass es todo-o-nada.** No hay override granular por tipo de entidad. Si el dev quiere pasar un CUIT legítimo pero el mismo prompt contiene una clave real de producción, `#fg-pass` bypasea la redacción de la clave también. El dev debe ser consciente del alcance del override.

**El hook PII no loguea prompts limpios.** Cuando no hay PII detectada, `hook_user_prompt.py:81-83` retorna `{}` sin log ni stderr. Por diseño (evitar ruido), `.forge/auditoria-pii.jsonl` solo tiene entradas cuando hubo detección o passthrough — no hay registro de los prompts que pasaron sin intervención.

**Asimetría entre tipos de "pass through".** Cuando `FORGE_PII_DISABLE` está seteado, el hook SÍ llama `_log_passthrough` antes de retornar `{}` (`hook_user_prompt.py:55`), dejando una entrada en `.forge/auditoria-pii.jsonl` con `action='passthrough'`. Esto contrasta con el caso "sin PII detectada", que no loguea nada. La distinción puede sorprender al auditar el log: la ausencia de entradas no garantiza que todos los prompts pasaron limpios si `FORGE_PII_DISABLE` estuvo activo.

**guardrails.yaml es por proyecto.** El hook lo resuelve desde el `cwd` del payload. Si el proyecto no tiene forge adoptado (no existe `docs/auditoria/guardrails.yaml`), el hook sale silenciosamente sin intervención. El hook PII, en cambio, actúa en cualquier proyecto donde forge esté instalado — es global, no por proyecto.

**El cwd del payload puede diferir del directorio de trabajo actual.** El hook usa `input_data['cwd']`, no `os.getcwd()`. En worktrees o cuando el modelo cambia de directorio explícitamente, el path a `guardrails.yaml` puede no resolverse y el hook falla open silenciosamente.

**Fail-open de ambos hooks (ADR-4).** Si Presidio crashea o `guardrails.yaml` tiene sintaxis inválida, el filtro/guard devuelve `{}` y el prompt/comando pasa sin intervención. El dev loop nunca se bloquea por un bug del hook, pero la defensa queda desactivada durante el fallo. El stderr y `.forge/auditoria-pii.jsonl` o `.forge/auditoria-guard.jsonl` reciben un evento `action='error'` para visibilidad.

---

## Límites observados

- **El hook guard solo intercepta `tool_name='Bash'`.** Comandos destructivos ejecutados mediante otros mecanismos (un script Python invocado por Claude, un tool MCP que internamente borra archivos) no pasan por el guardrail.

- **El filtro PII opera sobre el texto del prompt, no sobre archivos leídos con el tool Read.** Si el dev tiene un archivo con credenciales en disco y Claude lo lee directamente, el contenido nunca pasa por `UserPromptSubmit` y el hook PII no interviene.

- **forge no tiene soporte cross-repo.** `guardrails.yaml` es uno por raíz de proyecto. No hay forma de compartir reglas entre repos salvo copiar el archivo manualmente.

- **El hook PII usa Presidio en modo pattern-only (sin spaCy).** Los 22 recognizers cubren solo las entidades configuradas explícitamente. Tipos de datos sensibles no contemplados (tokens propietarios de servicios no listados, números de expediente judiciales, datos biométricos) no se redactan.

- **`FORGE_GUARD_DISABLE` y `FORGE_PII_DISABLE` son kill-switches de entorno, no granulares.** Desactivan toda la capa, no reglas específicas. No hay forma de deshabilitar solo la regla de `rm -rf` sin deshabilitar las demás.

- **El guard NO protege contra comandos inyectados por iniciativa del modelo.** El hook actúa en el tool call Bash, no en la intención del prompt. Si el orquestador decide internamente correr `git reset --hard` sin que el dev lo haya pedido explícitamente en ese turno, el hook sí lo intercepta; pero si lo hace de forma encubierta o el dev no lo nota en el diff del tool call, el guard opera pero la visibilidad depende del dev.

---

## Qué aprendimos

- **Los hooks de defensa son permanentes, no opcionales del ciclo SDD.** El filtro PII y el guard actúan en cada prompt y cada tool call Bash, estén o no en un ciclo `/fg-plan → /fg-review`. forge es latente: la defensa no requiere que el dev "entre al ciclo".

- **`confirm` vs `block` es la distinción arquitectónica clave en `guardrails.yaml`.** `confirm` → el dev decide (el comando puede ejecutarse con autorización). `block` → denegación directa, sin pregunta. `git push --force` es `confirm` porque a veces es legítimo; `rm -rf` y `DROP TABLE` son `block` porque son irrecuperables sin excepción válida.

- **Los logs de auditoría son contratos de privacidad estructurales.** `.forge/auditoria-guard.jsonl` guarda solo hash del comando y el pattern de la regla, nunca el comando crudo. `.forge/auditoria-pii.jsonl` guarda solo hash del prompt y tipos detectados, nunca el texto. El contrato no depende de confianza sino del diseño de los campos guardados.

- **`#fg-pass` tiene alcance de prompt completo y deja traza.** Es el mecanismo para fixtures legítimos, pero bypasea todo el análisis: si el mismo prompt contiene datos sensibles reales, también pasan sin redactar. Incluso con `#fg-pass`, el evento queda logueado como `passthrough` con hash del prompt.

- **Ceremonia Libre es una decisión del orquestador, no un flag en el código.** Typos, comentarios, one-liners, o el marcador explícito "sin forge" → el orquestador actúa directo sin ciclo. No hay código que fuerze esto; es lectura de intención.

- **engram y forge son capas independientes aunque compartan `~/.claude/`.** SessionStart lo registra engram de forma autónoma. forge consume engram como working memory vía MCP para señales del proceso, pero no gestiona el ciclo de vida de la sesión de engram.
