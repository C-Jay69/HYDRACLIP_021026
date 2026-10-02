"""Generation endpoints and the job state machine.

The pipeline itself is stubbed here — these tests are about the job lifecycle,
quota reservation, ownership and failure reporting, not about Ollama.
"""

from __future__ import annotations

import asyncio

import pytest

from apps.api.models import Project, Video, VideoJob
from apps.api.services import jobs as job_service
from apps.api.services import quota as quota_service
from apps.api.services.ai_pipeline import PipelineError, StageNotImplemented


# --- Doubles ---------------------------------------------------------------------


class FakeLLM:
    def __init__(self) -> None:
        self.reason: str | None = None

    async def unavailable_reason(self) -> str | None:
        return self.reason


class FakePipeline:
    """Stands in for AIPipeline; records calls and can be told to fail."""

    def __init__(self) -> None:
        self.llm = FakeLLM()
        self.script_calls: list[dict] = []
        self.tts_calls: list[tuple[str, str]] = []
        self.script_error: Exception | None = None
        self.tts_error: Exception | None = None
        self.on_script = None  # optional hook, called before the script stage

    async def generate_script(self, topic, style="short_form", duration=60):
        self.script_calls.append({"topic": topic, "style": style, "duration": duration})
        if self.on_script is not None:
            self.on_script()
        if self.script_error:
            raise self.script_error
        return {"script": f"A script about {topic}.", "topic": topic}

    async def text_to_speech(self, text, voice="lessac"):
        self.tts_calls.append((text, voice))
        if self.tts_error:
            raise self.tts_error
        return "/tmp/videoforce/tts_fake.wav"

    async def create_video_from_script(self, script, **kwargs):
        raise StageNotImplemented("video assembly is not implemented")


@pytest.fixture
def pipeline(monkeypatch):
    """Swap the real pipeline out, and make every stage look available."""
    fake = FakePipeline()
    monkeypatch.setattr(job_service, "get_ai_pipeline", lambda: fake)
    monkeypatch.setattr(
        job_service.PiperTTS, "unavailable_reason", classmethod(lambda cls, voice="lessac": None)
    )
    return fake


@pytest.fixture
def inline_runner(pipeline):
    """Run jobs synchronously inside the request, for deterministic tests."""

    async def run(job_id: int) -> None:
        await job_service.run_generation_job(job_id, pipeline=pipeline)

    previous = job_service.set_runner(run)
    yield
    job_service.set_runner(previous)


@pytest.fixture
def deferred_runner(pipeline):
    """Accept jobs without executing them, so 'pending' can be observed."""
    captured: list[int] = []

    async def run(job_id: int) -> None:
        captured.append(job_id)

    previous = job_service.set_runner(run)
    yield captured
    job_service.set_runner(previous)


