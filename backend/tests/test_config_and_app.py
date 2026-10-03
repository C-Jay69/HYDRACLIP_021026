"""Tests for settings hardening, app wiring and the package layout.

Several of these lock in Phase 0 fixes: the backend previously could not be
imported at all.
"""

from __future__ import annotations

import importlib

import pytest

from apps.api.core.config import INSECURE_SECRET_KEY, Settings


class TestSettings:
    def test_imports_without_any_environment_configured(self):
        """The old config raised ValueError at import when DATABASE_URL or
        STRIPE_SECRET_KEY were unset."""
        settings = Settings(_env_file=None)
        assert settings.DATABASE_URL
        assert settings.STRIPE_SECRET_KEY == ""

    def test_normalises_the_legacy_postgres_scheme(self):
        settings = Settings(_env_file=None, DATABASE_URL="postgres://u:p@h:5432/db")
        assert settings.DATABASE_URL.startswith("postgresql://")

    def test_rejects_the_placeholder_secret_in_production(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY=INSECURE_SECRET_KEY)

    def test_allows_a_real_secret_in_production(self):
        settings = Settings(
            _env_file=None, ENVIRONMENT="production", SECRET_KEY="a-genuinely-unique-value"
        )
        assert settings.ENVIRONMENT == "production"

    def test_cors_origins_are_deduplicated_and_non_empty(self):
        settings = Settings(
            _env_file=None,
            APP_URL="http://localhost:3000",
            NEXT_PUBLIC_APP_URL="http://localhost:3000",
        )
        assert settings.cors_origins == ["http://localhost:3000"]

    def test_hosted_llm_defaults_to_openrouter_then_nvidia(self):
        settings = Settings(_env_file=None)
        assert settings.LLM_PROVIDER_ORDER == "openrouter,nvidia_nim,ollama"
        assert settings.OPENROUTER_MODEL == "openrouter/auto"
        assert settings.NVIDIA_NIM_BASE_URL == "https://integrate.api.nvidia.com/v1"

    def test_new_and_legacy_supabase_auth_names_are_accepted(self, monkeypatch):
        monkeypatch.setenv("PROJECT_URL", "https://project.supabase.co")
        monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable")
        settings = Settings(_env_file=None)
        assert settings.SUPABASE_URL == "https://project.supabase.co"
        assert settings.SUPABASE_ANON_KEY == "publishable"


class TestPackageLayout:
    @pytest.mark.parametrize(
        "module",
        [
            "apps.api.main",
            "apps.api.core.config",
            "apps.api.core.db",
            "apps.api.core.deps",
            "apps.api.models",
            "apps.api.routers.auth",
            "apps.api.routers.shutterstock",
            "apps.api.schemas",
            "apps.api.services.auth",
            "apps.api.services.rate_limit",
        ],
    )
    def test_module_imports(self, module):
        assert importlib.import_module(module) is not None

    def test_every_model_is_registered_on_the_metadata(self):
        from apps.api.models import Base

        expected = {
            "users",
            "plans",
            "subscriptions",
            "usage_events",
            "projects",
            "videos",
            "video_jobs",
            "schedules",
            "published_posts",
            "social_accounts",
            "platform_tokens",
            "admin_audit_logs",
            "system_settings",
            "prompt_templates",
            "billing_events",
        }
        assert expected <= set(Base.metadata.tables)

    def test_seed_module_imports(self):
        """seed.py imported apps.api.services.auth, which did not exist."""
        assert importlib.import_module("seed") is not None


class TestApp:
    def test_healthz(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_readyz_reports_database_reachability(self, client):
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json()["database"] == "ok"

    def test_openapi_schema_is_generated(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        for path in [
            "/auth/signup",
            "/auth/login",
            "/auth/supabase/login",
            "/auth/google/authorize",
            "/auth/google/callback",
            "/auth/refresh",
            "/auth/me",
            "/healthz",
        ]:
            assert path in paths

    def test_stock_media_routes_are_still_mounted(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert "/shutterstock/images/search" in paths
        assert "/shutterstock/videos/search" in paths


class TestAdminGuard:
    def test_regular_user_is_refused(self, client, auth_headers):
        from apps.api.core.deps import require_admin
        from apps.api.main import app
        from fastapi import Depends

        # Mount a throwaway admin-only route to exercise the dependency.
        @app.get("/_test/admin-only")
        def _admin_only(_=Depends(require_admin)):
            return {"ok": True}

        try:
            headers = auth_headers(email="plain@example.com", role="USER")
            assert client.get("/_test/admin-only", headers=headers).status_code == 403

            admin = auth_headers(email="boss@example.com", role="ADMIN")
            assert client.get("/_test/admin-only", headers=admin).status_code == 200
        finally:
            app.router.routes = [
                r for r in app.router.routes if getattr(r, "path", "") != "/_test/admin-only"
            ]
