import json
import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


def test_manifest_endpoint(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert "application/manifest+json" in response["Content-Type"]
    manifest = json.loads(response.content.decode("utf-8"))
    assert manifest["name"] == "Gustul Cărților"
    assert manifest["start_url"] == "/copil/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert len(manifest["icons"]) >= 2


def test_service_worker_endpoint(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "application/javascript" in response["Content-Type"]
    assert response.get("Service-Worker-Allowed") == "/"
    assert "no-cache" in response.get("Cache-Control", "")
    content = response.content.decode("utf-8")
    assert "gustul-cartilor-static" in content
    # Ensure offline route is precached
    assert "/offline/" in content


def test_offline_view_no_private_data(client):
    response = client.get("/offline/")
    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]
    content = response.content.decode("utf-8")
    assert "Nu am internet acum" in content
    # Verify no private data leaked in offline view
    for forbidden in ["email", "csrfmiddlewaretoken", "guardian", "child_id", "password"]:
        assert forbidden not in content.lower()

