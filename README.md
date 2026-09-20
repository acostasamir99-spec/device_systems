# device_systems — EV11, versión 3.0.0

Actividad **GA1-220501096-01-AA1-EV11**. Implementación incremental sobre el
CRUD existente de Users, Devices y Loans; conserva SQLAlchemy, SQLite, joins,
filtros, Swagger, consola anterior y la migración previa. Rama de trabajo:
`device_systems_security`. No se ha hecho push ni merge a main.

## Ejecutar la versión actual

Desde la raíz, en PowerShell, con Python 3.10 o superior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Solo si no tienes un .env: copiar el ejemplo, sin sobrescribir tu configuración.
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Pegar el valor generado en SECRET_KEY del .env local.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Si `.venv` ya existe, reutilízalo. `.env`, la base y los respaldos `*.db` están
ignorados por Git. No compartas SECRET_KEY. El arranque rechaza una clave vacía
o de menos de 32 bytes; no existe una clave predeterminada. Para esta instalación
se generó una clave aleatoria únicamente en el `.env` local.

Variables: `SECRET_KEY`, `ALGORITHM` (HS256 por defecto; admite HS384/HS512),
`ACCESS_TOKEN_EXPIRE_MINUTES` (30), `APP_NAME`, `ADMIN_USER` y `DATABASE_URL`
opcional. Sin `DATABASE_URL` se conserva la ruta absoluta original
`device_systems.db`. `ADMIN_USER` pertenece a la consola antigua, no crea una
cuenta administradora. La versión API es 3.0.0; un `APP_VERSION` antiguo en el
entorno no rebaja los metadatos de EV11.

- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- ReDoc: http://127.0.0.1:8000/redoc

## Estructura actual

```text
app/
  main.py
  auth/{__init__,auth_routes,auth_service,security}.py
  config/settings.py
  database/connection.py
  dependencies/{database_dependency,user_dependencies,auth_dependency}.py
  middlewares/{__init__,request_middleware}.py
  models/{user_model,device_model,loan_model}.py
  routes/{user_routes,device_routes,loan_routes}.py
  schemas/{user_schema,device_schema,loan_schema,auth_schema}.py
  services/{user_service,device_service,loan_service}.py
  data/                         # Antecedente conservado
  usuarios/                     # Consola anterior conservada
alembic/
  env.py
  versions/ee65d39442b4_create_devices_and_loans_tables.py
  versions/f3a91c2d7b60_add_authentication_fields_to_users.py
tests/{conftest,test_users,test_security,test_security_migration}.py
docs/check_ev11.py               # HTTP + Swagger real con base temporal
docs/evidencias/seguridad_ev11.md # Informe de implementación
alembic.ini
.env.example
requirements.txt
pytest.ini
main.py                         # Entrada de consola anterior
```

## Registro, JWT y OAuth2

`POST /auth/register` acepta JSON, devuelve 201 y crea una cuenta autenticable:

```json
{"name":"Samir Acosta","email":"samir@example.com","password":"EjemploSeguro123","role":"user"}
```

La contraseña del ejemplo es solo ilustrativa: elige una propia. Pydantic v2
usa `Field`, `field_validator`, `model_validator` y `ConfigDict(from_attributes=True)`.
Se reutilizan `UserName`, `UserRole` y el servicio de unicidad existente. Nombre:
mínimo tres caracteres tras eliminar espacios exteriores. Email válido y único
sin distinguir mayúsculas ASCII. Contraseña: mínimo ocho caracteres, una mayúscula,
una minúscula y un número, sin espacios de ningún tipo. Máximo 1024 caracteres
para limitar el tamaño de entrada. Datos inválidos: 422; email repetido: 400.

`POST /auth/login` acepta JSON `email/password` o un formulario OAuth2 con
`username` (el correo) y `password`. Devuelve:

```json
{"access_token":"<JWT firmado>","token_type":"bearer"}
```

En Swagger pulsa **Authorize**, introduce el correo en **username** y la
contraseña; deja client_id/client_secret vacíos. Swagger obtiene y envía el JWT.
También puedes enviar `Authorization: Bearer <token>` desde cualquier cliente.
`GET /auth/me` devuelve la cuenta activa autenticada.

Los tokens incluyen `sub` (ID), `iat` y `exp`; se comprueban firma, algoritmo
configurado, expiración y claims. Contraseña incorrecta, usuario desconocido,
token inválido/expirado o ausente: 401 con `WWW-Authenticate: Bearer`.
Usuario inactivo o rol insuficiente: 403. Las dependencias `get_current_user`,
`get_current_active_user`, `require_admin` y `require_admin_or_support` consultan
el usuario en SQLite; un cambio de rol o desactivación surte efecto con tokens
ya emitidos. No se implementa refresh token ni logout del servidor en EV11.

