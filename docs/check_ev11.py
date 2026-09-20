"""Verificación HTTP y visual real, con SQLite temporal; no genera capturas.

Requiere Playwright opcional y Microsoft Edge. Ejecutar desde la raíz:
    python docs/check_ev11.py
"""
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import threading
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="device_systems_ev11_") as temporary:
        os.environ["DATABASE_URL"] = "sqlite:///" + (Path(temporary) / "manual.db").as_posix()
        os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
        os.environ["ALGORITHM"] = "HS256"
        from alembic import command
        from alembic.config import Config
        import uvicorn
        from app.database.connection import engine
        from app.main import app

        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        results = {}
        with socket.socket() as bound:
            bound.bind(("127.0.0.1", 0))
            port = bound.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        password = "ManualSegura123"

        def check_response(response, expected):
            assert response.status_code == expected, (response.status_code, expected)
            assert "hashed_password" not in response.text
            assert password not in response.text
            return response

        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started, "Uvicorn no inició"
            with httpx.Client(base_url=base, timeout=15) as client:
                check_response(client.get("/docs"), 200)
                results["docs_http"] = 200
                tokens = {}
                for role in ("admin", "support", "user"):
                    registration = check_response(client.post("/auth/register", json={
                        "name": f"Manual {role}", "email": f"{role}@example.com", "password": password, "role": role}), 201)
                    assert registration.json()["role"] == role
                    login = check_response(client.post("/auth/login", data={
                        "username": f"{role}@example.com", "password": password}), 200)
                    token = login.json()["access_token"]
                    assert len(token.split(".")) == 3
                    tokens[role] = {"Authorization": "Bearer " + token}
                results["register_roles"] = ["admin", "support", "user"]
                results["login_jwt"] = True
                assert check_response(client.get("/auth/me", headers=tokens["user"]), 200).json()["role"] == "user"
                results["me"] = 200
                check_response(client.get("/users"), 401)
                results["no_token"] = 401
                check_response(client.get("/loans/details", headers=tokens["user"]), 403)
                results["wrong_role"] = 403
                results["middleware"] = all(name in client.get("/").headers for name in (
                    "x-process-time", "x-app-name", "x-request-id", "x-api-version"))
                from playwright.sync_api import sync_playwright
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(channel="msedge", headless=True)
                    try:
                        page = browser.new_page()
                        page.goto(base + "/docs", wait_until="networkidle", timeout=60000)
                        page.locator("#operations-tag-Auth").wait_for(timeout=30000)
                        results["swagger_auth_visible"] = True
                        page.locator(".auth-wrapper button.authorize").click()
                        dialog = page.locator(".dialog-ux")
                        assert "OAuth2" in dialog.inner_text()
                        results["swagger_oauth2_visible"] = True
                        dialog.locator("#oauth_username").fill("user@example.com")
                        dialog.locator("#oauth_password").fill(password)
                        dialog.locator("button.authorize").click()
                        dialog.get_by_text("Logout", exact=True).wait_for()
                        results["swagger_authorize_login"] = True
                        dialog.locator("button.btn-done").click()
                        operation = page.locator("#operations-Auth-me_auth_me_get")
                        operation.locator(".opblock-summary").click()
                        operation.get_by_role("button", name="Try it out", exact=True).click()
                        with page.expect_response(lambda r: r.url == base + "/auth/me") as response_info:
                            operation.get_by_role("button", name="Execute", exact=True).click()
                        response = response_info.value
                        assert response.status == 200
                        assert "hashed_password" not in response.text()
                        assert response.json()["role"] == "user"
                        results["swagger_me_authorized"] = 200
                    finally:
                        browser.close()
                # Ya hubo cuatro logins: tres por HTTP y uno desde Swagger.
                check_response(client.post("/auth/login", data={"username": "user@example.com", "password": "Incorrecta123"}), 401)
                limited = check_response(client.post("/auth/login", data={"username": "user@example.com", "password": "Incorrecta123"}), 429)
                results["rate_limit"] = limited.status_code
                results["no_credentials_in_responses"] = True
                print(json.dumps(results, indent=2, ensure_ascii=False))
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            engine.dispose()


if __name__ == "__main__":
    main()
