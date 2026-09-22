# EV11 - Fase 13: pruebas funcionales reales

Inicio UTC: 2026-09-21T23:40:10.659771+00:00

HTTP real: httpx -> socket TCP local -> Uvicorn -> aplicacion existente

SQLite temporal migrada con Alembic; contadores reiniciados entre escenarios, nunca durante una secuencia de limite

JWT omitidos. Cuentas y contrasenas sinteticas de prueba. No se generaron capturas. No se modifico la aplicacion ni las pruebas existentes.

| N | PRUEBA | ENDPOINT | ROL | RESULTADO ESPERADO | RESULTADO REAL | HTTP | PASS/FAIL |
|---|---|---|---|---|---|---|---|
| 1 | Registro de usuario | POST /auth/register | user | 201; persistencia y hash seguro | Comprobaciones verificadas | 201 | PASS |
| 2 | Contrasena debil | POST /auth/register | user | 422, rechazo Pydantic | Comprobaciones verificadas | 422 | PASS |
| 3 | Email duplicado | POST /auth/register | user | 400; sigue existiendo un solo usuario | Comprobaciones verificadas | 400 | PASS |
| 4 | Login correcto | POST /auth/login | user | 200; access_token y token_type=bearer | Comprobaciones verificadas | 200 | PASS |
| 5 | Contrasena incorrecta | POST /auth/login | user | 401 | Comprobaciones verificadas | 401 | PASS |
| 6 | Consultar mi usuario | GET /auth/me | user | 200; usuario correcto sin credenciales | Comprobaciones verificadas | 200 | PASS |
| 7 | Sin token | GET /users | ninguno | 401 | Comprobaciones verificadas | 401 | PASS |
| 8 | Token invalido | GET /users | ninguno | 401 | Comprobaciones verificadas | 401 | PASS |
| 9 | Usuario sin permisos | POST /devices | user | 403 | Comprobaciones verificadas | 403 | PASS |
| 10 | Crear dispositivo con rol permitido | POST /devices | support | 201 | Comprobaciones verificadas | 201 | PASS |
| 11 | Eliminar con rol no permitido | DELETE /devices/{device_id} | support | 403; dispositivo conservado | Comprobaciones verificadas | 200, 403 | PASS |
| 12 | CORS | OPTIONS y GET /users | user / preflight sin token | 200 locales; 400 origen ajeno | Comprobaciones verificadas | 200, 400 | PASS |
| 13 | Cabeceras y log del middleware | GET /users | user | 200; tres cabeceras y log real | Comprobaciones verificadas | 200 | PASS |
| 14 | Rate limiting real | POST /auth/login; POST /auth/register; GET /users; POST /loans | user; admin prepara dispositivos | 429 en solicitudes 6, 4, 31 y 11 | Comprobaciones verificadas | 200, 201, 429 | PASS |
| 15 | Swagger / OpenAPI | GET /docs; GET /openapi.json | ninguno | 200; metadatos, OAuth2, rutas y modelos correctos | Comprobaciones verificadas | 200 | PASS |

## 1. Registro de usuario

Comprobaciones:

```json
{
  "persisted_from_independent_connection": true,
  "password_not_plaintext": true,
  "stored_hash_verifies_password": true,
  "hashed_password_absent_in_response": true
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/register",
    "headers": {},
    "json": {
      "name": "Usuario Prueba",
      "email": "usuario.ev11@example.com",
      "password": "Usuario123",
      "role": "user"
    },
    "form": null
  },
  "http": 201,
  "response": {
    "name": "Usuario Prueba",
    "email": "usuario.ev11@example.com",
    "role": "user",
    "is_active": true,
    "id": 1,
    "created_at": "2026-09-21T23:40:19.074605"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:17 GMT",
    "server": "uvicorn",
    "content-length": "140",
    "content-type": "application/json",
    "x-process-time": "0.593239",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "ac21a7db-9e53-48d2-a133-76bd148d8646"
  }
}
```

## 2. Contrasena debil

Comprobaciones:

```json
{
  "validation": {
    "detail": [
      {
        "loc": [
          "body",
          "password"
        ],
        "msg": "Value should have at least 8 items after validation, not 3",
        "type": "too_short"
      }
    ]
  }
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/register",
    "headers": {},
    "json": {
      "name": "Usuario Debil",
      "email": "debil.ev11@example.com",
      "password": "123",
      "role": "user"
    },
    "form": null
  },
  "http": 422,
  "response": {
    "detail": [
      {
        "loc": [
          "body",
          "password"
        ],
        "msg": "Value should have at least 8 items after validation, not 3",
        "type": "too_short"
      }
    ]
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:19 GMT",
    "server": "uvicorn",
    "content-length": "126",
    "content-type": "application/json",
    "x-process-time": "0.002490",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "d4b02e0b-f46c-46f5-bf97-850c3af0ddd2"
  }
}
```

## 3. Email duplicado

Comprobaciones:

```json
{
  "users_before": 1,
  "users_after": 1
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/register",
    "headers": {},
    "json": {
      "name": "Usuario Prueba",
      "email": "usuario.ev11@example.com",
      "password": "Usuario123",
      "role": "user"
    },
    "form": null
  },
  "http": 400,
  "response": {
    "detail": "El correo electrónico ya está registrado"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:19 GMT",
    "server": "uvicorn",
    "content-length": "55",
    "content-type": "application/json",
    "x-process-time": "0.003047",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "ccc11da1-4451-4e9e-832a-c14297aa6bad"
  }
}
```

## 4. Login correcto

Comprobaciones:

```json
{
  "token_generated": true,
  "signature_and_subject_verified": true
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/login",
    "headers": {},
    "json": null,
    "form": {
      "username": "usuario.ev11@example.com",
      "password": "Usuario123"
    }
  },
  "http": 200,
  "response": {
    "access_token": "[JWT OMITIDO]",
    "token_type": "bearer"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:19 GMT",
    "server": "uvicorn",
    "content-length": "182",
    "content-type": "application/json",
    "x-process-time": "0.342011",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "3f2b5767-2fc3-4909-bbc0-c8092ce1680a"
  }
}
```

## 5. Contrasena incorrecta

Comprobaciones:

```json
{}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/login",
    "headers": {},
    "json": null,
    "form": {
      "username": "usuario.ev11@example.com",
      "password": "Incorrecta123"
    }
  },
  "http": 401,
  "response": {
    "detail": "Correo o contraseña incorrectos"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:19 GMT",
    "server": "uvicorn",
    "www-authenticate": "Bearer",
    "content-length": "45",
    "content-type": "application/json",
    "x-process-time": "0.371753",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "76f3d89d-8bc4-43cf-9198-11849af97507"
  }
}
```

## 6. Consultar mi usuario

Comprobaciones:

```json
{
  "correct_user": true,
  "credentials_absent": true
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "GET",
    "path": "/auth/me",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": null,
    "form": null
  },
  "http": 200,
  "response": {
    "name": "Usuario Prueba",
    "email": "usuario.ev11@example.com",
    "role": "user",
    "is_active": true,
    "id": 1,
    "created_at": "2026-09-21T23:40:19.074605"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:20 GMT",
    "server": "uvicorn",
    "content-length": "140",
    "content-type": "application/json",
    "x-process-time": "0.005037",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "c313a80d-0cc2-453a-9663-85a562815d87"
  }
}
```

## 7. Sin token

Comprobaciones:

```json
{}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "GET",
    "path": "/users",
    "headers": {},
    "json": null,
    "form": null
  },
  "http": 401,
  "response": {
    "detail": "No autenticado o token inválido"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:20 GMT",
    "server": "uvicorn",
    "www-authenticate": "Bearer",
    "content-length": "45",
    "content-type": "application/json",
    "x-process-time": "0.001867",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "66b437d1-7ede-4cd7-95aa-32ecd778fa4f"
  }
}
```

## 8. Token invalido

Comprobaciones:

```json
{}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "GET",
    "path": "/users",
    "headers": {
      "Authorization": "Bearer token_invalido"
    },
    "json": null,
    "form": null
  },
  "http": 401,
  "response": {
    "detail": "No autenticado o token inválido"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:20 GMT",
    "server": "uvicorn",
    "www-authenticate": "Bearer",
    "content-length": "45",
    "content-type": "application/json",
    "x-process-time": "0.001502",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "9a34ec00-3042-4987-badd-b13d3e7bb0ca"
  }
}
```

## 9. Usuario sin permisos

Comprobaciones:

```json
{}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/devices",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": {
      "name": "Laptop Lenovo ThinkPad",
      "serial_number": "EV11-FASE13-001",
      "device_type": "laptop",
      "brand": "Lenovo",
      "is_available": true
    },
    "form": null
  },
  "http": 403,
  "response": {
    "detail": "Se requiere rol admin o support"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:20 GMT",
    "server": "uvicorn",
    "content-length": "44",
    "content-type": "application/json",
    "x-process-time": "0.004427",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "574f1172-9bd1-44a8-949a-248fb0954742"
  }
}
```

## 10. Crear dispositivo con rol permitido

Comprobaciones:

```json
{
  "created_device_id": 1
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "POST",
    "path": "/devices",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": {
      "name": "Laptop Lenovo ThinkPad",
      "serial_number": "EV11-FASE13-001",
      "device_type": "laptop",
      "brand": "Lenovo",
      "is_available": true
    },
    "form": null
  },
  "http": 201,
  "response": {
    "name": "Laptop Lenovo ThinkPad",
    "serial_number": "EV11-FASE13-001",
    "device_type": "laptop",
    "brand": "Lenovo",
    "is_available": true,
    "id": 1,
    "created_at": "2026-09-21T23:40:21.641138"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "content-length": "176",
    "content-type": "application/json",
    "x-process-time": "0.012734",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "e9e5c8ae-ee4e-46dc-a2b6-ffadd56f7ed9"
  }
}
```

## 11. Eliminar con rol no permitido

Comprobaciones:

```json
{
  "device_preserved": true
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "DELETE",
    "path": "/devices/1",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": null,
    "form": null
  },
  "http": 403,
  "response": {
    "detail": "Se requiere rol admin"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "content-length": "34",
    "content-type": "application/json",
    "x-process-time": "0.004763",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "ab21f623-04cb-4a43-a43d-d989e60a49e4"
  }
}
```

```json
{
  "request": {
    "method": "GET",
    "path": "/devices/1",
    "headers": {},
    "json": null,
    "form": null
  },
  "http": 200,
  "response": {
    "name": "Laptop Lenovo ThinkPad",
    "serial_number": "EV11-FASE13-001",
    "device_type": "laptop",
    "brand": "Lenovo",
    "is_available": true,
    "id": 1,
    "created_at": "2026-09-21T23:40:21.641138"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "content-length": "176",
    "content-type": "application/json",
    "x-process-time": "0.002915",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "46dd9022-9656-45de-bcff-2dcae972437a"
  }
}
```

## 12. CORS

Comprobaciones:

```json
{
  "configuration": {
    "allow_origins": [
      "http://localhost:5173",
      "http://localhost:3000"
    ],
    "allow_credentials": true,
    "allow_methods": [
      "*"
    ],
    "allow_headers": [
      "*"
    ],
    "expose_headers": [
      "X-Process-Time",
      "X-App-Name",
      "X-API-Version",
      "X-Request-ID"
    ]
  }
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "OPTIONS",
    "path": "/users",
    "headers": {
      "Origin": "http://localhost:5173",
      "Access-Control-Request-Method": "GET",
      "Access-Control-Request-Headers": "Authorization, Content-Type"
    },
    "json": null,
    "form": null
  },
  "http": 200,
  "response": "OK",
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "vary": "Origin",
    "access-control-allow-methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
    "access-control-max-age": "600",
    "access-control-allow-credentials": "true",
    "access-control-allow-origin": "http://localhost:5173",
    "access-control-allow-headers": "Authorization, Content-Type",
    "content-length": "2",
    "content-type": "text/plain; charset=utf-8",
    "x-process-time": "0.000069",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "66969e95-3636-413b-848e-7a34eeda13b4"
  }
}
```

```json
{
  "request": {
    "method": "GET",
    "path": "/users",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]",
      "Origin": "http://localhost:5173"
    },
    "json": null,
    "form": null
  },
  "http": 200,
  "response": [
    {
      "name": "Cuenta admin",
      "email": "admin.ev11@example.com",
      "role": "admin",
      "is_active": true,
      "id": 3,
      "created_at": "2026-09-21T23:40:21.272488"
    },
    {
      "name": "Cuenta support",
      "email": "support.ev11@example.com",
      "role": "support",
      "is_active": true,
      "id": 2,
      "created_at": "2026-09-21T23:40:20.489254"
    },
    {
      "name": "Usuario Prueba",
      "email": "usuario.ev11@example.com",
      "role": "user",
      "is_active": true,
      "id": 1,
      "created_at": "2026-09-21T23:40:19.074605"
    }
  ],
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "content-length": "424",
    "content-type": "application/json",
    "access-control-allow-credentials": "true",
    "access-control-expose-headers": "X-Process-Time, X-App-Name, X-API-Version, X-Request-ID",
    "access-control-allow-origin": "http://localhost:5173",
    "vary": "Origin",
    "x-process-time": "0.004883",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "0f31e548-e182-47ef-a5d8-3a9bb001410b"
  }
}
```

