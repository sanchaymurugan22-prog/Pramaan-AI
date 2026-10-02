"""Stage 6B part 1: accounts. First-time setup, password rules, lockout, access and reset requests,
and the Admin's changes (with the "last Admin" protection)."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import accounts
from app.auth.accounts import AccountError, SignInError
from app.auth.passwords import check_rules, PasswordRuleError, hash_password, temporary_password, verify_password
from app.db import AccountRequest, AuditEntry, SessionLocal, User, utc_now
from app.main import app
from tests.auth_helpers import ORIGIN, TEST_PASSWORD, empty_accounts, make_user

client = TestClient(app, headers=ORIGIN)


# ---- passwords -----------------------------------------------------------------------------------


def test_passwords_are_hashed_with_argon2id():
    stored = hash_password(TEST_PASSWORD)
    assert stored.startswith("$argon2id$") and TEST_PASSWORD not in stored
    assert verify_password(stored, TEST_PASSWORD)
    assert not verify_password(stored, TEST_PASSWORD + "!")
    assert not verify_password("not a hash", TEST_PASSWORD)


@pytest.mark.parametrize("password, why", [
    ("short-pass1", "at least 12"),
    ("x" * 129, "at most 128"),
    ("aaaaaaaaaaaaaaa", "same few characters"),
    ("Password1234", "too common"),
    ("priya.sharma-2026!", "username"),
    ("my name is Sharma ok", "your name"),
])
def test_password_rules(password, why):
    with pytest.raises(PasswordRuleError, match=why):
        check_rules(password, "priya.sharma", "Priya Sharma")


def test_good_passwords_and_temporary_passwords_pass_the_rules():
    check_rules(TEST_PASSWORD, "priya.sharma", "Priya Sharma")
    for _ in range(20):
        check_rules(temporary_password(), "priya.sharma", "Priya Sharma")


# ---- first-time setup ----------------------------------------------------------------------------


def test_first_time_setup_makes_the_first_admin_once():
    with empty_accounts():
        assert client.get("/api/auth/status").json()["needs_setup"] is True
        # no default accounts: nobody can sign in, and nothing can be requested yet
        with SessionLocal() as db:
            assert db.query(User).count() == 0
        assert client.post("/api/auth/request-access", json={
            "username": "rahul", "full_name": "Rahul Kumar", "role": "operator", "reason": "Cyber ops",
            "password": TEST_PASSWORD}).status_code == 409

        code = accounts.setup_code()  # printed in the server's terminal
        bad = client.post("/api/auth/setup", json={"username": "kavya", "full_name": "Kavya Nair", "password": "short",
                                                    "setup_code": code})
        assert bad.status_code == 400 and "12 characters" in bad.json()["detail"]

        made = client.post("/api/auth/setup", json={"username": "Kavya.Nair", "full_name": "Kavya  Nair",
                                                     "password": TEST_PASSWORD, "setup_code": code.lower()})
        assert made.status_code == 201, made.text
        user = made.json()["user"]
        assert (user["username"], user["full_name"], user["role"]) == ("kavya.nair", "Kavya Nair", "admin")
        assert "password_hash" not in user  # never sent to the web page
        assert "argon2" not in made.text

        assert client.get("/api/auth/status").json()["needs_setup"] is False
        again = client.post("/api/auth/setup", json={"username": "evil", "full_name": "Evil Admin",
                                                      "password": TEST_PASSWORD, "setup_code": code})
        assert again.status_code == 409


def test_first_time_setup_needs_the_code_printed_in_the_terminal(capsys):
    """v1.2: only the person at the server's terminal can make the first Admin."""
    with empty_accounts():
        code = accounts.setup_code(new=True)
        printed = capsys.readouterr().err
        assert f"Setup code:  {code}" in printed and re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", code)
        form = {"username": "first.admin", "full_name": "First Admin", "password": TEST_PASSWORD}
        for wrong in ("", "AAAA-AAAA"):
            refused = client.post("/api/auth/setup", json=form | {"setup_code": wrong})
            assert refused.status_code == 403 and "printed in the terminal" in refused.json()["detail"]
        assert client.get("/api/auth/status").json()["needs_setup"] is True
        # five wrong tries in all: a new code is printed, the old one stops working
        for _ in range(accounts.SETUP_TRIES - 3):
            client.post("/api/auth/setup", json=form | {"setup_code": "BBBB-BBBB"})
        last = client.post("/api/auth/setup", json=form | {"setup_code": "CCCC-CCCC"})
        assert last.status_code == 403 and "NEW code" in last.json()["detail"]
        new_code = accounts.setup_code()
        assert new_code != code and f"Setup code:  {new_code}" in capsys.readouterr().err
        assert client.post("/api/auth/setup", json=form | {"setup_code": code}).status_code == 403
        # the right code, typed loosely (spaces, small letters), works once
        made = client.post("/api/auth/setup", json=form | {"setup_code": f" {new_code.lower().replace('-', ' ')} "})
        assert made.status_code == 201, made.text
        # the code is never written to the audit trail
        with SessionLocal() as db:
            rows = [e.detail for e in db.query(AuditEntry).all()]
        assert any("wrong setup code" in r for r in rows) and not any(new_code in r or code in r for r in rows)