Passlib almacena **bcrypt_sha256**, que evita truncar contraseñas a 72 bytes.
`hashed_password` es NOT NULL y no forma parte de ningún schema de respuesta,
incluidos los joins. Los errores de validación omiten `input` y `ctx` para no
reflejar contraseñas. Nunca se registran cuerpos ni tokens en el log de peticiones.
Se mantiene `passlib[bcrypt]` y se limita bcrypt a `>=4.0.1,<4.1` por compatibilidad
con Passlib 1.7.4; no se han reemplazado las dependencias anteriores.

El `POST /users` anterior conserva su payload y su respuesta. Para esas cuentas,
y para inserciones ORM sin contraseña, se genera un hash de un secreto aleatorio
distinto que se descarta. No se devuelve ni se conoce esa contraseña; para crear
una cuenta con credenciales conocidas se usa `/auth/register`.

## Roles y rutas protegidas

| Método | Ruta | Acceso requerido |
| --- | --- | --- |
| GET | /users | Usuario activo autenticado |
| GET | /users/{user_id} | Usuario activo autenticado |
| POST | /devices | admin o support |
| PUT | /devices/{device_id} | admin o support |
| DELETE | /devices/{device_id} | admin |
| POST | /loans | Usuario activo autenticado |
| PATCH | /loans/{loan_id}/return | admin o support |
| GET | /loans/details | admin o support |
| GET | /auth/me | Usuario activo autenticado |

Las demás rutas mantienen el acceso anterior. Los filtros, ordenamiento, CRUD,
historiales, disponibilidad y devoluciones conservan su lógica de negocio.

**Alcance académico solicitado:** `/auth/register` admite los tres roles.
Asimismo, las escrituras del CRUD de Users y `PATCH /devices/{device_id}`
conservan su acceso público anterior porque no figuran entre las protecciones
exactas de EV11. Esto permite autoasignar/cambiar roles y modificar dispositivos
por esas vías. No debe interpretarse como una política lista para producción;
cerrar esas vías requiere ampliar expresamente el alcance de permisos.

## CORS, middleware y límites

CORS admite exclusivamente `http://localhost:5173` y `http://localhost:3000`,
con `allow_credentials=True`, métodos y cabeceras `*`. No usa origen comodín.
Expone al navegador las cabeceras del middleware.

Un único `RequestMiddleware` conserva `X-API-Version` y añade `X-App-Name:
device_systems`, `X-Process-Time` (segundos hasta el inicio de la respuesta) y
`X-Request-ID`. Propaga IDs de 1–128 caracteres alfanuméricos o `._:-`; si no
hay un ID válido, genera un UUID. Registra método HTTP, ruta sin query string,
código, duración e ID en `uvicorn.error.requests`.

SlowAPI aplica límites por IP de conexión, con almacenamiento en memoria:

| Ruta | Límite |
| --- | --- |
| POST /auth/login | 5/minute |
| POST /auth/register | 3/minute |
| GET /users | 30/minute |
| POST /loans | 10/minute |

Al superarlos devuelve 429. Los contadores son por proceso y se reinician al
reiniciar la aplicación; este montaje local usa un worker. No confía en un
`X-Forwarded-For` arbitrario del cliente. No desactiva límites para pasar pruebas.

## Alembic y compatibilidad de SQLite

La revisión anterior `ee65d39442b4` se conserva intacta. Solo creaba Devices y
Loans: Users se había creado mediante `Base.metadata.create_all()`.
La nueva revisión **f3a91c2d7b60 — add authentication fields to users**:

1. Si Users ya existe, conserva `role` e `is_active`, añade temporalmente
   `hashed_password` nullable y completa cada fila con un hash seguro distinto.
2. Reconstruye la tabla con el modo batch de Alembic para exigir NOT NULL,
   conservando índices, restricciones e IDs. Preserva `sqlite_sequence`, incluso
   IDs previamente eliminados, para no reutilizarlos.
3. Si Users no existe, crea la tabla completa y sus índices. Así `alembic upgrade
   head` funciona también desde una SQLite vacía, sin cambiar la revisión anterior.

La migración requiere conexión online por el backfill y la inspección de SQLite.
No usa `stamp`, no borra la base ni reemplaza el historial. `alembic/env.py`
admite una conexión suministrada para probar migraciones sobre bases temporales.
Se conserva `create_all()` de arranque, pero **no sustituye `alembic upgrade head`**.

