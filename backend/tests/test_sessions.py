"""Stage 6B part 2: sign-in sessions. The cookie, signing out, the 8-hour and 30-minute limits, the
Origin check, and APP_SECRET_KEY being made on first run."""

import logging
import stat
from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth import sessions
from app.config import ensure_secret
from app.db import SessionLocal, User, UserSession, utc_now
from app.main import app
from tests.auth_helpers import ORIGIN, TEST_PASSWORD, make_user


def sign_in(username: str, role: str = "operator", base_url: str = "http://testserver") -> TestClient:
    make_user(username, role)
    client = TestClient(app, base_url=base_url, headers={"Origin": base_url})
    response = client.post("/api/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return client


def session_rows(username: str) -> list[UserSession]:
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username).one()
        return db.query(UserSession).filter_by(user_id=user.id).all()


def test_the_cookie_is_httponly_and_samesite_strict():
    make_user("cookie.check", "operator")
    client = TestClient(app, headers=ORIGIN)
    response = client.post("/api/auth/login", json={"username": "cookie.check", "password": TEST_PASSWORD})
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{sessions.COOKIE_NAME}=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie  # plain http on this computer
    assert "expires" not in cookie.lower() and "max-age" not in cookie.lower()  # forgotten when the browser closes
    assert response.json()["user"]["role"] == "operator"


def test_the_cookie_is_secure_over_https():
    client = sign_in("https.user", base_url="https://testserver")
    assert client.cookies.get(sessions.COOKIE_NAME)
    make_user("https.user2", "operator")
    response = client.post("/api/auth/login", json={"username": "https.user2", "password": TEST_PASSWORD})
    assert "Secure" in response.headers["set-cookie"]


def test_only_a_fingerprint_of_the_token_is_stored():
    client = sign_in("fingerprint")
    token = client.cookies.get(sessions.COOKIE_NAME)
    assert len(token) >= 43  # 32 random bytes
    [row] = session_rows("fingerprint")
    assert row.token_hash != token and token not in row.token_hash


def test_me_and_sign_out():
    client = sign_in("sign.out")
    assert client.get("/api/auth/me").json()["user"]["username"] == "sign.out"
    assert client.get("/api/auth/status").json()["user"]["username"] == "sign.out"
    token = client.cookies.get(sessions.COOKIE_NAME)

    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert session_rows("sign.out") == []  # deleted on the server
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/status").json()["user"] is None
    # the old token is useless even if someone kept a copy
    stolen = TestClient(app, headers=ORIGIN, cookies={sessions.COOKIE_NAME: token})
    assert stolen.get("/api/auth/me").status_code == 401


def test_not_signed_in_is_401_with_a_friendly_message():
    anonymous = TestClient(app, headers=ORIGIN)
    response = anonymous.get("/api/auth/me")
    assert response.status_code == 401 and response.json()["detail"] == "Please sign in."
    forged = TestClient(app, headers=ORIGIN, cookies={sessions.COOKIE_NAME: "made-up-token"})
    assert forged.get("/api/auth/me").status_code == 401


def _age_session(username: str, created_ago: timedelta, seen_ago: timedelta) -> None:
    with SessionLocal() as db:
        for row in db.query(UserSession).join(User).filter(User.username == username):
            row.created_at, row.last_seen = utc_now() - created_ago, utc_now() - seen_ago
        db.commit()


def test_sessions_end_after_8_hours_even_when_busy():
    client = sign_in("long.day")
    _age_session("long.day", timedelta(hours=7, minutes=59), timedelta(minutes=1))
    assert client.get("/api/auth/me").status_code == 200
    _age_session("long.day", timedelta(hours=8, minutes=1), timedelta(minutes=1))
    response = client.get("/api/auth/me")
    assert response.status_code == 401 and "8-hour" in response.json()["detail"]
    assert session_rows("long.day") == []


