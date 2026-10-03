"""Regression tests for deployment-critical Docker Compose wiring.

The application settings can be correct while Compose silently replaces them
with container-local defaults. These checks keep the external Supabase database,
S3 credentials, encryption key and OAuth values flowing from ``.env`` into the
API/worker containers.
"""

from pathlib import Path

import yaml


COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def _environment(service: str) -> dict[str, str]:
    values = _compose()["services"][service]["environment"]
    return dict(item.split("=", 1) for item in values)


def test_service_dependency_graph_has_no_cycles():
    services = _compose()["services"]
    graph = {
        name: set((definition.get("depends_on") or {}).keys())
        for name, definition in services.items()
    }

    def visit(name: str, path: tuple[str, ...] = ()) -> None:
        assert name not in path, " -> ".join((*path, name))
        for dependency in graph[name]:
            visit(dependency, (*path, name))

    for service in graph:
        visit(service)


def test_api_honours_external_database_url():
    database_url = _environment("api")["DATABASE_URL"]

    assert database_url.startswith("${DATABASE_URL:-")
    assert "postgres:5432/hydraclip" in database_url


def test_hosted_services_do_not_force_obsolete_local_infrastructure():
    services = _compose()["services"]

    # MinIO stopped publishing official container images. Supabase/S3 users
    # must not be blocked by Compose trying to pull a dead local dependency.
    assert "minio" not in services
    assert "minio-init" not in services
    assert services["postgres"]["profiles"] == ["local-db"]

    for service in ("api", "worker", "beat"):
        dependencies = services[service].get("depends_on") or {}
        assert "postgres" not in dependencies
        assert "minio" not in dependencies
        assert "minio-init" not in dependencies


def test_optional_monitoring_cannot_block_core_startup():
    flower = _compose()["services"]["flower"]

    assert flower["profiles"] == ["monitoring"]
    assert flower["image"] == "mher/flower:2.2.0"
    assert flower["image"] != "celery/flower:latest"


def test_beat_does_not_inherit_the_api_http_healthcheck():
    # Beat has no HTTP server. Inheriting the Dockerfile's /healthz probe makes
    # a functioning scheduler transition from "starting" to "unhealthy".
    assert _compose()["services"]["beat"]["healthcheck"] == {"disable": True}


def test_hosted_llm_is_default_and_ollama_is_opt_in():
    services = _compose()["services"]
    environment = _environment("api")

    assert services["ollama"]["profiles"] == ["local-llm"]
    assert environment["LLM_PROVIDER_ORDER"].startswith(
        "${LLM_PROVIDER_ORDER:-openrouter,nvidia_nim,ollama}"
    )
    assert environment["OPENROUTER_API_KEY"] == "${OPENROUTER_API_KEY:-}"
    assert "NVIDIA_API_KEY" in environment["NVIDIA_NIM_API_KEY"]


def test_login_provider_settings_are_forwarded():
    environment = _environment("api")

    assert "PROJECT_URL" in environment["SUPABASE_URL"]
    assert "SUPABASE_PUBLISHABLE_KEY" in environment["SUPABASE_ANON_KEY"]
    assert environment["GOOGLE_LOGIN_REDIRECT_URI"].startswith(
        "${GOOGLE_LOGIN_REDIRECT_URI:-"
    )


def test_optional_stock_keys_do_not_emit_compose_warnings():
    environment = _environment("api")

    for name in (
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
        "UNSPLASH_ACCESS_KEY",
        "SHUTTERSTOCK_API_TOKEN",
    ):
        assert environment[name] == f"${{{name}:-}}"


def test_api_honours_s3_and_supabase_storage_names():
    environment = _environment("api")

    assert environment["MINIO_ENDPOINT"].startswith("${S3_ENDPOINT:-${MINIO_ENDPOINT:-")
    assert environment["MINIO_ACCESS_KEY"].startswith("${S3_ACCESS_KEY:-${MINIO_ACCESS_KEY:-")
    assert environment["MINIO_SECRET_KEY"].startswith("${S3_SECRET_KEY:-${MINIO_SECRET_KEY:-")
    assert "SUPABASE_STORAGE_BUCKET" in environment["MINIO_BUCKET"]


def test_encryption_and_oauth_secrets_are_forwarded():
    environment = _environment("api")
    expected = {
        "TOKEN_ENCRYPTION_KEY",
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REDIRECT_URI",
        "INSTAGRAM_CLIENT_ID",
        "INSTAGRAM_CLIENT_SECRET",
        "INSTAGRAM_REDIRECT_URI",
        "TIKTOK_CLIENT_ID",
        "TIKTOK_CLIENT_SECRET",
        "TIKTOK_REDIRECT_URI",
        "X_CLIENT_ID",
        "X_CLIENT_SECRET",
        "X_REDIRECT_URI",
    }

    assert expected <= environment.keys()
