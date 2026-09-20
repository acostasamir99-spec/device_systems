# Informe EV11 — device_systems

Fecha de ejecución: 19 de septiembre de 2026.
Actividad: GA1-220501096-01-AA1-EV11.
Rama: `device_systems_security`.

## Resultado

Implementación incremental de autenticación JWT/OAuth2, contraseñas Passlib,
dependencias por rol, ocho protecciones requeridas, CORS, middleware de
peticiones, SlowAPI y documentación OpenAPI 3.0.0 (versión de la aplicación).
No se rehízo el proyecto, no se eliminaron pruebas y no se hizo commit, push
ni merge. `main` no recibió commits ni cambios de implementación en esta fase;
se creó y activó la rama de seguridad antes de editar.

## Diagnóstico y compatibilidad

La ejecución inicial dio **71 passed, 0 failed, 2 warnings**. Se encontraron
modificaciones locales previas de Users, Devices, Loans y Alembic y se conservaron.
`role` e `is_active` ya existían. La base local estaba vacía y su revisión era
`ee65d39442b4`. Las pruebas antiguas usaban GET /users sin token y creaban
usuarios sin contraseña. Samir autorizó adaptar la autenticación de las fixtures
y generar hashes seguros de secretos descartados en el alta antigua.

Las 71 comprobaciones anteriores se conservan. Sus fixtures usan un JWT real de
la cuenta support, independiente de la cuenta admin modificada en varias pruebas,
y hashes reales. Se conserva la comprobación de constraints por INSERT directo,
añadiendo un hash válido para no ocultar el error de integridad que cada prueba
pretende evaluar. No se añadió un bypass de autenticación ni se desactivó SlowAPI.

## Archivos creados en esta implementación

```text
app/auth/__init__.py
app/auth/auth_routes.py
app/auth/auth_service.py
app/auth/security.py
app/schemas/auth_schema.py
app/dependencies/auth_dependency.py
app/middlewares/__init__.py
app/middlewares/request_middleware.py
alembic/versions/f3a91c2d7b60_add_authentication_fields_to_users.py
tests/conftest.py
tests/test_security.py
tests/test_security_migration.py
docs/check_ev11.py
docs/evidencias/seguridad_ev11.md
```

Archivos locales adicionales excluidos de Git:

- `.env`: clave aleatoria local, nunca impresa ni incluida en este informe.
- `backups/device_systems_before_ev11_20260919_191452.db`: respaldo anterior
  a la migración, creado con la API SQLite backup.

## Archivos modificados en esta implementación

```text
.env.example
README.md
requirements.txt
app/config/settings.py
app/database/connection.py
app/main.py
app/models/user_model.py
app/routes/user_routes.py
app/routes/device_routes.py
app/routes/loan_routes.py
alembic/env.py
tests/test_users.py
```

Además se migró el archivo local `device_systems.db`, ignorado por Git.
`app/schemas/user_schema.py` ya estaba modificado antes de EV11 y no se editó
durante esta implementación. Los modelos, schemas y servicios de Devices/Loans,
la revisión anterior, `alembic.ini`, `git` y `tree` ya existían sin seguimiento;
el estado `??` de Git no significa que todos ellos se hayan creado en EV11.

## Endpoints nuevos

| Método | Ruta | Resultado |
| --- | --- | --- |
| POST | /auth/register | 201; valida datos y guarda hash real |
| POST | /auth/login | 200; access_token y token_type=bearer |
| GET | /auth/me | 200; usuario activo autenticado sin hash |

Login acepta JSON email/password y formulario OAuth2 username/password;
username contiene el email. Swagger usa el formulario. El registro reutiliza
las validaciones de nombre/rol, la consulta de email y el commit del servicio
existente. UNIQUE en SQLite resuelve también duplicados concurrentes.

## Protecciones

