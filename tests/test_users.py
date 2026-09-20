from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.database.connection import Base, get_db
from app.models.user_model import User
from app.services.user_service import find_user_by_email
from app.dependencies.user_dependencies import get_user_or_404
from app.main import app
from app.auth.security import create_access_token, get_password_hash


@pytest.fixture(scope="session")
def legacy_hash():
    return get_password_hash("FixtureSegura123")


@pytest.fixture
def database(tmp_path, legacy_hash, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.main.engine", engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([
            User(name="Administrador", email="admin@devicesystems.com", role="admin", hashed_password=legacy_hash),
            User(name="Soporte", email="support@devicesystems.com", role="support", hashed_password=legacy_hash),
            User(name="Usuario", email="user@devicesystems.com", role="user", is_active=False, hashed_password=legacy_hash),
        ])
        db.commit()
    yield engine, factory
    engine.dispose()


@pytest.fixture
def client(database):
    _, factory = database
    def override_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            test_client.headers["Authorization"] = "Bearer " + create_access_token({"sub": "2"})
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def payload():
    return {"name": "Samir Acosta", "email": "samir@example.com",
            "role": "user", "is_active": True}


def test_list_and_existing_user(client):
    response = client.get("/users")
    assert response.status_code == 200
    assert len(response.json()) == 3
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.json()["email"] == "admin@devicesystems.com"


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_missing_user(client, payload, method):
    kwargs = {"json": payload} if method in {"put", "patch"} else {}
    response = getattr(client, method)("/users/99999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Usuario no encontrado"}


@pytest.mark.parametrize("query,expected", [
    ("role=admin", [1]), ("role=support", [2]), ("role=user", [3]),
    ("is_active=true", [1, 2]), ("is_active=false", [3]),
    ("role=admin&is_active=true", [1]), ("role=admin&is_active=false", []),
])
def test_filters(client, query, expected):
    response = client.get(f"/users?{query}")
    assert response.status_code == 200
    assert [user["id"] for user in response.json()] == expected


def test_create_and_default_active(client, payload):
    payload.pop("is_active")
    response = client.post("/users", json=payload)
    assert response.status_code == 201
    assert response.json() == {**payload, "id": 4, "is_active": True, "created_at": response.json()["created_at"]}
    datetime.fromisoformat(response.json()["created_at"])
    assert client.get("/users/4").json() == response.json()