Antes de migrar la base local se creó
`backups/device_systems_before_ev11_20260919_191452.db` mediante SQLite backup.
La base conserva 0 usuarios, 0 dispositivos y 0 préstamos; los datos de prueba
se insertan únicamente en bases temporales. Un downgrade elimina las credenciales
añadidas; no lo ejecutes sobre cuentas nuevas que necesites conservar autenticables.

```powershell
python -m alembic current
python -m alembic history
python -m alembic check
```

Estado esperado: `f3a91c2d7b60 (head)` y cadena
`<base> -> ee65d39442b4 -> f3a91c2d7b60`.

## Pruebas y comprobación en navegador

```powershell
python -m pytest
# Opcional: Playwright ya estaba instalado en el entorno de trabajo.
python -m pip install playwright
python docs/check_ev11.py
```

Se conservan las **71 pruebas anteriores**. Sus fixtures añaden hashes y Bearer
real; las comprobaciones del CRUD no se eliminan. Los INSERT de restricciones
incluyen un hash válido para comprobar la restricción original, no fallar por
la nueva columna. Cada prueba reinicia los contadores y usa SQLite aislada.

`test_security.py` cubre los 15 escenarios EV11, todos los límites, las ocho
rutas protegidas, roles, usuarios inactivos, tokens alterados/expirados,
contraseñas Unicode largas, confidencialidad y regresión Devices/Loans con joins
y filtros. `test_security_migration.py` prueba bases vacías y pobladas,
upgrade/downgrade/upgrade, constraints, relaciones y secuencias.

El script opcional abre Edge headless, comprueba Swagger real, realiza Authorize
con OAuth2 y ejecuta `/auth/me` desde la interfaz. También comprueba HTTP 201,
200, 401, 403 y 429 contra Uvicorn. No imprime JWT, contraseñas ni claves, no
genera capturas y no usa la base de trabajo.

Consulta los resultados finales en [el informe EV11](docs/evidencias/seguridad_ev11.md).

## Capturas pendientes de Samir — EV11

Estos son lugares pendientes, no capturas inventadas. Samir debe agregar las
imágenes reales y contrastar los nombres/número de evidencias con su guía:

- **[PENDIENTE SAMIR]** Estructura y rama `device_systems_security`.
- **[PENDIENTE SAMIR]** Swagger con Auth, Authorize/OAuth2 y versión 3.0.0.
- **[PENDIENTE SAMIR]** Registro correcto, contraseña débil y email duplicado.
- **[PENDIENTE SAMIR]** Login y `/auth/me`; ocultar el JWT y la contraseña.
- **[PENDIENTE SAMIR]** Respuestas 401 y 403, y operación permitida por rol.
- **[PENDIENTE SAMIR]** CORS y cabeceras de middleware.
- **[PENDIENTE SAMIR]** Rate limiting: respuesta 429.
- **[PENDIENTE SAMIR]** Suite completa, `alembic current`, `alembic history` y Git.