```json
{
  "request": {
    "method": "OPTIONS",
    "path": "/users",
    "headers": {
      "Origin": "http://localhost:3000",
      "Access-Control-Request-Method": "GET",
      "Access-Control-Request-Headers": "Authorization, Content-Type"
    },
    "json": null,
    "form": null
  },
  "http": 200,
  "response": "OK",
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "vary": "Origin",
    "access-control-allow-methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
    "access-control-max-age": "600",
    "access-control-allow-credentials": "true",
    "access-control-allow-origin": "http://localhost:3000",
    "access-control-allow-headers": "Authorization, Content-Type",
    "content-length": "2",
    "content-type": "text/plain; charset=utf-8",
    "x-process-time": "0.000069",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "c9e10b7b-6bc9-4184-9314-2b74cb26f6a9"
  }
}
```

```json
{
  "request": {
    "method": "GET",
    "path": "/users",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]",
      "Origin": "http://localhost:3000"
    },
    "json": null,
    "form": null
  },
  "http": 200,
  "response": [
    {
      "name": "Cuenta admin",
      "email": "admin.ev11@example.com",
      "role": "admin",
      "is_active": true,
      "id": 3,
      "created_at": "2026-09-21T23:40:21.272488"
    },
    {
      "name": "Cuenta support",
      "email": "support.ev11@example.com",
      "role": "support",
      "is_active": true,
      "id": 2,
      "created_at": "2026-09-21T23:40:20.489254"
    },
    {
      "name": "Usuario Prueba",
      "email": "usuario.ev11@example.com",
      "role": "user",
      "is_active": true,
      "id": 1,
      "created_at": "2026-09-21T23:40:19.074605"
    }
  ],
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "content-length": "424",
    "content-type": "application/json",
    "access-control-allow-credentials": "true",
    "access-control-expose-headers": "X-Process-Time, X-App-Name, X-API-Version, X-Request-ID",
    "access-control-allow-origin": "http://localhost:3000",
    "vary": "Origin",
    "x-process-time": "0.004016",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "c276295d-e111-4a29-aa14-8d7e1a669c48"
  }
}
```

```json
{
  "request": {
    "method": "OPTIONS",
    "path": "/users",
    "headers": {
      "Origin": "https://untrusted.example",
      "Access-Control-Request-Method": "GET"
    },
    "json": null,
    "form": null
  },
  "http": 400,
  "response": "Disallowed CORS origin",
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "vary": "Origin",
    "access-control-allow-methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
    "access-control-max-age": "600",
    "access-control-allow-credentials": "true",
    "content-length": "22",
    "content-type": "text/plain; charset=utf-8",
    "x-process-time": "0.000056",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "5fab6a46-6571-42c7-afd2-f5927a9d861d"
  }
}
```

## 13. Cabeceras y log del middleware

Comprobaciones:

```json
{
  "headers": {
    "X-App-Name": "device_systems",
    "X-Process-Time": "0.004118",
    "X-Request-ID": "363a7da3-ea90-48ef-b178-6d189e87ab42"
  },
  "real_log": [
    "method=GET path='/users' status=200 request_id=363a7da3-ea90-48ef-b178-6d189e87ab42 duration=0.005160"
  ]
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "GET",
    "path": "/users",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": null,
    "form": null
  },
  "http": 200,
  "response": [
    {
      "name": "Cuenta admin",
      "email": "admin.ev11@example.com",
      "role": "admin",
      "is_active": true,
      "id": 3,
      "created_at": "2026-09-21T23:40:21.272488"
    },
    {
      "name": "Cuenta support",
      "email": "support.ev11@example.com",
      "role": "support",
      "is_active": true,
      "id": 2,
      "created_at": "2026-09-21T23:40:20.489254"
    },
    {
      "name": "Usuario Prueba",
      "email": "usuario.ev11@example.com",
      "role": "user",
      "is_active": true,
      "id": 1,
      "created_at": "2026-09-21T23:40:19.074605"
    }
  ],
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:21 GMT",
    "server": "uvicorn",
    "content-length": "424",
    "content-type": "application/json",
    "x-process-time": "0.004118",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "363a7da3-ea90-48ef-b178-6d189e87ab42"
  }
}
```

