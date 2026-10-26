"""Tests for the health endpoint and basic app wiring."""

from __future__ import annotations


class TestHealthEndpoint:
    """GET /health must return status and version."""

    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_body_contains_status_ok(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_body_contains_version(self, client):
        body = client.get("/health").json()
        assert "version" in body
        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    def test_version_matches_settings(self, client):
        """The version in the response must come from settings."""
        body = client.get("/health").json()
        # Default version in Settings is "1.0.0"
        assert body["version"] == "1.0.0"


class TestCORSHeaders:
    """CORS middleware must be active and honour CORS_ORIGINS."""

    def test_cors_allows_configured_origin(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Test settings set CORS_ORIGINS="*", so any origin is allowed.
        assert resp.status_code == 200

    def test_cors_header_present_on_get(self, client):
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert "access-control-allow-origin" in resp.headers


class TestAppFactory:
    """Verify the app is assembled correctly."""

    def test_openapi_title(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["title"] == "REDELIVER"

    def test_unknown_route_returns_404(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