| Método | Ruta | Dependencia |
| --- | --- | --- |
| GET | /users | get_current_active_user |
| GET | /users/{user_id} | get_current_active_user |
| POST | /devices | require_admin_or_support |
| PUT | /devices/{device_id} | require_admin_or_support |
| DELETE | /devices/{device_id} | require_admin |
| POST | /loans | get_current_active_user |
| PATCH | /loans/{loan_id}/return | require_admin_or_support |
| GET | /loans/details | require_admin_or_support |
| GET | /auth/me | get_current_active_user |

Las dependencias usan get_current_user, verifican JWT firmado/expiración/claims
y cargan el usuario actual en la base. Token ausente o inválido: 401 y
WWW-Authenticate: Bearer. Usuario inactivo o rol insuficiente: 403.

La lógica CRUD, relaciones, joins, filtros, historiales, devoluciones y
disponibilidad continúa en los servicios existentes. Las respuestas existentes
no incorporan campos de contraseña. Los errores 422 omiten los inputs para
evitar reflejar secretos enviados en peticiones inválidas.

## Migración

Nueva revisión: `f3a91c2d7b60`, **add authentication fields to users**.
Padre: `ee65d39442b4`, sin editar su contenido ni su historial.

Se resuelve el caso de Users creada previamente por create_all inspeccionando
la base: si existe, se añade el campo, se completa con un hash distinto de
contraseña aleatoria por fila y se exige NOT NULL mediante batch. Se conservan
role/is_active, índices, constraints, IDs y la secuencia autoincremental
histórica. Si Users no existe, esta revisión crea la tabla completa y sus
índices; así una base vacía se puede construir con alembic upgrade head.

El downgrade solo elimina la columna nueva y preserva Users y la secuencia;
elimina las credenciales y no debe usarse en cuentas que deban conservarlas.
Las pruebas de downgrade se hicieron exclusivamente en bases temporales.
No se usó stamp, no se borró la base ni se sustituyeron migraciones.

Comandos ejecutados sobre la base local:

```text
python -m alembic upgrade head
Running upgrade ee65d39442b4 -> f3a91c2d7b60, add authentication fields to users

python -m alembic current
f3a91c2d7b60 (head)

python -m alembic history
ee65d39442b4 -> f3a91c2d7b60 (head), add authentication fields to users
<base> -> ee65d39442b4, create devices and loans tables

python -m alembic check
No new upgrade operations detected.
```

Comprobación final de SQLite: Users=0, Devices=0, Loans=0; hashed_password
VARCHAR NOT NULL sin server default; integrity_check=ok; foreign_key_check=[].
No se insertaron usuarios de pruebas en la base de trabajo.

## Pruebas ejecutadas

| Ejecución | Collected | Passed | Failed | Warnings |
| --- | ---: | ---: | ---: | ---: |
| Diagnóstico anterior | 71 | 71 | 0 | 2 |
| Regresión test_users.py adaptada | 71 | 71 | 0 | 2 |
| test_security.py + test_security_migration.py | 71 | 71 | 0 | 2 |
| Suite completa final | **142** | **142** | **0** | **2** |

Comando final: `.\.venv\Scripts\python.exe -m pytest`.
Salida: **142 passed, 2 warnings in 20.32s**.
Desglose: 71 pruebas anteriores, 69 casos de seguridad/regresión y 2 casos de
migración. Los 15 escenarios EV11 se implementaron y varios se parametrizaron
para cubrir todas las rutas, roles, orígenes y límites.

Los dos warnings son los mismos del diagnóstico:

- StarletteDeprecationWarning: uso de httpx en starlette.testclient.
- DeprecationWarning: alias anyio.abc.BlockingPortal.

Se probaron los límites 5/3/30/10 por minuto, hash obligatorio, ausencia de
hashes en respuestas, contraseñas débiles y Unicode largas, validación de
registro, cambios de rol en vivo, usuarios inactivos, tokens expirados y
manipulados, CORS autorizado/rechazado y logging/cabeceras.
Los casos de migración incluyen datos y relaciones existentes, preservación
del ID eliminado 99, constraints y el ciclo upgrade/downgrade/upgrade.

