"""EV11: 15 escenarios mínimos y regresiones de seguridad/Devices/Loans."""
from datetime import datetime, timedelta, timezone
import logging

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.config import settings
from app.database.connection import Base, get_db
from app.main import app
from app.middlewares.request_middleware import limiter
from app.models.user_model import User

PASSWORD = "CuentaSegura123"
DEVICE = {"name": "Laptop EV11", "serial_number": "EV11-001", "device_type": "laptop", "brand": "Lenovo", "is_available": True}
PROTECTED = [
    ("get", "/users"), ("get", "/users/1"),
    ("post", "/devices"), ("put", "/devices/1"), ("delete", "/devices/1"),
    ("post", "/loans"), ("patch", "/loans/1/return"), ("get", "/loans/details"),
]


@pytest.fixture(scope="session")
def account_hash():
    return get_password_hash(PASSWORD)


@pytest.fixture
def security_db(tmp_path, monkeypatch, account_hash):
    engine = create_engine(f"sqlite:///{tmp_path / 'security.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.main.engine", engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        for role in ("admin", "support", "user"):
            db.add(User(name=f"Cuenta {role}", email=f"{role}@example.com", role=role, hashed_password=account_hash))
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def client(security_db):
    def override_db():
        with security_db() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth():
    return {role: {"Authorization": "Bearer " + create_access_token({"sub": str(i)})}
            for i, role in enumerate(("admin", "support", "user"), 1)}


def register_payload(**updates):
    return {"name": "Samir Acosta", "email": "samir@example.com", "password": PASSWORD, "role": "user"} | updates


def test_01_registration(client, security_db):
    response = client.post("/auth/register", json=register_payload())
    assert response.status_code == 201
    assert response.json()["is_active"] is True
    assert "password" not in response.text
    with security_db() as db:
        user = db.scalar(select(User).where(User.email == "samir@example.com"))
        assert user.hashed_password != PASSWORD
        assert verify_password(PASSWORD, user.hashed_password)


@pytest.mark.parametrize("password", ["Short1", "lowercase123", "UPPERCASE123", "NoNumbersHere", "With Space123", "With\tTab123", "With\nNewline123"])
def test_02_weak_password(client, password):
    response = client.post("/auth/register", json=register_payload(password=password))
    assert response.status_code == 422
    assert "input" not in response.text


def test_03_duplicate_email(client):
    assert client.post("/auth/register", json=register_payload(email="ADMIN@EXAMPLE.COM")).status_code == 400


@pytest.mark.parametrize("as_json", [True, False])
def test_04_login(client, as_json):
    body = {"json": {"email": "admin@example.com", "password": PASSWORD}} if as_json else {
        "data": {"username": "admin@example.com", "password": PASSWORD, "grant_type": "password"}}
    response = client.post("/auth/login", **body)
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    assert decode_access_token(response.json()["access_token"])["sub"] == "1"


@pytest.mark.parametrize("email", ["admin@example.com", "missing@example.com"])
def test_05_incorrect_password(client, email):
    response = client.post("/auth/login", json={"email": email, "password": "Incorrecta123"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_06_me(client):
    token = client.post("/auth/login", data={"username": "user@example.com", "password": PASSWORD}).json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert "password" not in response.text


@pytest.mark.parametrize("method,path", PROTECTED + [("get", "/auth/me")])
def test_07_no_token(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method,path", PROTECTED + [("get", "/auth/me")])
def test_08_invalid_token(client, method, path):
    assert getattr(client, method)(path, headers={"Authorization": "Bearer invalid"}).status_code == 401


@pytest.mark.parametrize("method,path", [("post", "/devices"), ("put", "/devices/999"), ("get", "/loans/details"), ("patch", "/loans/999/return")])
def test_09_wrong_role(client, auth, method, path):
    assert getattr(client, method)(path, headers=auth["user"]).status_code == 403


@pytest.mark.parametrize("role", ["admin", "support"])
def test_10_create_device_allowed(client, auth, role):
    response = client.post("/devices", json=DEVICE, headers=auth[role])
    assert response.status_code == 201
    assert response.json()["serial_number"] == DEVICE["serial_number"]


@pytest.mark.parametrize("role", ["support", "user"])
def test_11_delete_forbidden(client, auth, role):
    created = client.post("/devices", json=DEVICE, headers=auth["admin"]).json()
    assert client.delete(f"/devices/{created['id']}", headers=auth[role]).status_code == 403
    assert client.get(f"/devices/{created['id']}").status_code == 200


@pytest.mark.parametrize("origin,allowed", [("http://localhost:5173", True), ("http://localhost:3000", True), ("https://untrusted.example", False)])
def test_12_cors(client, origin, allowed):
    response = client.options("/users", headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"})
    assert response.status_code == (200 if allowed else 400)
    assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
    if allowed:
        assert response.headers["access-control-allow-credentials"] == "true"
        denied = client.get("/users", headers={"Origin": origin})
        assert denied.status_code == 401
        assert denied.headers["access-control-allow-origin"] == origin


def test_13_headers_and_logging(client, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error.requests"):
        response = client.get("/users", headers={"X-Request-ID": "ev11-request"})
    assert response.headers["X-Request-ID"] == "ev11-request"
    assert response.headers["X-App-Name"] == "device_systems"
    assert response.headers["X-API-Version"] == "3.0.0"
    assert float(response.headers["X-Process-Time"]) >= 0
    assert "method=GET" in caplog.text and "path='/users'" in caplog.text and "status=401" in caplog.text
    first = client.get("/").headers["X-Request-ID"]
    assert first and first != client.get("/").headers["X-Request-ID"]


@pytest.mark.parametrize("endpoint,limit", [("/auth/login", 5), ("/auth/register", 3), ("/users", 30), ("/loans", 10)])
def test_14_rate_limits(client, auth, endpoint, limit):
    def request(index):
        if endpoint == "/auth/login":
            return client.post(endpoint, json={"email": "user@example.com", "password": "Incorrecta123"})
        if endpoint == "/auth/register":
            return client.post(endpoint, json=register_payload(email=f"person{index}@example.com"))
        if endpoint == "/users":
            return client.get(endpoint, headers=auth["user"])
        return client.post(endpoint, json={"user_id": 3, "device_id": 999, "status": "active"}, headers=auth["user"])
    for index in range(limit):
        assert request(index).status_code != 429
    response = request(limit)
    assert response.status_code == 429
    assert response.headers["X-App-Name"] == "device_systems"


def test_15_swagger_openapi(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "device_systems API"
    assert schema["info"]["version"] == "3.0.0"
    assert schema["info"]["description"] == "API REST segura para gestión de usuarios, dispositivos y préstamos"
    assert {t["name"] for t in schema["tags"]} == {"Auth", "Users", "Devices", "Loans", "Security"}
    oauth = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert oauth["type"] == "oauth2"
    assert oauth["flows"]["password"]["tokenUrl"] == "auth/login"
    for method, path in PROTECTED:
        path = path.replace("/users/1", "/users/{user_id}").replace("/devices/1", "/devices/{device_id}").replace("/loans/1/return", "/loans/{loan_id}/return")
        assert schema["paths"][path][method]["security"] == [{"OAuth2PasswordBearer": []}]
    assert "hashed_password" not in str(schema)


@pytest.mark.parametrize("update", [{"name": "  "}, {"name": " ab "}, {"email": "invalid"}, {"role": "owner"}])
def test_registration_validation(client, update):
    response = client.post("/auth/register", json=register_payload(**update))
    assert response.status_code == 422
    assert PASSWORD not in response.text


@pytest.mark.parametrize("role", ["admin", "support", "user"])
def test_registration_allowed_roles(client, role):
    assert client.post("/auth/register", json=register_payload(role=role)).json()["role"] == role


@pytest.mark.parametrize("kind", ["expired", "wrong_signature", "wrong_algorithm", "missing_exp", "missing_sub", "malformed_sub", "oversized_sub", "missing_user"])
def test_jwt_rejection(client, kind):
    now = datetime.now(timezone.utc)
    claims = {"sub": "1", "iat": now, "exp": now + timedelta(minutes=30)}
    key, algorithm = settings.SECRET_KEY, settings.ALGORITHM
    if kind == "expired":
        claims.update(iat=now - timedelta(hours=2), exp=now - timedelta(hours=1))
    elif kind == "wrong_signature":
        key = "another-signing-key-for-tests-only"
    elif kind == "wrong_algorithm":
        algorithm = "HS512"
    elif kind == "missing_exp":
        claims.pop("exp")
    elif kind == "missing_sub":
        claims.pop("sub")
    elif kind == "malformed_sub":
        claims["sub"] = "abc"
    elif kind == "oversized_sub":
        claims["sub"] = "9999999999999999999"
    else:
        claims["sub"] = "99999"
    token = jwt.encode(claims, key, algorithm=algorithm)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_inactive_user_and_live_role(client, auth, security_db):
    with security_db() as db:
        db.get(User, 1).role = "user"
        db.get(User, 2).is_active = False
        db.commit()
    assert client.post("/devices", json=DEVICE, headers=auth["admin"]).status_code == 403
    assert client.get("/auth/me", headers=auth["support"]).status_code == 403
    assert client.post("/auth/login", json={"email": "support@example.com", "password": PASSWORD}).status_code == 403


def test_legacy_account_hash_and_private_responses(client, auth, security_db):
    response = client.post("/users", json={"name": "Legacy User", "email": "legacy@example.com", "role": "user"})
    assert response.status_code == 201
    user_id = response.json()["id"]
    with security_db() as db:
        hashed = db.get(User, user_id).hashed_password
        assert hashed.startswith("$bcrypt-sha256$")
        assert not verify_password(PASSWORD, hashed)
        for password in ("", "password", "12345678"):
            assert not verify_password(password, hashed)
    for path in ("/users", f"/users/{user_id}", "/auth/me", "/loans/details"):
        result = client.get(path, headers=auth["admin"])
        assert result.status_code == 200
        assert "password" not in result.text and hashed not in result.text


def test_hashed_password_required(security_db):
    with security_db() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("INSERT INTO users (name,email,role) VALUES ('Persona','nohash@example.com','user')"))
            db.commit()


def test_long_unicode_password_not_truncated():
    password = "Ab1" + "ñ" * 100
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
    assert not verify_password(password + "x", hashed)


def test_devices_loans_joins_filters_and_return(client, auth):
    admin, support, user = auth["admin"], auth["support"], auth["user"]
    device = client.post("/devices", json=DEVICE, headers=support).json()
    device_id = device["id"]
    path = f"/devices/{device_id}"
    assert client.put(path, json=DEVICE | {"name": "Equipo actualizado"}, headers=support).status_code == 200
    assert client.patch(path, json={"brand": "Dell"}).json()["brand"] == "Dell"
    assert len(client.get("/devices?device_type=laptop&brand=Dell&search=actualizado&is_available=true").json()) == 1
    loan = client.post("/loans", json={"user_id": 3, "device_id": device_id, "status": "returned"}, headers=user)
    assert loan.status_code == 201
    loan_id = loan.json()["id"]
    assert loan.json()["status"] == "active"
    assert client.get(path).json()["is_available"] is False
    assert client.post("/loans", json={"user_id": 3, "device_id": device_id, "status": "active"}, headers=user).status_code == 409
    result = client.get("/loans?status=active&user_email=user%40example.com&device_type=laptop")
    assert [item["id"] for item in result.json()] == [loan_id]
    details = client.get("/loans/details", headers=support).json()
    assert details[0]["user"]["email"] == "user@example.com"
    assert details[0]["device"]["id"] == device_id
    assert "password" not in str(details)
    assert client.get("/users/3/loans").json()[0]["id"] == loan_id
    assert client.get(path + "/loans").json()[0]["id"] == loan_id
    assert client.get(f"/loans/{loan_id}").status_code == 200
    returned = client.patch(f"/loans/{loan_id}/return", headers=support)
    assert returned.json()["status"] == "returned" and returned.json()["return_date"]
    assert client.get(path).json()["is_available"] is True
    assert client.patch(f"/loans/{loan_id}/return", headers=admin).status_code == 409
    unused = client.post("/devices", json=DEVICE | {"serial_number": "delete-test"}, headers=admin).json()
    assert client.delete(f"/devices/{unused['id']}", headers=admin).status_code == 204
    assert client.get(f"/devices/{unused['id']}").status_code == 404