Referencias de implementación: [FastAPI OAuth2/JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[Passlib bcrypt_sha256](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt_sha256.html)
y [SlowAPI](https://slowapi.readthedocs.io/en/stable/).

---

# Referencia histórica EV09 (conservada)

El contenido y las capturas siguientes describen la versión anterior. Sus
resultados, acceso público y configuración corresponden a EV09; para ejecutar
EV11 usa las instrucciones anteriores y autentícate en las rutas protegidas.

Actividad **GA1-220501096-01-AA1-EV09**: API REST de usuarios con FastAPI,
SQLAlchemy 2, Pydantic v2 y SQLite. Los datos se guardan en `device_systems.db`
y permanecen al reiniciar la API. La base empieza vacía y se crea al arrancar.
El nombre de la aplicación es `device_systems`.

## Instalación y ejecución

Requiere Python 3.10 o superior (verificado con Python 3.13).
Desde la raíz, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

En Linux/macOS usa `.venv/bin/python` en lugar de `.venv\Scripts\python.exe`.

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Especificación OpenAPI: http://127.0.0.1:8000/openapi.json

La ruta SQLite se resuelve desde `app/database/connection.py` hacia
`device_systems.db`, independientemente del directorio de ejecución.
Ejecuta Uvicorn desde la raíz del proyecto. La base existente se conserva al reorganizar.
La base local está excluida de Git. No se insertan usuarios automáticamente.
`create_all()` crea tablas ausentes; no migra tablas existentes.

## Estructura

```text
device_systems/
  app/
    main.py
    database/connection.py
    models/user_model.py
    schemas/user_schema.py
    routes/user_routes.py
    services/user_service.py
    dependencies/database_dependency.py
    dependencies/user_dependencies.py
    config/settings.py
    data/users_db.py                  # antecedente; no usado por la API
    usuarios/{gestor,validaciones}.py # consola anterior
  tests/test_users.py
  docs/
  device_systems.db                   # base local, ignorada por Git
  requirements.txt
  .gitignore
  README.md
  pytest.ini
  .env.example
  main.py                            # entrada de consola anterior
  legacy_csharp/                     # respaldo local conservado
```

La captura siguiente corresponde a la estructura anterior; el árbol de arriba refleja la reorganización.

![Captura histórica de la estructura](docs/images/estructura.png)

Los módulos anteriores de consola (`main.py` y `app/usuarios`) se
conservan como antecedentes; se ejecutan con `python main.py` desde la raíz del proyecto.
`app/data` conserva el almacenamiento histórico en memoria, que no utiliza la API.
El punto de entrada de esta API es **app.main:app**.
El respaldo `legacy_csharp/` se conserva localmente y está ignorado por Git.

## Arquitectura y persistencia

`connection.py` configura `engine`, `SessionLocal`, `Base` y `get_db()`.
`database_dependency.py` expone la sesión mediante `Depends(get_db)`.
Cada petición recibe una sesión que se cierra al terminar; las dependencias
anidadas de una misma petición comparten esa sesión gracias a FastAPI.
Las rutas delegan las consultas y transacciones en `user_service.py`.
Las escrituras utilizan `commit()` y hacen `rollback()` ante errores de integridad.

El **modelo SQLAlchemy** `User` representa la tabla `users`: columnas, tipos,
clave primaria, índices y restricciones. El **schema Pydantic** define el contrato
HTTP: valida el JSON de entrada y controla qué campos devuelve la API.
Un schema no crea tablas y un modelo ORM no sustituye la validación HTTP.
`UserResponse` utiliza `from_attributes=True` para leer objetos SQLAlchemy.

| Campo | Tipo SQLAlchemy | Restricciones |
| --- | --- | --- |
| id | Integer | Clave primaria autoincremental, no reutiliza IDs eliminados |
| name | String | NOT NULL; CHECK de al menos 3 caracteres tras trim |
| email | String | NOT NULL; UNIQUE con NOCASE en SQLite; índice |
| role | String | NOT NULL; CHECK admin, support o user |
| is_active | Boolean | NOT NULL; predeterminado True; CHECK booleano |
| created_at | DateTime | NOT NULL; fecha automática en UTC |

La fecha se almacena y devuelve sin desplazamiento de zona horaria; se interpreta
como UTC. PUT y PATCH conservan tanto el ID como la fecha de creación.
SQLite NOCASE compara sin mayúsculas/minúsculas los caracteres ASCII del correo.
El formato del correo se valida en Pydantic mediante `EmailStr`.

![Esquema y consulta real de SQLite](docs/images/base-datos.png)

## Schemas y validaciones

- `UserCreate`: name, email y role obligatorios; is_active vale true si se omite.
- `UserUpdate`: PUT exige los cuatro campos editables.
- `UserPatch`: campos omitibles; rechaza null explícito y el objeto vacío.
- `UserResponse`: añade id y created_at, asignados por el servidor.

El nombre elimina espacios exteriores y requiere mínimo 3 caracteres.
Los roles admitidos son `admin`, `support` y `user`; un rol inválido genera 422.
No se admiten campos extra ni IDs o fechas proporcionados por el cliente.
Los correos duplicados generan 400, incluso ante inserciones concurrentes,
gracias a la restricción UNIQUE de la base de datos.

## Endpoints

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | /users | Lista, filtros y ordenamiento; 200 |
| GET | /users/{user_id} | Usuario por ID; 200 |
| POST | /users | Crea usuario; 201 |
| PUT | /users/{user_id} | Reemplaza todos los campos editables; 200 |
| PATCH | /users/{user_id} | Modifica campos enviados; 200 |
| DELETE | /users/{user_id} | Elimina; 204 sin cuerpo |

Ejemplos de consultas combinables:

```text
/users?role=support
/users?is_active=true
/users?role=admin&is_active=true&sort_by=name&order=asc
/users?sort_by=created_at&order=desc
```

`sort_by` admite `name` (predeterminado) o `created_at`; `order` admite `asc`
(predeterminado) o `desc`. Los empates se resuelven por ID ascendente.
El servicio también incluye `find_user_by_email()` para buscar por correo.

POST `/users`:

```json
{"name":"Samir Acosta","email":"samir@example.com","role":"user","is_active":true}
```

PUT `/users/1` (usa el ID devuelto por POST):

```json
{"name":"Samir Actualizado","email":"samir@example.com","role":"support","is_active":true}
```

PATCH `/users/1`:

```json
{"is_active":false}
```

## Errores controlados

| Código | Situación |
| --- | --- |
| 400 | Email duplicado o PATCH vacío |
| 404 | Usuario inexistente al consultar, actualizar o eliminar |
| 422 | Nombre/email/rol inválido, campos faltantes, null o parámetros inválidos |

Ejemplo: `{"detail":"Usuario no encontrado"}`.
Las actualizaciones con correo duplicado se rechazan antes de modificar campos.
La validación de roles ahora se realiza con Pydantic y devuelve 422.

## Configuración y documentación

La configuración existente admite `APP_NAME`, `APP_VERSION` y `ADMIN_USER` en
`.env`; consulta `.env.example`. `ADMIN_USER` no implementa autenticación.
El middleware conserva las cabeceras `X-App-Name` y `X-API-Version`.
Swagger incluye schemas, parámetros, descripciones y códigos HTTP.
Sus recursos visuales se cargan desde CDN y requieren Internet.

![Swagger UI real](docs/images/swagger-ui.png)

## Pruebas y evidencias

Desde la raíz, con el entorno virtual activo:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado: **71 pruebas aprobadas**. Las pruebas usan archivos SQLite temporales,
incluyen CRUD, filtros, orden, errores, concurrencia, constraints y persistencia
al abrir un engine nuevo. No insertan datos de prueba en la base de trabajo.

Consulta el [informe histórico de reorganización](docs/evidencias/reorganizacion_backend.md),
el [informe de validación](docs/validacion.md), la
[guía de pruebas manuales](docs/pruebas_manuales.md), las
[respuestas HTTP completas](docs/resultados.json) y el
[informe HTML de evidencias](docs/evidencias.html).

Las siguientes imágenes son capturas de respuestas HTTP reales obtenidas con
Uvicorn y httpx, presentadas en un informe HTML. La captura de Swagger corresponde
a la interfaz real. La captura de base de datos muestra el esquema y la consulta
SQL de una base temporal aislada, antes de eliminar el usuario de prueba.

### Crear usuario: 201

![Crear usuario: 201](docs/images/prueba-01.png)

### Email repetido: 400

![Email repetido: 400](docs/images/prueba-02.png)

### Listar usuarios: 200

![Listar usuarios: 200](docs/images/prueba-03.png)

### Consultar por ID: 200

![Consultar por ID: 200](docs/images/prueba-04.png)

### Usuario inexistente: 404

![Usuario inexistente: 404](docs/images/prueba-05.png)

### Filtrar por rol: 200

![Filtrar por rol: 200](docs/images/prueba-06.png)

### Filtrar activos: 200

![Filtrar activos: 200](docs/images/prueba-07.png)

### Ordenar por fecha: 200

![Ordenar por fecha: 200](docs/images/prueba-08.png)

### PUT completo: 200

![PUT completo: 200](docs/images/prueba-09.png)

### PATCH parcial: 200

![PATCH parcial: 200](docs/images/prueba-10.png)

### Rol inválido: 422

![Rol inválido: 422](docs/images/prueba-11.png)

### Email inválido: 422

![Email inválido: 422](docs/images/prueba-12.png)

### Nombre inválido: 422

![Nombre inválido: 422](docs/images/prueba-13.png)

### DELETE: 204

![DELETE: 204](docs/images/prueba-14.png)

### Verificar eliminación: 404

![Verificar eliminación: 404](docs/images/prueba-15.png)

### Eliminar inexistente: 404

![Eliminar inexistente: 404](docs/images/prueba-16.png)

### Actualizar inexistente: 404

![Actualizar inexistente: 404](docs/images/prueba-17.png)

Para regenerar las evidencias con Microsoft Edge instalado:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe docs/generar_evidencias.py
```

Playwright es una herramienta opcional para las capturas; no se requiere para
usar la API ni para ejecutar pytest. El generador inicia un servidor temporal,
comprueba los códigos HTTP, captura los resultados y cierra servidor y navegador.

## Reflexión final

La persistencia permite que los usuarios sigan disponibles después de reiniciar
el servidor. SQLAlchemy organiza las consultas con objetos Python y las
restricciones de SQLite protegen la integridad incluso fuera de la API.
Pydantic valida los datos antes de guardarlos y proporciona errores comprensibles
al cliente. Separar conexión, modelos, schemas, servicios y rutas facilita probar
y mantener la aplicación. Las transacciones evitan guardar cambios incompletos,
y las pruebas de reapertura comprueban que la persistencia es real.