# ---- signing in and lockout ----------------------------------------------------------------------


def test_sign_in_checks_the_password_and_records_the_time():
    make_user("sign.in", "operator")
    with SessionLocal() as db:
        user = accounts.sign_in(db, "Sign.In", TEST_PASSWORD)  # usernames ignore upper/lower case
        assert user.last_login is not None and user.failed_attempts == 0
        with pytest.raises(SignInError) as wrong:
            accounts.sign_in(db, "sign.in", "wrong password here")
        assert wrong.value.event == "wrong_password" and str(wrong.value).startswith("Wrong username or password.")
        with pytest.raises(SignInError) as unknown:
            accounts.sign_in(db, "nobody.here", TEST_PASSWORD)
        assert unknown.value.event == "unknown_user" and str(unknown.value) == "Wrong username or password."


def test_five_wrong_passwords_lock_the_account_for_15_minutes():
    make_user("lock.me", "operator")
    with SessionLocal() as db:
        events = []
        for _ in range(5):
            with pytest.raises(SignInError) as refused:
                accounts.sign_in(db, "lock.me", "not the right password")
            events.append(refused.value.event)
        assert events == ["wrong_password"] * 4 + ["locked_now"]
        user = accounts.find_user(db, "lock.me")
        locked_for = user.locked_until.replace(tzinfo=None) - utc_now().replace(tzinfo=None)
        assert timedelta(minutes=14) < locked_for <= timedelta(minutes=15)

        # even the right password is refused while locked
        with pytest.raises(SignInError) as still:
            accounts.sign_in(db, "lock.me", TEST_PASSWORD)
        assert still.value.event == "locked" and "15 minutes" in str(still.value)

        # after 15 minutes the right password works again
        user.locked_until = utc_now() - timedelta(seconds=1)
        db.commit()
        assert accounts.sign_in(db, "lock.me", TEST_PASSWORD).username == "lock.me"


def test_a_right_password_resets_the_wrong_count():
    make_user("forgetful", "operator")
    with SessionLocal() as db:
        for _ in range(4):
            with pytest.raises(SignInError):
                accounts.sign_in(db, "forgetful", "not the right password")
        accounts.sign_in(db, "forgetful", TEST_PASSWORD)
        with pytest.raises(SignInError) as refused:
            accounts.sign_in(db, "forgetful", "not the right password")
        assert refused.value.event == "wrong_password"  # counting starts again


def test_switched_off_accounts_cannot_sign_in():
    make_user("switched.off", "operator", is_active=False)
    with SessionLocal() as db, pytest.raises(SignInError) as refused:
        accounts.sign_in(db, "switched.off", TEST_PASSWORD)
    assert refused.value.event == "inactive"


# ---- requests from the sign-in pages -------------------------------------------------------------


def access_form(**changes) -> dict:
    return {"username": "rahul.kumar", "full_name": "Rahul Kumar", "role": "operator",
            "reason": "I write advisories for cyber operations", "password": TEST_PASSWORD} | changes


