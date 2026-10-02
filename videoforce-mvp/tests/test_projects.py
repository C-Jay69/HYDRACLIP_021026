"""Project CRUD, pagination and ownership isolation."""

from __future__ import annotations

from apps.api.models import Project, Video, VideoJob


def _create(client, headers, title="My Project", **extra):
    payload = {"title": title, **extra}
    return client.post("/projects", json=payload, headers=headers)


# --- Creation ----------------------------------------------------------------


def test_create_project_returns_201_and_owns_it(client, auth_headers):
    headers = auth_headers()
    response = _create(client, headers, title="Launch video", topic="Coffee roasting")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Launch video"
    assert body["topic"] == "Coffee roasting"
    assert body["status"] == "pending"
    assert body["settings_json"] == {}
    assert isinstance(body["id"], int)


def test_create_project_requires_authentication(client):
    assert _create(client, {}).status_code == 401


def test_create_project_rejects_blank_title(client, auth_headers):
    headers = auth_headers()
    assert _create(client, headers, title="   ").status_code == 422


def test_create_project_rejects_overlong_title(client, auth_headers):
    headers = auth_headers()
    assert _create(client, headers, title="x" * 201).status_code == 422


def test_client_cannot_set_status_on_create(client, auth_headers):
    """status is pipeline-owned; an injected value must be ignored."""
    headers = auth_headers()
    response = client.post(
        "/projects",
        json={"title": "Sneaky", "status": "completed"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_client_cannot_set_user_id_on_create(client, auth_headers, make_user, db):
    """Ownership comes from the token, never from the body."""
    victim = make_user(email="victim@example.com")
    headers = auth_headers(email="attacker@example.com")

    response = client.post(
        "/projects",
        json={"title": "Not yours", "user_id": victim.id},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["user_id"] != victim.id


# --- Listing -----------------------------------------------------------------


def test_list_returns_only_own_projects(client, auth_headers, make_user, db):
    other = make_user(email="other@example.com")
    db.add(Project(user_id=other.id, title="Other person's project", status="pending"))
    db.commit()

    headers = auth_headers(email="me@example.com")
    _create(client, headers, title="Mine")

    body = client.get("/projects", headers=headers).json()
    assert body["total"] == 1
    assert [p["title"] for p in body["items"]] == ["Mine"]


def test_list_is_paginated(client, auth_headers):
    headers = auth_headers()
    for i in range(5):
        _create(client, headers, title=f"Project {i}")

    body = client.get("/projects?limit=2&offset=0", headers=headers).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["has_more"] is True

    last = client.get("/projects?limit=2&offset=4", headers=headers).json()
    assert len(last["items"]) == 1
    assert last["has_more"] is False


def test_list_rejects_oversized_page(client, auth_headers):
    headers = auth_headers()
    assert client.get("/projects?limit=1000", headers=headers).status_code == 422


def test_list_rejects_negative_offset(client, auth_headers):
    headers = auth_headers()
    assert client.get("/projects?offset=-1", headers=headers).status_code == 422


def test_list_filters_by_status(client, auth_headers, db):
    headers = auth_headers()
    _create(client, headers, title="Pending one")
    project_id = _create(client, headers, title="Done one").json()["id"]

    done = db.get(Project, project_id)
    done.status = "completed"
    db.commit()

    body = client.get("/projects?status=completed", headers=headers).json()
    assert [p["title"] for p in body["items"]] == ["Done one"]


def test_list_rejects_unknown_status(client, auth_headers):
    headers = auth_headers()
    response = client.get("/projects?status=banana", headers=headers)
    assert response.status_code == 422
    assert "status must be one of" in response.json()["detail"]


def test_list_searches_titles(client, auth_headers):
    headers = auth_headers()
    _create(client, headers, title="Coffee roasting explainer")
    _create(client, headers, title="Tea brewing guide")

    body = client.get("/projects?q=coffee", headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Coffee roasting explainer"


def test_list_includes_video_count(client, auth_headers, db):
    headers = auth_headers()
    project_id = _create(client, headers).json()["id"]
    owner_id = db.get(Project, project_id).user_id

    db.add_all(
        [
            Video(project_id=project_id, user_id=owner_id, status="completed"),
            Video(project_id=project_id, user_id=owner_id, status="pending"),
        ]
    )
    db.commit()

    body = client.get("/projects", headers=headers).json()
    assert body["items"][0]["video_count"] == 2


def test_list_counts_zero_videos_without_dropping_the_project(client, auth_headers):
    """An outer join regression would make empty projects vanish from the list."""
    headers = auth_headers()
    _create(client, headers, title="Empty")

    body = client.get("/projects", headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["video_count"] == 0


# --- Retrieval and ownership --------------------------------------------------


def test_get_own_project(client, auth_headers):
    headers = auth_headers()
    project_id = _create(client, headers).json()["id"]

    response = client.get(f"/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_get_other_users_project_returns_404_not_403(client, auth_headers, make_user, db):
    """403 would confirm the id exists. The two cases must be indistinguishable."""
    victim = make_user(email="victim@example.com")
    project = Project(user_id=victim.id, title="Private", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    headers = auth_headers(email="attacker@example.com")
    existing = client.get(f"/projects/{project.id}", headers=headers)
    missing = client.get("/projects/99999", headers=headers)

    assert existing.status_code == 404
    assert existing.json() == missing.json()


def test_admin_can_read_any_project(client, auth_headers, make_user, db):
    owner = make_user(email="owner@example.com")
    project = Project(user_id=owner.id, title="Someone's", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    headers = auth_headers(email="admin@example.com", role="ADMIN")
    assert client.get(f"/projects/{project.id}", headers=headers).status_code == 200


# --- Updates ------------------------------------------------------------------


def test_patch_updates_only_supplied_fields(client, auth_headers):
    headers = auth_headers()
    project_id = _create(client, headers, title="Before", topic="Keep me").json()["id"]

    response = client.patch(
        f"/projects/{project_id}", json={"title": "After"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "After"
    assert response.json()["topic"] == "Keep me"


def test_patch_cannot_change_status(client, auth_headers):
    headers = auth_headers()
    project_id = _create(client, headers).json()["id"]

    response = client.patch(
        f"/projects/{project_id}", json={"status": "completed"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_patch_other_users_project_returns_404(client, auth_headers, make_user, db):
    victim = make_user(email="victim@example.com")
    project = Project(user_id=victim.id, title="Private", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    headers = auth_headers(email="attacker@example.com")
    response = client.patch(
        f"/projects/{project.id}", json={"title": "Defaced"}, headers=headers
    )
    assert response.status_code == 404

    db.expire_all()
    assert db.get(Project, project.id).title == "Private"


# --- Deletion ------------------------------------------------------------------


def test_delete_removes_project(client, auth_headers):
    headers = auth_headers()
    project_id = _create(client, headers).json()["id"]

    assert client.delete(f"/projects/{project_id}", headers=headers).status_code == 204
    assert client.get(f"/projects/{project_id}", headers=headers).status_code == 404


def test_delete_cascades_to_videos_and_jobs(client, auth_headers, db):
    """No FK constraints exist, so the cascade is application code worth testing."""
    headers = auth_headers()
    project_id = _create(client, headers).json()["id"]
    owner_id = db.get(Project, project_id).user_id

    video = Video(project_id=project_id, user_id=owner_id, status="completed")
    db.add(video)
    db.commit()
    db.refresh(video)
    db.add(VideoJob(video_id=video.id, job_type="generate", status="completed"))
    db.commit()

    video_id = video.id
    assert client.delete(f"/projects/{project_id}", headers=headers).status_code == 204

    # The request ran in its own session; drop this one's identity map.
    db.expire_all()
    assert db.query(Video).filter_by(project_id=project_id).count() == 0
    assert db.query(VideoJob).filter_by(video_id=video_id).count() == 0


def test_delete_leaves_other_projects_videos_alone(client, auth_headers, db):
    headers = auth_headers()
    doomed = _create(client, headers, title="Doomed").json()["id"]
    keeper = _create(client, headers, title="Keeper").json()["id"]
    owner_id = db.get(Project, keeper).user_id

    db.add(Video(project_id=keeper, user_id=owner_id, status="completed"))
    db.commit()

    client.delete(f"/projects/{doomed}", headers=headers)
    db.expire_all()
    assert db.query(Video).filter_by(project_id=keeper).count() == 1


def test_delete_other_users_project_returns_404(client, auth_headers, make_user, db):
    victim = make_user(email="victim@example.com")
    project = Project(user_id=victim.id, title="Private", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)

    headers = auth_headers(email="attacker@example.com")
    assert client.delete(f"/projects/{project.id}", headers=headers).status_code == 404
    db.expire_all()
    assert db.get(Project, project.id) is not None


# --- Nested videos --------------------------------------------------------------


def test_list_project_videos(client, auth_headers, db):
    headers = auth_headers()
    project_id = _create(client, headers).json()["id"]
    owner_id = db.get(Project, project_id).user_id

    db.add(Video(project_id=project_id, user_id=owner_id, status="completed"))
    db.commit()

    body = client.get(f"/projects/{project_id}/videos", headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["project_id"] == project_id


def test_list_videos_of_other_users_project_returns_404(
    client, auth_headers, make_user, db
):
    victim = make_user(email="victim@example.com")
    project = Project(user_id=victim.id, title="Private", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    db.add(Video(project_id=project.id, user_id=victim.id, status="completed"))
    db.commit()

    headers = auth_headers(email="attacker@example.com")
    assert client.get(f"/projects/{project.id}/videos", headers=headers).status_code == 404
