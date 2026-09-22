"""Ejecuta Fase 13 por HTTP real sobre SQLite temporal y documenta resultados.

Desde la raiz: .venv/Scripts/python.exe docs/verificar_fase13.py
No modifica la aplicacion, sus pruebas ni la base de trabajo. No genera capturas.
"""
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "docs" / "evidencias"


def main():
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "transport": "HTTP real: httpx -> socket TCP local -> Uvicorn -> aplicacion existente",
              "isolation": "SQLite temporal migrada con Alembic; contadores reiniciados entre escenarios, nunca durante una secuencia de limite",
              "setup": [], "tests": [], "screenshots": "Ninguna; Authorize visual pendiente de captura manual"}
    current = report["setup"]
    with tempfile.TemporaryDirectory(prefix="ev11_fase13_") as temporary:
        database = Path(temporary) / "fase13.db"
        os.environ["DATABASE_URL"] = "sqlite:///" + database.as_posix()
        os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
        os.environ["ALGORITHM"] = "HS256"
        from sqlalchemy import create_engine, select, func
        from sqlalchemy.orm import Session
        import uvicorn
        from app.main import app
        from app.database.connection import engine
        from app.models.user_model import User
        from app.auth.security import verify_password, decode_access_token
        from app.middlewares.request_middleware import limiter

        # Alembic configura logging con fileConfig: aislarlo como en el uso CLI
        # evita que desactive el logger de la API en este proceso.
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True)
        report["alembic_temporary_database"] = "upgrade head ejecutado correctamente"
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", access_log=False))
        logs = []

        class Capture(logging.Handler):
            def emit(self, record):
                logs.append(record.getMessage())

        logger = logging.getLogger("uvicorn.error.requests")
        handler = Capture()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        bound = socket.socket()
        bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
        thread = threading.Thread(target=server.run, kwargs={"sockets": [bound]}, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        report["base_url"] = base
        password = "Usuario123"
        user_body = {"name": "Usuario Prueba", "email": "usuario.ev11@example.com", "password": password, "role": "user"}
        device_body = {"name": "Laptop Lenovo ThinkPad", "serial_number": "EV11-FASE13-001", "device_type": "laptop", "brand": "Lenovo", "is_available": True}
        accounts, headers = {}, {}

        def require(condition, message):
            if not condition:
                raise AssertionError(message)

        def run(number, name, endpoint, role, expected, action):
            nonlocal current
            case = {"number": number, "test": name, "endpoint": endpoint, "role": role,
                    "expected": expected, "requests": [], "checks": {}}
            report["tests"].append(case)
            current = case["requests"]
            limiter.reset()
            try:
                action(case["checks"])
                case["result"] = "PASS"
            except Exception as error:
                case["result"] = "FAIL"
                case["cause"] = f"{type(error).__name__}: {error}"
            print(f"{number:02d} {name}: {case['result']}", flush=True)

        try:
            for _ in range(200):
                if server.started:
                    break
                if not thread.is_alive():
                    raise RuntimeError("Uvicorn termino antes del arranque")
                time.sleep(0.05)
            require(server.started, "Uvicorn no inicio")
            with httpx.Client(base_url=base, timeout=20) as client:
                def request(method, path, expected, role=None, **kwargs):
                    if role:
                        kwargs["headers"] = headers[role] | kwargs.get("headers", {})
                    response = client.request(method, path, **kwargs)
                    try:
                        body = response.json()
                    except ValueError:
                        body = response.text
                    if isinstance(body, dict) and "access_token" in body:
                        body = body | {"access_token": "[JWT OMITIDO]"}
                    shown_headers = dict(kwargs.get("headers", {}))
                    if "Authorization" in shown_headers and shown_headers["Authorization"] != "Bearer token_invalido":
                        shown_headers["Authorization"] = "Bearer [JWT OMITIDO]"
                    current.append({"request": {"method": method, "path": path, "headers": shown_headers,
                                                "json": kwargs.get("json"), "form": kwargs.get("data")},
                                    "http": response.status_code, "response": body,
                                    "response_headers": dict(response.headers)})
                    require(response.status_code == expected, f"{method} {path}: HTTP {response.status_code}, esperado {expected}; respuesta={body}")
                    return response

                def registration(checks):
                    response = request("POST", "/auth/register", 201, json=user_body)
                    accounts["user"] = response.json()
                    require("hashed_password" not in response.text and password not in response.text, "Credenciales expuestas")
                    independent = create_engine(os.environ["DATABASE_URL"])
                    try:
                        with Session(independent) as db:
                            user = db.scalar(select(User).where(User.email == user_body["email"]))
                            checks.update(persisted_from_independent_connection=user is not None,
                                          password_not_plaintext=user.hashed_password != password,
                                          stored_hash_verifies_password=verify_password(password, user.hashed_password),
                                          hashed_password_absent_in_response="hashed_password" not in response.text)
                            require(all(checks.values()), "Fallo en persistencia/hash/confidencialidad")
                    finally:
                        independent.dispose()

                run(1, "Registro de usuario", "POST /auth/register", "user", "201; persistencia y hash seguro", registration)

                def weak(checks):
                    response = request("POST", "/auth/register", 422, json=user_body | {"name": "Usuario Debil", "email": "debil.ev11@example.com", "password": "123"})
                    checks["validation"] = response.json()
                    require(any("password" in error["loc"] for error in response.json()["detail"]), "Falta validacion de password")
                run(2, "Contrasena debil", "POST /auth/register", "user", "422, rechazo Pydantic", weak)

                def duplicate(checks):
                    def count():
                        with Session(engine) as db:
                            return db.scalar(select(func.count()).select_from(User).where(User.email == user_body["email"]))
                    before = count()
                    request("POST", "/auth/register", 400, json=user_body)
                    checks.update(users_before=before, users_after=count())
                    require(checks["users_before"] == checks["users_after"] == 1, "El duplicado altero el numero de usuarios")
                run(3, "Email duplicado", "POST /auth/register", "user", "400; sigue existiendo un solo usuario", duplicate)

                def login(checks):
                    response = request("POST", "/auth/login", 200, data={"username": user_body["email"], "password": password})
                    data = response.json()
                    require(data["access_token"] and data["token_type"] == "bearer", "No se genero Bearer")
                    require(decode_access_token(data["access_token"])["sub"] == str(accounts["user"]["id"]), "JWT de usuario incorrecto")
                    headers["user"] = {"Authorization": "Bearer " + data["access_token"]}
                    checks.update(token_generated=True, signature_and_subject_verified=True)
                run(4, "Login correcto", "POST /auth/login", "user", "200; access_token y token_type=bearer", login)
                run(5, "Contrasena incorrecta", "POST /auth/login", "user", "401", lambda c: request("POST", "/auth/login", 401, data={"username": user_body["email"], "password": "Incorrecta123"}))

                def me(checks):
                    response = request("GET", "/auth/me", 200, role="user")
                    require(response.json() == accounts["user"], "Datos de usuario diferentes")
                    require("password" not in response.text and password not in response.text, "Credenciales expuestas")
                    checks.update(correct_user=True, credentials_absent=True)
                run(6, "Consultar mi usuario", "GET /auth/me", "user", "200; usuario correcto sin credenciales", me)
                run(7, "Sin token", "GET /users", "ninguno", "401", lambda c: request("GET", "/users", 401))
                run(8, "Token invalido", "GET /users", "ninguno", "401", lambda c: request("GET", "/users", 401, headers={"Authorization": "Bearer token_invalido"}))
                run(9, "Usuario sin permisos", "POST /devices", "user", "403", lambda c: request("POST", "/devices", 403, role="user", json=device_body))

                current = report["setup"]
                limiter.reset()
                for role in ("support", "admin"):
                    body = user_body | {"name": "Cuenta " + role, "email": role + ".ev11@example.com", "role": role}
                    accounts[role] = request("POST", "/auth/register", 201, json=body).json()
                    response = request("POST", "/auth/login", 200, data={"username": body["email"], "password": password})
                    headers[role] = {"Authorization": "Bearer " + response.json()["access_token"]}

                device = {}
                def create_device(checks):
                    response = request("POST", "/devices", 201, role="support", json=device_body)
                    device.update(response.json())
                    require(all(device[k] == v for k, v in device_body.items()), "Dispositivo diferente del enviado")
                    checks["created_device_id"] = device["id"]
                run(10, "Crear dispositivo con rol permitido", "POST /devices", "support", "201", create_device)

                def delete_forbidden(checks):
                    request("DELETE", f"/devices/{device['id']}", 403, role="support")
                    response = request("GET", f"/devices/{device['id']}", 200)
                    require(response.json() == device, "El dispositivo fue alterado/eliminado")
                    checks["device_preserved"] = True
                run(11, "Eliminar con rol no permitido", "DELETE /devices/{device_id}", "support", "403; dispositivo conservado", delete_forbidden)

                def cors(checks):
                    middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
                    checks["configuration"] = middleware.kwargs
                    require(middleware.kwargs["allow_credentials"] is True, "allow_credentials incorrecto")
                    require(middleware.kwargs["allow_methods"] == ["*"] and middleware.kwargs["allow_headers"] == ["*"], "Metodos/cabeceras configurados diferentes")
                    for origin in ["http://localhost:5173", "http://localhost:3000"]:
                        response = request("OPTIONS", "/users", 200, headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization, Content-Type"})
                        require(response.headers["access-control-allow-origin"] == origin, "Origen no permitido")
                        require(response.headers["access-control-allow-credentials"] == "true", "Credenciales CORS ausentes")
                        require("GET" in response.headers["access-control-allow-methods"], "GET ausente")
                        require("authorization" in response.headers["access-control-allow-headers"].lower(), "Authorization ausente")
                        response = request("GET", "/users", 200, role="user", headers={"Origin": origin})
                        require(response.headers["access-control-allow-origin"] == origin, "Falta CORS en GET real")
                    response = request("OPTIONS", "/users", 400, headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"})
                    require("access-control-allow-origin" not in response.headers, "Origen ajeno autorizado")
                run(12, "CORS", "OPTIONS y GET /users", "user / preflight sin token", "200 locales; 400 origen ajeno", cors)

                def middleware(checks):
                    response = request("GET", "/users", 200, role="user")
                    values = {name: response.headers[name] for name in ["X-App-Name", "X-Process-Time", "X-Request-ID"]}
                    require(values["X-App-Name"] == "device_systems" and float(values["X-Process-Time"]) >= 0 and values["X-Request-ID"], "Cabeceras incorrectas")
                    for _ in range(100):
                        matching = [line for line in logs if values["X-Request-ID"] in line]
                        if matching:
                            break
                        time.sleep(0.01)
                    require(any("method=GET" in line and "path='/users'" in line and "status=200" in line for line in matching), "Falta log de metodo/ruta/status")
                    checks.update(headers=values, real_log=matching)
                run(13, "Cabeceras y log del middleware", "GET /users", "user", "200; tres cabeceras y log real", middleware)

                def rates(checks):
                    for endpoint, limit in [("/auth/login", 5), ("/auth/register", 3), ("/users", 30), ("/loans", 10)]:
                        limiter.reset()
                        codes = []
                        started = time.monotonic()
                        for index in range(limit + 1):
                            last = index == limit
                            if endpoint == "/auth/login":
                                response = request("POST", endpoint, 429 if last else 200, data={"username": user_body["email"], "password": password})
                            elif endpoint == "/auth/register":
                                response = request("POST", endpoint, 429 if last else 201, json=user_body | {"email": f"limite{index}.ev11@example.com"})
                            elif endpoint == "/users":
                                response = request("GET", endpoint, 429 if last else 200, role="user")
                            else:
                                created = request("POST", "/devices", 201, role="admin", json=device_body | {"serial_number": f"RATE-FASE13-{index}"}).json()
                                response = request("POST", endpoint, 429 if last else 201, role="user", json={"user_id": accounts["user"]["id"], "device_id": created["id"], "status": "active"})
                            codes.append(response.status_code)
                        elapsed = time.monotonic() - started
                        require(elapsed < 60, "La secuencia excedio un minuto")
                        require(response.json() == {"error": f"Rate limit exceeded: {limit} per 1 minute"}, "Respuesta de limite inesperada")
                        checks[endpoint] = {"limit_per_minute": limit, "requests": len(codes), "codes": codes, "first_429": codes.index(429) + 1, "response_429": response.json(), "elapsed_seconds": elapsed}
                run(14, "Rate limiting real", "POST /auth/login; POST /auth/register; GET /users; POST /loans", "user; admin prepara dispositivos", "429 en solicitudes 6, 4, 31 y 11", rates)

                def swagger(checks):
                    response = request("GET", "/docs", 200)
                    require("SwaggerUIBundle" in response.text, "HTML no contiene Swagger")
                    schema = request("GET", "/openapi.json", 200).json()
                    require(schema["info"]["title"] == "device_systems API" and schema["info"]["version"] == "3.0.0", "Metadatos incorrectos")
                    tags = [t["name"] for t in schema["tags"]]
                    require(set(tags) == {"Auth", "Users", "Devices", "Loans", "Security"}, "Tags incorrectos")
                    oauth = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
                    require(oauth["type"] == "oauth2" and oauth["flows"]["password"]["tokenUrl"] == "auth/login", "OAuth2 incorrecto")
                    protected = [("get", "/users"), ("get", "/users/{user_id}"), ("post", "/devices"), ("put", "/devices/{device_id}"), ("delete", "/devices/{device_id}"), ("post", "/loans"), ("patch", "/loans/{loan_id}/return"), ("get", "/loans/details"), ("get", "/auth/me")]
                    for method, path in protected:
                        require(schema["paths"][path][method]["security"] == [{"OAuth2PasswordBearer": []}], f"Falta seguridad OpenAPI: {method} {path}")
                    for path in ["/auth/register", "/auth/login", "/auth/me", "/users", "/devices", "/loans"]:
                        require(path in schema["paths"], "Falta ruta " + path)
                    models = schema["components"]["schemas"]
                    for name in ["UserRegister", "Token", "UserResponse", "DeviceCreate", "DeviceResponse", "LoanCreate", "LoanResponse"]:
                        require(name in models, "Falta modelo " + name)
                    for path, input_model, output_model in [("/auth/register", "UserRegister", "UserResponse"), ("/devices", "DeviceCreate", "DeviceResponse"), ("/loans", "LoanCreate", "LoanResponse")]:
                        operation = schema["paths"][path]["post"]
                        require(operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/" + input_model), "Modelo de entrada incorrecto")
                        require(operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith("/" + output_model), "Modelo de salida incorrecto")
                    require("hashed_password" not in json.dumps(schema), "Hash expuesto en OpenAPI")
                    checks.update(info=schema["info"], tags=tags, oauth2=oauth, protected_operations=protected, models=list(models), visual_authorize="No ejecutado; captura manual pendiente")
                run(15, "Swagger / OpenAPI", "GET /docs; GET /openapi.json", "ninguno", "200; metadatos, OAuth2, rutas y modelos correctos", swagger)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            bound.close()
            engine.dispose()
            logger.removeHandler(handler)
            report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            report["summary"] = {"passed": sum(t.get("result") == "PASS" for t in report["tests"]), "failed": sum(t.get("result") == "FAIL" for t in report["tests"])}
            OUTPUT.mkdir(exist_ok=True)
            (OUTPUT / "fase13_resultados.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            lines = ["# EV11 - Fase 13: pruebas funcionales reales", "", "Inicio UTC: " + report["started_at_utc"], "", report["transport"], "", report["isolation"], "", "JWT omitidos. Cuentas y contrasenas sinteticas de prueba. No se generaron capturas. No se modifico la aplicacion ni las pruebas existentes.", "", "| N | PRUEBA | ENDPOINT | ROL | RESULTADO ESPERADO | RESULTADO REAL | HTTP | PASS/FAIL |", "|---|---|---|---|---|---|---|---|"]
            for case in report["tests"]:
                codes = ", ".join(str(code) for code in sorted({r["http"] for r in case["requests"]}))
                actual = "Comprobaciones verificadas" if case.get("result") == "PASS" else case.get("cause", "Interrumpida")
                lines.append(f"| {case['number']} | {case['test']} | {case['endpoint']} | {case['role']} | {case['expected']} | {actual} | {codes} | {case.get('result', 'FAIL')} |")
            for case in report["tests"]:
                lines += ["", f"## {case['number']}. {case['test']}", "", "Comprobaciones:", "", "```json", json.dumps(case["checks"], ensure_ascii=False, indent=2), "```", "", "Peticiones y respuestas (JWT omitidos):"]
                if case["number"] == 14:
                    selected = [r for r in case["requests"] if r["http"] == 429]
                    lines += ["", "Se muestran las cuatro peticiones bloqueadas. Todas las solicitudes previas y sus respuestas estan en fase13_resultados.json."]
                else:
                    selected = case["requests"]
                for entry in selected:
                    displayed = dict(entry)
                    if entry["request"]["path"] == "/openapi.json":
                        displayed["response"] = "Esquema completo conservado en fase13_resultados.json; comprobaciones arriba."
                    lines += ["", "```json", json.dumps(displayed, ensure_ascii=False, indent=2), "```"]
            (OUTPUT / "fase13_pruebas_funcionales.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(json.dumps(report["summary"]), flush=True)
    return 0 if report["summary"] == {"passed": 15, "failed": 0} else 1


if __name__ == "__main__":
    raise SystemExit(main())