## 14. Rate limiting real

Comprobaciones:

```json
{
  "/auth/login": {
    "limit_per_minute": 5,
    "requests": 6,
    "codes": [
      200,
      200,
      200,
      200,
      200,
      429
    ],
    "first_429": 6,
    "response_429": {
      "error": "Rate limit exceeded: 5 per 1 minute"
    },
    "elapsed_seconds": 1.7839424000121653
  },
  "/auth/register": {
    "limit_per_minute": 3,
    "requests": 4,
    "codes": [
      201,
      201,
      201,
      429
    ],
    "first_429": 4,
    "response_429": {
      "error": "Rate limit exceeded: 3 per 1 minute"
    },
    "elapsed_seconds": 1.0109310999978334
  },
  "/users": {
    "limit_per_minute": 30,
    "requests": 31,
    "codes": [
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      200,
      429
    ],
    "first_429": 31,
    "response_429": {
      "error": "Rate limit exceeded: 30 per 1 minute"
    },
    "elapsed_seconds": 0.19713570002932101
  },
  "/loans": {
    "limit_per_minute": 10,
    "requests": 11,
    "codes": [
      201,
      201,
      201,
      201,
      201,
      201,
      201,
      201,
      201,
      201,
      429
    ],
    "first_429": 11,
    "response_429": {
      "error": "Rate limit exceeded: 10 per 1 minute"
    },
    "elapsed_seconds": 0.2416333999717608
  }
}
```

Peticiones y respuestas (JWT omitidos):