También se ejecutaron `python -m pip check` (sin dependencias rotas),
`git diff --check` (sin errores) y la comprobación real siguiente.

## Verificación HTTP y visual real

Comando: `.\.venv\Scripts\python.exe docs/check_ev11.py`.
Uvicorn local, SQLite temporal y Microsoft Edge headless mediante Playwright.
No se generaron capturas ni se atribuyeron capturas históricas a EV11.

```json
{
  "docs_http": 200,
  "register_roles": ["admin", "support", "user"],
  "login_jwt": true,
  "me": 200,
  "no_token": 401,
  "wrong_role": 403,
  "middleware": true,
  "swagger_auth_visible": true,
  "swagger_oauth2_visible": true,
  "swagger_authorize_login": true,
  "swagger_me_authorized": 200,
  "rate_limit": 429,
  "no_credentials_in_responses": true
}
```

La comprobación incluyó pulsar Authorize, iniciar sesión y ejecutar /auth/me
desde la interfaz. No fue solo una inspección del JSON OpenAPI.
Samir tiene marcadores explícitos en README para añadir las capturas requeridas.

## Problemas encontrados y límites del alcance

- El sandbox impidió crear la rama en .git y descargar dependencias. Se pidió
  escalación para esas acciones; ambas se completaron. Edge se ejecutó con
  autorización fuera del sandbox.
- La automatización visual necesitó corregir selectores: Swagger tiene dos
  inputs password y nombres accesibles distintos para algunos botones. Se
  corrigió el script y la ejecución final terminó correctamente.
- Se fijó bcrypt en la serie 4.0 compatible con Passlib 1.7.4. Hashes reales,
  verificación y Unicode largo fueron comprobados en Python 3.13.14.
- Git sigue avisando que no puede leer `.pytest_tmp/`, condición previa a EV11.
  No afectó la suite: pytest utilizó sus directorios temporales normales.
  También informa conversiones LF/CRLF por la configuración local de Windows.
- Por las protecciones exactas solicitadas, el registro acepta los tres roles
  y las escrituras antiguas de Users y PATCH de Devices conservan acceso público.
  Esto permite autoasignar o cambiar roles y modificar dispositivos por esas
  vías. Es el alcance académico pedido, no un cierre completo para producción.
- SlowAPI utiliza memoria local por proceso, sin contadores distribuidos ni
  persistencia entre reinicios. Se documenta ejecución local con un worker.

## Estado final de Git

`git branch --show-current`: **device_systems_security**.
Sin commit, push ni merge; se conservan cambios locales anteriores.

Salida de `git status --short --branch` al cierre:

```text
## device_systems_security
 M .env.example
 M README.md
 M app/config/settings.py
 M app/database/connection.py
 M app/main.py
 M app/models/user_model.py
 M app/routes/user_routes.py
 M app/schemas/user_schema.py
 M requirements.txt
 M tests/test_users.py
?? alembic.ini
?? alembic/
?? app/auth/
?? app/dependencies/auth_dependency.py
?? app/middlewares/
?? app/models/device_model.py
?? app/models/loan_model.py
?? app/routes/device_routes.py
?? app/routes/loan_routes.py
?? app/schemas/auth_schema.py
?? app/schemas/device_schema.py
?? app/schemas/loan_schema.py
?? app/services/device_service.py
?? app/services/loan_service.py
?? docs/check_ev11.py
?? docs/evidencias/seguridad_ev11.md
?? git
?? tests/conftest.py
?? tests/test_security.py
?? tests/test_security_migration.py
?? tree
```

`git check-ignore` confirmó la exclusión de `.env` y del respaldo SQLite.
La lista de archivos de este informe distingue el trabajo EV11 del preexistente.
