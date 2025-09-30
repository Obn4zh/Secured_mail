"""Integration tests for the Flask server endpoints."""

import base64
import importlib
import pathlib
import sys

import pytest

pytest.importorskip("flask", reason="Flask is required for server tests")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Return a Flask test client backed by temporary SQLite databases."""

    monkeypatch.setenv("SECURED_MAIL_MAIN_DB", str(tmp_path / "main.sqlite"))
    monkeypatch.setenv("SECURED_MAIL_CA_DB", str(tmp_path / "ca.sqlite"))

    project_root = pathlib.Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    sys.modules.pop("server", None)
    server = importlib.import_module("server")

    yield server.app.test_client()

    sys.modules.pop("server", None)


def test_add_and_get_user_cert(client):
    email = "alice@example.com"
    cert_payload = base64.b64encode(b"fake cert bytes").decode()

    response = client.post(
        "/add_user_cert",
        json={"email": email, "public_key_cert": cert_payload},
    )
    assert response.status_code == 200

    response = client.get("/get_user_cert", query_string={"email": email})
    assert response.status_code == 200
    assert response.json == {
        "email": email,
        "public_key_cert": cert_payload,
    }


def test_get_user_cert_missing_email(client):
    response = client.get("/get_user_cert")
    assert response.status_code == 400
    assert response.json["error"] == "Email is required"


def test_add_and_fetch_ca_data(client):
    private_key = base64.b64encode(b"private").decode()
    ca_cert = base64.b64encode(b"certificate").decode()

    response = client.post(
        "/add_ca_data",
        json={"private_key": private_key, "ca_cert": ca_cert},
    )
    assert response.status_code == 200

    response = client.get("/get_ca_data")
    assert response.status_code == 200
    assert response.json == {
        "private_key": private_key,
        "ca_cert": ca_cert,
    }


def test_check_user_endpoint(client):
    email = "bob@example.com"
    cert_payload = base64.b64encode(b"cert").decode()

    client.post(
        "/add_user_cert",
        json={"email": email, "public_key_cert": cert_payload},
    )

    response = client.get("/check_user", query_string={"email": email})
    assert response.status_code == 200
    assert response.json == {"exists": True}

    response = client.get(
        "/check_user", query_string={"email": "carol@example.com"}
    )
    assert response.status_code == 200
    assert response.json == {"exists": False}
