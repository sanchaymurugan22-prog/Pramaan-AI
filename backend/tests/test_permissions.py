"""Stage 6B part 7: the permission matrix. Every API endpoint x (not signed in, Operator, Reviewer, Admin).

    not signed in                  -> 401
    signed in, role not allowed    -> 403
    signed in, role allowed        -> anything but 401 / 403 (it may still be 404 / 409 / 400 for other reasons)

test_every_endpoint_is_in_the_matrix fails when a new endpoint is added without deciding who may use it.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import ORIGIN, make_user, signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

OP, RV, AD = "operator", "reviewer", "admin"
ANYONE = {OP, RV, AD}

# (method, path, roles allowed, JSON body or form data). {job}, {output}, {user}, {record} are filled in below.
MATRIX = [
    ("GET", "/api/options", ANYONE, None),
    ("GET", "/api/ai/ping", ANYONE, None),
    ("GET", "/api/auth/me", ANYONE, None),
    ("POST", "/api/auth/change-password", ANYONE, {"current_password": "not my password", "new_password": "x"}),
    # jobs
    ("POST", "/api/jobs", {OP}, {"form": {"text": "A short source for the permission test."}}),
    ("GET", "/api/jobs", {OP, RV}, None),
    ("GET", "/api/jobs/{job}", {OP, RV}, None),
    ("GET", "/api/jobs/{job}/sources/S1", {OP, RV}, None),
    ("POST", "/api/jobs/{job}/start", {OP}, {"outputs": ["x_thread"]}),
    ("POST", "/api/jobs/{job}/retry", {OP}, None),
    ("PUT", "/api/jobs/{job}/safety", {OP}, {}),
    # outputs
    ("PUT", "/api/jobs/{job}/outputs/{output}", {OP}, {"fields": []}),
    ("POST", "/api/jobs/{job}/outputs/{output}/regenerate", {OP}, None),
    ("GET", "/api/jobs/{job}/outputs/{output}/versions", {OP, RV}, None),
    ("GET", "/api/jobs/{job}/outputs/{output}/versions/1", {OP, RV}, None),
    ("GET", "/api/jobs/{job}/outputs/{output}/download?format=txt", {OP, RV}, None),
    ("GET", "/api/jobs/{job}/kit.zip", {OP, RV}, None),
    ("GET", "/api/jobs/{job}/compare", {OP, RV}, None),
    ("GET", "/api/jobs/{job}/kit-info", {OP, RV}, None),
    # review
    ("POST", "/api/jobs/{job}/submit", {OP}, {}),
    ("POST", "/api/jobs/{job}/review", {RV}, {"decision": "send_back", "notes": "Permission test note"}),
    ("GET", "/api/review/queue", {RV}, None),
    # signing and records (Stage 7)
    ("GET", "/api/jobs/{job}/sign-info", {RV}, None),
    ("POST", "/api/jobs/{job}/new-version", {OP}, None),
    ("GET", "/api/records/{record}", ANYONE, None),
    ("GET", "/api/records/{record}/qr.png", ANYONE, None),
    ("GET", "/api/records", {RV, AD}, None),
    ("POST", "/api/records/verify", {RV, AD}, None),
    ("GET", "/api/records/public-key.pem", ANYONE, None),
    ("POST", "/api/admin/records/{record}/withdraw", {AD}, {"reason": "Permission test"}),
    ("GET", "/api/admin/records/verify-bundle.zip", {AD}, None),
    ("POST", "/api/check-message", ANYONE, {"text": "Is this real?"}),
    # Stage 9B: line comments, profile
    ("GET", "/api/jobs/{job}/comments", {OP, RV}, None),
    ("POST", "/api/jobs/{job}/comments", {RV}, {"text": "A comment"}),
    ("DELETE", "/api/jobs/{job}/comments/999999", {RV}, None),
    ("GET", "/api/profile", ANYONE, None),
    ("PUT", "/api/profile", ANYONE, {}),
    # Stage 9A: notifications, search, dashboard
    ("GET", "/api/notifications", ANYONE, None),
    ("GET", "/api/notifications/count", ANYONE, None),
    ("POST", "/api/notifications/read-all", ANYONE, None),
    ("POST", "/api/notifications/999999/read", ANYONE, None),
    ("GET", "/api/search?q=ransomware", ANYONE, None),
    ("GET", "/api/dashboard", {OP}, None),
    ("GET", "/api/watch", {OP}, None),
    ("PUT", "/api/watch", {OP}, {}),
    ("POST", "/api/watch/folders", {OP}, {"name": "matrix"}),
    ("POST", "/api/watch/check", {OP}, None),
    ("POST", "/api/alerts/check", {OP}, {"message": "Do not open unknown links. Report fraud by calling 1930."}),
    ("POST", "/api/alerts", {OP}, {"type": "Other", "severity": "Advisory", "message": "x"}),
    # admin
    ("GET", "/api/admin/users", {AD}, None),
    ("POST", "/api/admin/users", {AD}, {"username": "matrix.made", "full_name": "Matrix Made", "role": "operator"}),
    ("PUT", "/api/admin/users/{user}", {AD}, {}),
    ("POST", "/api/admin/users/{user}/reset-password", {AD}, None),
    ("GET", "/api/admin/requests", {AD}, None),
    ("POST", "/api/admin/requests/999999/approve", {AD}, {}),
    ("POST", "/api/admin/requests/999999/reject", {AD}, None),
    ("GET", "/api/admin/audit", {AD}, None),
    ("POST", "/api/admin/audit/verify", {AD}, None),
]

# Open to everyone, signed in or not (the sign-in pages need them).
PUBLIC = [
    ("GET", "/api/health"),
    ("GET", "/api/auth/status"),
    ("POST", "/api/auth/setup"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/request-access"),
    ("POST", "/api/auth/forgot"),
    ("GET", "/api/auth/options"),
    ("GET", "/api/auth/computer"),
]

CLIENTS = {role: signed_in_client(role, f"matrix.{role}") for role in ANYONE}
CLIENTS[None] = TestClient(app, headers=ORIGIN)


@pytest.fixture(scope="module")
def ids() -> dict:
    """A finished job (made by the matrix Operator) and a user the Admin calls may change."""
    operator = CLIENTS[OP]
    job = operator.post("/api/jobs", data={"text": SAMPLE_REPORT.read_text(encoding="utf-8"), "outputs": ["x_thread"]})
    done = wait_for(job.json()["id"])
    target = make_user("matrix.target", "operator")
    return {"job": done["id"], "output": done["outputs"][0]["id"], "user": target.id, "record": "PRM-2000-000000"}


def call(client: TestClient, method: str, path: str, body):
    if isinstance(body, dict) and "form" in body:
        return client.request(method, path, data=body["form"])
    return client.request(method, path, json=body)


@pytest.mark.parametrize("role", [None, OP, RV, AD], ids=["not-signed-in", OP, RV, AD])
@pytest.mark.parametrize("method, path, allowed, body", MATRIX, ids=[f"{m} {p}" for m, p, _, _ in MATRIX])
def test_permission_matrix(ids, role, method, path, allowed, body):
    url = path.format(**ids)
    response = call(CLIENTS[role], method, url, body)
    if role is None:
        assert response.status_code == 401, f"{method} {url} without signing in: {response.status_code} {response.text}"
    elif role in allowed:
        assert response.status_code not in (401, 403), f"{role} should be allowed {method} {url}: {response.text}"
    else:
        assert response.status_code == 403, f"{role} must not {method} {url}: {response.status_code} {response.text}"
        assert "Only" in response.json()["detail"]


@pytest.mark.parametrize("method, path", PUBLIC, ids=[f"{m} {p}" for m, p in PUBLIC])
def test_public_endpoints_need_no_sign_in(method, path):
    response = CLIENTS[None].request(method, path, json={})
    assert response.status_code not in (401, 403)


def _template(path: str) -> str:
    """"/api/jobs/12/outputs/3?format=txt" -> "/api/jobs/{}/outputs/{}" (to compare with the app's routes)."""
    parts = path.split("?")[0].split("/")
    return "/".join("{}" if p.startswith("{") or p.isdigit() or p == "S1" else p for p in parts)


def app_endpoints() -> set[tuple[str, str]]:
    """Every endpoint of the app, from its OpenAPI description (the list shown at /docs)."""
    paths = app.openapi()["paths"]
    return {(method.upper(), _template(path)) for path, methods in paths.items() for method in methods}


def test_every_endpoint_is_in_the_matrix():
    covered = {(m, _template(p)) for m, p, _, _ in MATRIX} | {(m, p) for m, p in PUBLIC}
    endpoints = app_endpoints()
    assert len(endpoints) >= 36  # guard: the list itself must not come back empty
    missing = sorted(endpoints - covered)
    assert not missing, f"Not in the permission matrix (decide who may use them): {missing}"
    assert not covered - endpoints, f"In the matrix but not in the app: {sorted(covered - endpoints)}"


def test_a_temporary_password_only_allows_changing_it():
    """Signed in with an Admin's temporary password: everything else is 403 until it is changed."""
    make_user("matrix.temporary", "operator", must_change_password=True)
    client = signed_in_client("operator", "matrix.temporary")
    assert client.get("/api/auth/me").status_code == 200
    for method, path, _, body in MATRIX:
        if path.startswith("/api/auth/"):
            continue
        response = call(client, method, path.format(job=1, output=1, user=1, record="PRM-2000-000000"), body)
        assert response.status_code == 403, f"{method} {path}: {response.status_code}"