def test_request_access_then_admin_approves():
    make_user("approver", "admin")
    response = client.post("/api/auth/request-access", json=access_form())
    assert response.status_code == 201, response.text
    assert response.json()["role_label"] == "Operator"

    # asking for Admin is not allowed; the same username twice is not allowed
    assert client.post("/api/auth/request-access", json=access_form(username="x.admin", role="admin")).status_code == 400
    assert client.post("/api/auth/request-access", json=access_form()).status_code == 400

    with SessionLocal() as db:
        # waiting: signing in says so (only with the right password)
        with pytest.raises(SignInError) as waiting:
            accounts.sign_in(db, "rahul.kumar", TEST_PASSWORD)
        assert waiting.value.event == "pending"
        with pytest.raises(SignInError) as wrong:
            accounts.sign_in(db, "rahul.kumar", "some other password")
        assert wrong.value.event == "unknown_user"

        request = db.query(AccountRequest).filter_by(username="rahul.kumar", status="pending").one()
        admin = accounts.find_user(db, "approver")
        user = accounts.approve_access(db, request, admin, role="reviewer")
        assert (user.role, user.must_change_password) == ("reviewer", False)
        assert request.status == "approved" and request.password_hash is None
        assert accounts.sign_in(db, "rahul.kumar", TEST_PASSWORD).id == user.id
        with pytest.raises(AccountError, match="already been handled"):
            accounts.approve_access(db, request, admin)


def test_rejected_request_cannot_sign_in():
    make_user("rejecter", "admin")
    client.post("/api/auth/request-access", json=access_form(username="meera.iyer", full_name="Meera Iyer"))
    with SessionLocal() as db:
        request = db.query(AccountRequest).filter_by(username="meera.iyer").one()
        accounts.reject_request(db, request, accounts.find_user(db, "rejecter"))
        with pytest.raises(SignInError) as refused:
            accounts.sign_in(db, "meera.iyer", TEST_PASSWORD)
        assert refused.value.event == "unknown_user"


def test_forgot_password_gives_the_same_answer_for_any_username():
    known = client.post("/api/auth/forgot", json={"username": "approver", "message": "Locked out"})
    unknown = client.post("/api/auth/forgot", json={"username": "no.such.person"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    client.post("/api/auth/forgot", json={"username": "approver"})  # asked twice: stored once
    with SessionLocal() as db:
        assert db.query(AccountRequest).filter_by(kind="reset", username="approver", status="pending").count() == 1


# ---- the Admin's changes -------------------------------------------------------------------------


def test_admin_creates_a_user_with_a_temporary_password():
    make_user("maker", "admin")
    with SessionLocal() as db:
        admin = accounts.find_user(db, "maker")
        user, temporary = accounts.create_user(db, admin, "new.person", "New Person", "operator")
        assert user.must_change_password and verify_password(user.password_hash, temporary)
        signed_in = accounts.sign_in(db, "new.person", temporary)
        assert signed_in.must_change_password
        with pytest.raises(AccountError, match="current password is wrong"):
            accounts.change_password(db, signed_in, "wrong", "a brand new secret phrase")
        with pytest.raises(AccountError, match="12 characters"):
            accounts.change_password(db, signed_in, temporary, "too short")
        accounts.change_password(db, signed_in, temporary, "a brand new secret phrase")
        assert not signed_in.must_change_password
        with pytest.raises(AccountError, match="already used"):
            accounts.create_user(db, admin, "new.person", "Someone Else", "reviewer")


def test_admin_reset_sets_a_temporary_password_and_unlocks():
    make_user("resetter", "admin")
    make_user("locked.out", "reviewer", locked_until=utc_now() + timedelta(minutes=10))
    client.post("/api/auth/forgot", json={"username": "locked.out"})
    with SessionLocal() as db:
        user = accounts.find_user(db, "locked.out")
        temporary = accounts.reset_password(db, accounts.find_user(db, "resetter"), user)
        assert user.must_change_password and not accounts.is_locked(user)
        assert accounts.sign_in(db, "locked.out", temporary).id == user.id
        assert db.query(AccountRequest).filter_by(kind="reset", username="locked.out").one().status == "done"


def test_the_last_admin_cannot_be_removed():
    with empty_accounts():
        only = make_user("only.admin", "admin")
        other = make_user("an.operator", "operator")
        with SessionLocal() as db:
            admin, operator = db.get(User, only.id), db.get(User, other.id)
            with pytest.raises(AccountError, match="only active Admin"):
                accounts.update_user(db, admin, admin, role="operator")
            with pytest.raises(AccountError, match="only active Admin"):
                accounts.update_user(db, admin, admin, is_active=False)
            assert accounts.update_user(db, admin, operator, role="admin") == ["role Operator → Admin"]
            # now there are two Admins: one can step down, but nobody can switch themselves off
            with pytest.raises(AccountError, match="your own account"):
                accounts.update_user(db, admin, admin, is_active=False)
            assert accounts.update_user(db, admin, admin, role="reviewer") == ["role Admin → Reviewer"]