Se muestran las cuatro peticiones bloqueadas. Todas las solicitudes previas y sus respuestas estan en fase13_resultados.json.

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/login",
    "headers": {},
    "json": null,
    "form": {
      "username": "usuario.ev11@example.com",
      "password": "Usuario123"
    }
  },
  "http": 429,
  "response": {
    "error": "Rate limit exceeded: 5 per 1 minute"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:23 GMT",
    "server": "uvicorn",
    "content-length": "47",
    "content-type": "application/json",
    "x-process-time": "0.002466",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "ba2a6171-5757-4cd6-bcde-8a6e0435f7a3"
  }
}
```

```json
{
  "request": {
    "method": "POST",
    "path": "/auth/register",
    "headers": {},
    "json": {
      "name": "Usuario Prueba",
      "email": "limite3.ev11@example.com",
      "password": "Usuario123",
      "role": "user"
    },
    "form": null
  },
  "http": 429,
  "response": {
    "error": "Rate limit exceeded: 3 per 1 minute"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:23 GMT",
    "server": "uvicorn",
    "content-length": "47",
    "content-type": "application/json",
    "x-process-time": "0.001806",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "ad54a154-aef0-4b3d-b242-fb048a4452cb"
  }
}
```

```json
{
  "request": {
    "method": "GET",
    "path": "/users",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": null,
    "form": null
  },
  "http": 429,
  "response": {
    "error": "Rate limit exceeded: 30 per 1 minute"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:24 GMT",
    "server": "uvicorn",
    "content-length": "48",
    "content-type": "application/json",
    "x-process-time": "0.003804",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "ded46d3d-d63b-4fe0-8b7a-f98af83b8714"
  }
}
```

```json
{
  "request": {
    "method": "POST",
    "path": "/loans",
    "headers": {
      "Authorization": "Bearer [JWT OMITIDO]"
    },
    "json": {
      "user_id": 1,
      "device_id": 12,
      "status": "active"
    },
    "form": null
  },
  "http": 429,
  "response": {
    "error": "Rate limit exceeded: 10 per 1 minute"
  },
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:24 GMT",
    "server": "uvicorn",
    "content-length": "48",
    "content-type": "application/json",
    "x-process-time": "0.003179",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "2127cf18-4189-454a-a3bb-63601c611f4e"
  }
}
```

## 15. Swagger / OpenAPI

Comprobaciones:

```json
{
  "info": {
    "title": "device_systems API",
    "description": "API REST segura para gestión de usuarios, dispositivos y préstamos",
    "contact": {
      "name": "Samir Acosta Peña"
    },
    "version": "3.0.0"
  },
  "tags": [
    "Auth",
    "Users",
    "Devices",
    "Loans",
    "Security"
  ],
  "oauth2": {
    "type": "oauth2",
    "flows": {
      "password": {
        "scopes": {},
        "tokenUrl": "auth/login"
      }
    }
  },
  "protected_operations": [
    [
      "get",
      "/users"
    ],
    [
      "get",
      "/users/{user_id}"
    ],
    [
      "post",
      "/devices"
    ],
    [
      "put",
      "/devices/{device_id}"
    ],
    [
      "delete",
      "/devices/{device_id}"
    ],
    [
      "post",
      "/loans"
    ],
    [
      "patch",
      "/loans/{loan_id}/return"
    ],
    [
      "get",
      "/loans/details"
    ],
    [
      "get",
      "/auth/me"
    ]
  ],
  "models": [
    "DeviceCreate",
    "DeviceResponse",
    "DeviceUpdate",
    "HTTPValidationError",
    "LoanCreate",
    "LoanDetailResponse",
    "LoanResponse",
    "Token",
    "UserCreate",
    "UserPatch",
    "UserRegister",
    "UserResponse",
    "UserUpdate",
    "ValidationError",
    "_LoanDeviceResponse",
    "_LoanUserResponse"
  ],
  "visual_authorize": "No ejecutado; captura manual pendiente"
}
```

Peticiones y respuestas (JWT omitidos):

```json
{
  "request": {
    "method": "GET",
    "path": "/docs",
    "headers": {},
    "json": null,
    "form": null
  },
  "http": 200,
  "response": "\n    <!DOCTYPE html>\n    <html>\n    <head>\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <link type=\"text/css\" rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css\">\n    <link rel=\"shortcut icon\" href=\"https://fastapi.tiangolo.com/img/favicon.png\">\n    <title>device_systems API - Swagger UI</title>\n    </head>\n    <body>\n    <div id=\"swagger-ui\">\n    </div>\n    <script src=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>\n    <!-- `SwaggerUIBundle` is now available on the page -->\n    <script>\n    const ui = SwaggerUIBundle({\n        url: '/openapi.json',\n    \"dom_id\": \"#swagger-ui\",\n\"layout\": \"BaseLayout\",\n\"deepLinking\": true,\n\"showExtensions\": true,\n\"showCommonExtensions\": true,\noauth2RedirectUrl: window.location.origin + '/docs/oauth2-redirect',\n    presets: [\n        SwaggerUIBundle.presets.apis,\n        SwaggerUIBundle.SwaggerUIStandalonePreset\n        ],\n    })\n    </script>\n    </body>\n    </html>\n    ",
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:24 GMT",
    "server": "uvicorn",
    "content-length": "1017",
    "content-type": "text/html; charset=utf-8",
    "x-process-time": "0.000144",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "f035e214-9794-4929-ae9d-a69fa71a309d"
  }
}
```

```json
{
  "request": {
    "method": "GET",
    "path": "/openapi.json",
    "headers": {},
    "json": null,
    "form": null
  },
  "http": 200,
  "response": "Esquema completo conservado en fase13_resultados.json; comprobaciones arriba.",
  "response_headers": {
    "date": "Mon, 21 Sep 2026 23:40:24 GMT",
    "server": "uvicorn",
    "content-length": "26124",
    "content-type": "application/json",
    "x-process-time": "0.112527",
    "x-app-name": "device_systems",
    "x-api-version": "3.0.0",
    "x-request-id": "23c9af58-3e3f-4ce0-a966-8327a21ccfc3"
  }
}
```

## Incidencia del primer intento

El primer intento dio 14 PASS y 1 FAIL: la prueba 13 recibio HTTP 200 y las cabeceras correctas, pero no capturo el log. Causa reproducida: fileConfig de Alembic cambio logger.disabled de False a True al ejecutar la migracion en el mismo proceso de la API; configurar Uvicorn no lo restauro. Se corrigio exclusivamente el ejecutor nuevo para ejecutar Alembic en un proceso separado. La aplicacion y las pruebas existentes no cambiaron. El primer resultado se conserva en fase13_intento_inicial.json. La repeticion completa dio 15 PASS.

## Suite pytest posterior

Comando: `.\.venv\Scripts\python.exe -m pytest`. 142 passed, 0 failed, 2 warnings, 25.31 segundos. Son pruebas pytest, distintas de los 15 escenarios funcionales. Salida literal:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\SAMIR ACOSTA\device_systems
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 142 items

tests\test_security.py ................................................. [ 34%]
....................                                                     [ 48%]
tests\test_security_migration.py ..                                      [ 50%]
tests\test_users.py .................................................... [ 86%]
...................                                                      [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\SAMIR ACOSTA\device_systems\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  C:\Users\SAMIR ACOSTA\device_systems\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== 142 passed, 2 warnings in 25.31s =======================
```