@pytest.mark.parametrize("method,path", [("post", "/users"), ("put", "/users/1"), ("patch", "/users/1")])
def test_duplicate_email(client, payload, method, path):
    payload["email"] = "SUPPORT@DEVICESYSTEMS.COM"
    response = getattr(client, method)(path, json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": "El correo electrónico ya está registrado"}
    assert client.get("/users/1").json()["role"] == "admin"


@pytest.mark.parametrize("method,path", [("post", "/users"), ("put", "/users/1"), ("patch", "/users/1")])
def test_invalid_role(client, payload, method, path):
    payload["role"] = "technician"
    response = getattr(client, method)(path, json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("method,path", [("post", "/users"), ("put", "/users/1"), ("patch", "/users/1")])
@pytest.mark.parametrize("field,value", [
    ("email", "correo-invalido"), ("name", "  "), ("name", " ab "),
    ("is_active", "quizas"), ("id", 99), ("unknown", "extra"),
])
def test_invalid_data(client, payload, method, path, field, value):
    payload[field] = value
    assert getattr(client, method)(path, json=payload).status_code == 422


@pytest.mark.parametrize("field", ["name", "email", "role", "is_active"])
def test_put_requires_every_field(client, payload, field):
    payload.pop(field)
    assert client.put("/users/1", json=payload).status_code == 422


def test_put_replaces_all_fields_and_allows_own_email(client):
    payload = {"name": "Administrador Nuevo", "email": "ADMIN@DEVICESYSTEMS.COM",
               "role": "user", "is_active": False}
    response = client.put("/users/1", json=payload)
    assert response.status_code == 200
    assert response.json() == {**payload, "email": "ADMIN@devicesystems.com", "id": 1, "created_at": response.json()["created_at"]}
    assert client.get("/users/1").json() == response.json()


def test_patch_only_changes_sent_fields(client):
    before = client.get("/users/1").json()
    response = client.patch("/users/1", json={"role": "support"})
    assert response.status_code == 200
    assert response.json() == {**before, "role": "support"}
    response = client.patch("/users/1", json={"is_active": False})
    assert response.json() == {**before, "role": "support", "is_active": False}


def test_patch_empty(client):
    response = client.patch("/users/1", json={})
    assert response.status_code == 400
    assert response.json() == {"detail": "Debe enviar al menos un campo para actualizar"}


@pytest.mark.parametrize("field", ["name", "email", "role", "is_active"])
def test_patch_explicit_null(client, field):
    assert client.patch("/users/1", json={field: None}).status_code == 422


def test_delete_and_id_not_reused(client, payload):
    created = client.post("/users", json=payload).json()
    response = client.delete(f"/users/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/users/{created['id']}").status_code == 404
    assert client.post("/users", json=payload).json()["id"] > created["id"]


def test_dependency_is_used(client):
    app.dependency_overrides[get_user_or_404] = lambda: {
        "id": 77, "name": "Usuario Inyectado", "email": "test@example.com",
        "role": "user", "is_active": True, "created_at": datetime(2026, 1, 1),
    }
    assert client.get("/users/99999").json()["id"] == 77


@pytest.mark.parametrize("path,code", [("/", 200), ("/users", 200), ("/users/99999", 404),
                                         ("/users?is_active=quizas", 422), ("/users?role=invalid", 422)])
def test_headers(client, path, code):
    response = client.get(path)
    assert response.status_code == code
    assert response.headers["X-App-Name"] == settings.APP_NAME
    assert response.headers["X-API-Version"] == settings.APP_VERSION


def test_root_and_documentation(client):
    assert client.get("/").json() == {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200
    schema = client.get("/openapi.json").json()
    expected = {"/users": {"get": "200", "post": "201"},
                "/users/{user_id}": {"get": "200", "put": "200", "patch": "200", "delete": "204"}}
    for path, methods in expected.items():
        assert set(schema["paths"][path]) == set(methods)
        for method, code in methods.items():
            operation = schema["paths"][path][method]
            assert operation["tags"] == ["Users"]
            assert operation["summary"] and operation["description"]
            assert operation["responses"][code]["description"]
    assert "content" not in schema["paths"]["/users/{user_id}"]["delete"]["responses"]["204"]


def test_concurrent_duplicate_creation(client, payload):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post("/users", json=payload), range(4)))
    assert sorted(response.status_code for response in responses) == [201, 400, 400, 400]


def test_concurrent_ids_are_unique(client, payload):
    def create(index):
        return client.post("/users", json={**payload, "email": f"person{index}@example.com"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(create, range(8)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 8


@pytest.mark.parametrize("sort_by", ["name", "created_at"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_ordering(client, sort_by, order):
    users = client.get(f"/users?sort_by={sort_by}&order={order}").json()
    values = [user[sort_by] for user in users]
    assert values == sorted(values, reverse=order == "desc")


@pytest.mark.parametrize("query", ["sort_by=email", "order=invalid"])
def test_invalid_sort(client, query):
    assert client.get(f"/users?{query}").status_code == 422


def test_persistence_after_reconnecting(client, database, payload):
    engine, _ = database
    created = client.post("/users", json=payload).json()
    engine.dispose()
    reopened = create_engine(engine.url)
    try:
        with sessionmaker(bind=reopened)() as db:
            stored = find_user_by_email(db, payload["email"].upper())
            assert stored.id == created["id"]
            assert stored.name == payload["name"]
    finally:
        reopened.dispose()


@pytest.mark.parametrize("values", [
    {"name": None}, {"name": "ab"}, {"role": "invalid"}, {"email": None},
    {"email": "ADMIN@DEVICESYSTEMS.COM"}, {"is_active": None},
])
def test_database_constraints(database, values, legacy_hash):
    _, factory = database
    with factory() as db:
        user = User(**({"name": "Persona", "email": "new@example.com", "role": "user"} | values))
        # INSERT directo permite comprobar NULL sin aplicar defaults del ORM.
        fields = {"name": user.name, "email": user.email, "role": user.role, "is_active": values.get("is_active", True)}
        fields["hashed_password"] = legacy_hash
        with pytest.raises(IntegrityError):
            db.execute(text("INSERT INTO users (name, email, role, is_active, hashed_password) VALUES (:name, :email, :role, :is_active, :hashed_password)"), fields)
            db.commit()
        db.rollback()
        assert find_user_by_email(db, "admin@devicesystems.com") is not None