def test_sessions_end_after_30_idle_minutes():
    client = sign_in("coffee.break")
    _age_session("coffee.break", timedelta(hours=1), timedelta(minutes=29))
    assert client.get("/api/auth/me").status_code == 200  # ... and this request counts as activity
    [row] = session_rows("coffee.break")
    assert utc_now() - row.last_seen.replace(tzinfo=utc_now().tzinfo) < timedelta(seconds=5)

    _age_session("coffee.break", timedelta(hours=1), timedelta(minutes=31))
    response = client.get("/api/auth/me")
    assert response.status_code == 401 and "30 minutes" in response.json()["detail"]


def test_switching_a_user_off_ends_their_session():
    client = sign_in("soon.off")
    make_user("soon.off", "operator", is_active=False)
    assert client.get("/api/auth/me").status_code == 401


def test_changing_the_password_signs_out_other_computers():
    laptop = sign_in("two.places")
    desktop = TestClient(app, headers=ORIGIN)
    desktop.post("/api/auth/login", json={"username": "two.places", "password": TEST_PASSWORD})
    assert len(session_rows("two.places")) == 2
    response = laptop.post("/api/auth/change-password", json={"current_password": TEST_PASSWORD,
                                                               "new_password": "a new long passphrase"})
    assert response.status_code == 200, response.text
    assert laptop.get("/api/auth/me").status_code == 200
    assert desktop.get("/api/auth/me").status_code == 401


def test_wrong_passwords_answer_401_then_423_when_locked():
    make_user("api.lock", "operator")
    client = TestClient(app, headers=ORIGIN)
    codes = [client.post("/api/auth/login", json={"username": "api.lock", "password": "wrong password!"}).status_code
             for _ in range(6)]
    assert codes == [401, 401, 401, 401, 423, 423]
    assert sessions.COOKIE_NAME not in client.cookies


# ---- the Origin check -----------------------------------------------------------------------------


def test_changes_from_other_websites_are_refused():
    client = sign_in("origin.check")
    token = client.cookies.get(sessions.COOKIE_NAME)
    for headers in ({}, {"Origin": "https://evil.example"}, {"Origin": "null"},
                    {"Referer": "https://evil.example/page"}):
        other = TestClient(app, headers=headers, cookies={sessions.COOKIE_NAME: token})
        response = other.post("/api/auth/logout")
        assert response.status_code == 403, headers
        assert "did not come from a Pramaan AI page" in response.json()["detail"]
    assert len(session_rows("origin.check")) == 1  # the forged sign-out did nothing

    # reading is not a change, so it is not checked (the SameSite cookie already protects it)
    assert TestClient(app, cookies={sessions.COOKIE_NAME: token}).get("/api/auth/me").status_code == 200
    # a Referer from our own page is accepted when there is no Origin header
    ours = TestClient(app, headers={"Referer": "http://localhost:5173/#/jobs"}, cookies={sessions.COOKIE_NAME: token})
    assert ours.post("/api/auth/logout").status_code == 200


# ---- APP_SECRET_KEY made on first run --------------------------------------------------------------


def test_an_empty_secret_is_made_and_saved_without_printing_it(tmp_path, monkeypatch, caplog, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text("AI_MODE=mock\n# comment\nNEW_TEST_SECRET=\nDATA_DIR=./data\n")
    monkeypatch.delenv("NEW_TEST_SECRET", raising=False)
    with caplog.at_level(logging.DEBUG):
        value = ensure_secret("NEW_TEST_SECRET", env_file)
    assert len(value) == 64 and int(value, 16) >= 0
    assert env_file.read_text() == f"AI_MODE=mock\n# comment\nNEW_TEST_SECRET={value}\nDATA_DIR=./data\n"
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert "NEW_TEST_SECRET" in caplog.text and value not in caplog.text
    captured = capsys.readouterr()
    assert value not in captured.out + captured.err

    # the second start uses the saved value, and a missing name is added at the end
    assert ensure_secret("NEW_TEST_SECRET", env_file) == value
    monkeypatch.delenv("OTHER_TEST_SECRET", raising=False)
    other = ensure_secret("OTHER_TEST_SECRET", env_file)
    assert env_file.read_text().endswith(f"OTHER_TEST_SECRET={other}\n") and other != value
    monkeypatch.delenv("NEW_TEST_SECRET")
    monkeypatch.delenv("OTHER_TEST_SECRET")