## Alembic

Comandos current y heads sobre la configuracion local: ambos devolvieron `f3a91c2d7b60 (head)`. Las migraciones de esta ejecucion solo se aplicaron a SQLite temporal.

## Capturas manuales pendientes

No se generaron capturas ni se usaron imagenes antiguas. Authorize visual no se ejecuto; la comprobacion automatica cubrio HTTP y OpenAPI. La siguiente lista identifica el contenido a capturar, no acredita que existan capturas:

1. Estructura: app/auth, dependencies, middlewares, models, schemas, routes, alembic y rama device_systems_security; mostrar tambien la rama activa real.
2. Alembic: salidas reales de current y heads (f3a91c2d7b60), y archivo de migracion.
3. Prueba 1: POST /auth/register role=user, HTTP 201 y response sin hashed_password; verificacion de persistencia/hash del informe.
4. Prueba 2: contrasena debil y HTTP 422 con el mensaje Pydantic.
5. Prueba 3: email duplicado, HTTP 400 y comprobacion de un solo usuario.
6. Prueba 4: login correcto, HTTP 200 y token_type=bearer; ocultar access_token y contrasena.
7. Prueba 5: login incorrecto, HTTP 401 y respuesta.
8. Prueba 6: /auth/me, HTTP 200 y usuario esperado; ocultar Authorization.
9. Prueba 7: GET /users sin Authorization y HTTP 401.
10. Prueba 8: GET /users con token_invalido y HTTP 401.
11. Prueba 9: POST /devices con role=user y HTTP 403.
12. Prueba 10: POST /devices con role=support, body real y HTTP 201.
13. Prueba 11: DELETE /devices/{id} con role=support y HTTP 403; dispositivo conservado.
14. Prueba 12: preflight para localhost:5173 y localhost:3000, cabeceras CORS y rechazo del origen ajeno.
15. Prueba 13: X-App-Name, X-Process-Time, X-Request-ID y linea de log del mismo request_id.
16. Prueba 14: secuencias y primer 429 de login (6), register (4), users (31) y loans (11).
17. Prueba 15: Swagger en navegador, title/version/tags, Authorize OAuth2 y ejecucion autenticada; ocultar JWT y contrasena.
18. Pytest completo y estado Git: 142 passed, warnings, tiempo, git status y git diff --stat.

## Archivos y Git

README.md ya estaba modificado al empezar esta fase y se conservo sin cambios adicionales. Se conservaron sus espacios para evidencias. Se crearon un ejecutor en docs y cuatro archivos de evidencia; no se modificaron app/, tests/ ni dependencias. No se hizo commit, push ni merge.

Archivos nuevos:

- docs/verificar_fase13.py
- docs/evidencias/fase13_pruebas_funcionales.md
- docs/evidencias/fase13_resultados.json
- docs/evidencias/fase13_intento_inicial.json
- docs/evidencias/fase13_pytest.txt

git diff --stat (no incluye archivos nuevos sin seguimiento):

```text
README.md | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

git status:

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   README.md

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/evidencias/fase13_intento_inicial.json
	docs/evidencias/fase13_pruebas_funcionales.md
	docs/evidencias/fase13_pytest.txt
	docs/evidencias/fase13_resultados.json
	docs/verificar_fase13.py

no changes added to commit (use "git add" and/or "git commit -a")
```

Aviso adicional de Git: LF sera reemplazado por CRLF en README.md la proxima vez que Git lo procese.