def _project(client, headers, title="Coffee explainer", topic="Light roast"):
    response = client.post(
        "/projects", json={"title": title, "topic": topic}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- Accepting a job ---------------------------------------------------------------


def test_generate_returns_202_with_a_job_to_poll(client, auth_headers, deferred_runner):
    headers = auth_headers()
    project_id = _project(client, headers)

    response = client.post(f"/projects/{project_id}/generate", json={}, headers=headers)
    assert response.status_code == 202, response.text

    body = response.json()
    assert body["job"]["status"] == "pending"
    assert body["job"]["job_type"] == "generate"
    assert body["job"]["progress_pct"] == 0
    assert body["video"]["status"] == "pending"
    assert body["stages"] == ["script"]
    assert body["poll_url"] == f"/jobs/{body['job']['id']}"
    assert deferred_runner == [body["job"]["id"]]


def test_generate_requires_authentication(client):
    assert client.post("/projects/1/generate", json={}).status_code == 401


def test_generate_on_another_users_project_returns_404(
    client, auth_headers, make_user, db, deferred_runner
):
    victim = make_user(email="victim@example.com")
    project = Project(user_id=victim.id, title="Private", topic="x", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    headers = auth_headers(email="attacker@example.com")
    response = client.post(f"/projects/{project.id}/generate", json={}, headers=headers)

    assert response.status_code == 404
    assert db.query(Video).count() == 0


def test_topic_comes_from_the_project_not_the_request(
    client, auth_headers, db, deferred_runner
):
    headers = auth_headers()
    project_id = _project(client, headers, topic="Light roast")

    client.post(
        f"/projects/{project_id}/generate",
        json={"topic": "something else entirely"},
        headers=headers,
    )

    video = db.query(Video).one()
    assert video.generation_params_json["topic"] == "Light roast"


def test_project_title_is_used_when_there_is_no_topic(
    client, auth_headers, db, deferred_runner
):
    headers = auth_headers()
    response = client.post("/projects", json={"title": "Just a title"}, headers=headers)
    project_id = response.json()["id"]

    client.post(f"/projects/{project_id}/generate", json={}, headers=headers)
    assert db.query(Video).one().generation_params_json["topic"] == "Just a title"


def test_generation_params_are_recorded(client, auth_headers, db, deferred_runner):
    headers = auth_headers()
    project_id = _project(client, headers)

    client.post(
        f"/projects/{project_id}/generate",
        json={"style": "long_form", "duration": 90, "voice": "isley"},
        headers=headers,
    )

    params = db.query(Video).one().generation_params_json
    assert params["style"] == "long_form"
    assert params["duration"] == 90
    assert params["voice"] == "isley"


@pytest.mark.parametrize(
    "payload",
    [
        {"duration": 2},
        {"duration": 10_000},
        {"style": "haiku"},
        {"stages": ["script", "nonsense"]},
    ],
)
def test_invalid_generation_options_are_rejected(
    client, auth_headers, deferred_runner, payload
):
    headers = auth_headers()
    project_id = _project(client, headers)
    response = client.post(
        f"/projects/{project_id}/generate", json=payload, headers=headers
    )
    assert response.status_code == 422


def test_stages_are_reordered_into_pipeline_order(
    client, auth_headers, db, deferred_runner
):
    headers = auth_headers()
    project_id = _project(client, headers)

    client.post(
        f"/projects/{project_id}/generate",
        json={"stages": ["voiceover", "script"]},
        headers=headers,
    )
    assert db.query(Video).one().generation_params_json["stages"] == ["script", "voiceover"]


# --- Guards -------------------------------------------------------------------------


def test_second_concurrent_generation_is_rejected(client, auth_headers, deferred_runner):
    """A double-clicked button must not create two videos."""
    headers = auth_headers()
    project_id = _project(client, headers)

    first = client.post(f"/projects/{project_id}/generate", json={}, headers=headers)
    second = client.post(f"/projects/{project_id}/generate", json={}, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 409
    assert "already pending" in second.json()["detail"]


def test_a_new_job_is_allowed_once_the_previous_one_finished(
    client, auth_headers, inline_runner
):
    headers = auth_headers()
    project_id = _project(client, headers)

    assert client.post(f"/projects/{project_id}/generate", json={}, headers=headers).status_code == 202
    assert client.post(f"/projects/{project_id}/generate", json={}, headers=headers).status_code == 202


def test_unavailable_stage_is_rejected_with_503_before_queueing(
    client, auth_headers, db, pipeline, deferred_runner
):
    """Queueing work that cannot possibly finish is worse than refusing it."""
    pipeline.llm.reason = "Ollama is unreachable at http://localhost:11434"
    headers = auth_headers()
    project_id = _project(client, headers)

    response = client.post(f"/projects/{project_id}/generate", json={}, headers=headers)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "script" in detail["unavailable_stages"]
    assert "unreachable" in detail["unavailable_stages"]["script"]
    # Nothing was created.
    assert db.query(Video).count() == 0
    assert db.query(VideoJob).count() == 0


def test_assemble_stage_is_rejected_when_no_provider_is_configured(
    client, auth_headers, deferred_runner
):
    """Preflight refuses up front rather than failing the job later."""
    headers = auth_headers()
    project_id = _project(client, headers)

    response = client.post(
        f"/projects/{project_id}/generate",
        json={"stages": ["script", "assemble"]},
        headers=headers,
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "assemble" in detail["unavailable_stages"]
    assert "PEXELS_API_KEY" in detail["unavailable_stages"]["assemble"]


def test_quota_exhaustion_blocks_generation_with_402(
    client, auth_headers, db, deferred_runner
):
    headers = auth_headers(email="me@example.com")
    user_id = client.get("/auth/me", headers=headers).json()["id"]

    for _ in range(quota_service.FALLBACK_VIDEO_LIMIT):
        quota_service.record_video_generated(db, user_id)
    db.commit()

    project_id = _project(client, headers)
    response = client.post(f"/projects/{project_id}/generate", json={}, headers=headers)

    assert response.status_code == 402
    assert "Upgrade to continue" in response.json()["detail"]
    assert db.query(VideoJob).count() == 0


def test_in_flight_jobs_hold_a_quota_slot(client, auth_headers, db, deferred_runner):
    """Without this, N concurrent requests all see the same free slot."""
    headers = auth_headers()

    # Free plan allows 3. Start 3 jobs across 3 projects; none complete.
    for i in range(quota_service.FALLBACK_VIDEO_LIMIT):
        project_id = _project(client, headers, title=f"P{i}")
        assert client.post(
            f"/projects/{project_id}/generate", json={}, headers=headers
        ).status_code == 202

    quota = client.get("/videos/quota", headers=headers).json()
    assert quota["used"] == 0          # nothing finished
    assert quota["in_flight"] == 3     # but three slots are reserved
    assert quota["remaining"] == 0

    fourth = _project(client, headers, title="P4")
    response = client.post(f"/projects/{fourth}/generate", json={}, headers=headers)
    assert response.status_code == 402
    assert "3 generating" in response.json()["detail"]


# --- Execution --------------------------------------------------------------------------


def test_successful_job_completes_and_stores_the_script(
    client, auth_headers, db, inline_runner, pipeline
):
    headers = auth_headers()
    project_id = _project(client, headers, topic="Light roast")

    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()

    job = client.get(body["poll_url"], headers=headers).json()
    assert job["status"] == "completed"
    assert job["progress_pct"] == 100
    assert job["started_at"] is not None
    assert job["completed_at"] is not None
    assert job["error_message"] is None

    video = client.get(f"/videos/{body['video']['id']}", headers=headers).json()
    assert video["status"] == "completed"
    assert video["script_text"] == "A script about Light roast."
    assert pipeline.script_calls == [
        {"topic": "Light roast", "style": "short_form", "duration": 60}
    ]


def test_voiceover_stage_runs_after_the_script(
    client, auth_headers, db, inline_runner, pipeline
):
    headers = auth_headers()
    project_id = _project(client, headers, topic="Light roast")

    body = client.post(
        f"/projects/{project_id}/generate",
        json={"stages": ["script", "voiceover"], "voice": "isley"},
        headers=headers,
    ).json()

    assert client.get(body["poll_url"], headers=headers).json()["status"] == "completed"
    assert pipeline.tts_calls == [("A script about Light roast.", "isley")]

    video = client.get(f"/videos/{body['video']['id']}", headers=headers).json()
    assert video["storage_key"] == "/tmp/videoforce/tts_fake.wav"


def test_a_failing_stage_records_the_reason_on_the_job(
    client, auth_headers, db, inline_runner, pipeline
):
    pipeline.script_error = PipelineError("the model returned nothing")
    headers = auth_headers()
    project_id = _project(client, headers)

    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()

    job = client.get(body["poll_url"], headers=headers).json()
    assert job["status"] == "failed"
    assert "script" in job["error_message"]
    assert "the model returned nothing" in job["error_message"]

    video = client.get(f"/videos/{body['video']['id']}", headers=headers).json()
    assert video["status"] == "failed"
    assert "the model returned nothing" in video["error_message"]


def test_an_unexpected_crash_is_captured_not_propagated(
    client, auth_headers, db, inline_runner, pipeline
):
    """A bug in a stage must become a failed job, not a 500 or a lost task."""
    pipeline.script_error = ZeroDivisionError("division by zero")
    headers = auth_headers()
    project_id = _project(client, headers)

    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()

    job = client.get(body["poll_url"], headers=headers).json()
    assert job["status"] == "failed"
    assert "ZeroDivisionError" in job["error_message"]


def test_a_failed_job_does_not_consume_quota(
    client, auth_headers, db, inline_runner, pipeline
):
    pipeline.script_error = PipelineError("nope")
    headers = auth_headers()
    project_id = _project(client, headers)

    client.post(f"/projects/{project_id}/generate", json={}, headers=headers)

    quota = client.get("/videos/quota", headers=headers).json()
    assert quota["used"] == 0
    assert quota["in_flight"] == 0
    assert quota["remaining"] == quota_service.FALLBACK_VIDEO_LIMIT


def test_a_successful_job_consumes_exactly_one(
    client, auth_headers, db, inline_runner
):
    headers = auth_headers()
    project_id = _project(client, headers)
    client.post(f"/projects/{project_id}/generate", json={}, headers=headers)

    quota = client.get("/videos/quota", headers=headers).json()
    assert quota["used"] == 1
    assert quota["remaining"] == quota_service.FALLBACK_VIDEO_LIMIT - 1


def test_runner_never_raises_for_a_missing_job(pipeline):
    asyncio.run(job_service.run_generation_job(999_999, pipeline=pipeline))


def test_runner_handles_a_video_deleted_before_it_ran(db, make_user, pipeline):
    user = make_user()
    project = Project(user_id=user.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    video, job = job_service.create_generation_job(db, project)
    db.commit()
    job_id, video_id = job.id, video.id

    db.delete(db.get(Video, video_id))
    db.commit()

    asyncio.run(job_service.run_generation_job(job_id, pipeline=pipeline))

    db.expire_all()
    refreshed = db.get(VideoJob, job_id)
    assert refreshed.status == "failed"
    assert "deleted" in refreshed.error_message


# --- Cancellation --------------------------------------------------------------------------


def test_cancel_a_pending_job(client, auth_headers, db, deferred_runner):
    headers = auth_headers()
    project_id = _project(client, headers)
    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()
    job_id = body["job"]["id"]

    response = client.post(f"/jobs/{job_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["completed_at"] is not None


def test_cancelling_releases_the_quota_slot(client, auth_headers, deferred_runner):
    headers = auth_headers()
    project_id = _project(client, headers)
    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()

    assert client.get("/videos/quota", headers=headers).json()["in_flight"] == 1
    client.post(f"/jobs/{body['job']['id']}/cancel", headers=headers)
    assert client.get("/videos/quota", headers=headers).json()["in_flight"] == 0


def test_a_cancelled_job_is_not_executed(db, make_user, pipeline):
    """The runner must notice the cancel rather than claim the job anyway."""
    user = make_user()
    project = Project(user_id=user.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    video, job = job_service.create_generation_job(db, project)
    db.commit()
    job_id = job.id

    assert job_service.request_cancel(db, job) is True
    asyncio.run(job_service.run_generation_job(job_id, pipeline=pipeline))

    db.expire_all()
    assert db.get(VideoJob, job_id).status == "cancelled"
    assert pipeline.script_calls == []


def test_cancelling_a_finished_job_returns_409(client, auth_headers, inline_runner):
    headers = auth_headers()
    project_id = _project(client, headers)
    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()

    response = client.post(f"/jobs/{body['job']['id']}/cancel", headers=headers)
    assert response.status_code == 409
    assert "already finished" in response.json()["detail"]


def test_cancel_mid_run_stops_at_the_next_stage_boundary(
    client, auth_headers, db, pipeline
):
    """Stages shell out to binaries and cannot be preempted, so cancellation
    is cooperative: it lands at the boundary, and later stages do not run."""
    headers = auth_headers()
    project_id = _project(client, headers)

    state: dict[str, int] = {}

    async def run(job_id: int) -> None:
        state["job_id"] = job_id
        # Cancel from a separate session while the script stage is executing.
        def cancel_now():
            from apps.api.core.db import SessionLocal

            other = SessionLocal()
            try:
                job = other.get(VideoJob, job_id)
                job_service.request_cancel(other, job)
            finally:
                other.close()

        pipeline.on_script = cancel_now
        await job_service.run_generation_job(job_id, pipeline=pipeline)

    previous = job_service.set_runner(run)
    try:
        client.post(
            f"/projects/{project_id}/generate",
            json={"stages": ["script", "voiceover"]},
            headers=headers,
        )
    finally:
        job_service.set_runner(previous)

    db.expire_all()
    job = db.get(VideoJob, state["job_id"])
    assert job.status == "cancelled"
    assert pipeline.tts_calls == []  # the second stage never started


# --- Job visibility ------------------------------------------------------------------------------


def test_another_users_job_is_indistinguishable_from_a_missing_one(
    client, auth_headers, make_user, db, deferred_runner
):
    owner = make_user(email="owner@example.com")
    project = Project(user_id=owner.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    video, job = job_service.create_generation_job(db, project)
    db.commit()

    headers = auth_headers(email="attacker@example.com")
    existing = client.get(f"/jobs/{job.id}", headers=headers)
    missing = client.get("/jobs/99999", headers=headers)

    assert existing.status_code == 404
    assert existing.json() == missing.json()


def test_another_users_job_cannot_be_cancelled(
    client, auth_headers, make_user, db, deferred_runner
):
    owner = make_user(email="owner@example.com")
    project = Project(user_id=owner.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    video, job = job_service.create_generation_job(db, project)
    db.commit()
    job_id = job.id

    headers = auth_headers(email="attacker@example.com")
    assert client.post(f"/jobs/{job_id}/cancel", headers=headers).status_code == 404

    db.expire_all()
    assert db.get(VideoJob, job_id).status == "pending"


def test_admin_can_read_any_job(client, auth_headers, make_user, db, deferred_runner):
    owner = make_user(email="owner@example.com")
    project = Project(user_id=owner.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    video, job = job_service.create_generation_job(db, project)
    db.commit()

    headers = auth_headers(email="admin@example.com", role="ADMIN")
    assert client.get(f"/jobs/{job.id}", headers=headers).status_code == 200


def test_job_appears_in_the_videos_job_history(
    client, auth_headers, inline_runner
):
    headers = auth_headers()
    project_id = _project(client, headers)
    body = client.post(f"/projects/{project_id}/generate", json={}, headers=headers).json()

    jobs = client.get(f"/videos/{body['video']['id']}/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["id"] == body["job"]["id"]


# --- Pipeline status ------------------------------------------------------------------------------


def test_pipeline_status_lists_stage_availability(client, auth_headers, pipeline):
    headers = auth_headers()
    body = client.get("/pipeline/status", headers=headers).json()

    stages = {s["name"]: s for s in body["stages"]}
    assert set(stages) == {"script", "voiceover", "assemble"}
    assert stages["script"]["available"] is True
    assert stages["assemble"]["available"] is False
    # Assembly is implemented now, so the reason is a missing dependency
    # rather than missing code: no stock provider key is set in the suite.
    assert "stock media provider is configured" in stages["assemble"]["reason"]
    assert body["default_stages"] == ["script"]


def test_pipeline_status_explains_an_unavailable_stage(client, auth_headers, pipeline):
    pipeline.llm.reason = "Ollama is unreachable at http://localhost:11434"
    headers = auth_headers()
    body = client.get("/pipeline/status", headers=headers).json()

    script = next(s for s in body["stages"] if s["name"] == "script")
    assert script["available"] is False
    assert "unreachable" in script["reason"]


def test_pipeline_status_requires_authentication(client):
    assert client.get("/pipeline/status").status_code == 401
