"""Backend tests for grau TI Helpdesk."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://helpdesk-grau.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def deivid_token(s):
    r = s.post(f"{API}/auth/login", json={"username": "deividsuporte2006", "password": "83668743"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and data["user"]["username"] == "deividsuporte2006"
    return data["token"]


@pytest.fixture(scope="session")
def bruno_token(s):
    r = s.post(f"{API}/auth/login", json={"username": "bruno", "password": "81718608"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------- Auth ----------
class TestAuth:
    def test_login_bruno(self, bruno_token):
        assert bruno_token

    def test_login_bad_password(self, s):
        r = s.post(f"{API}/auth/login", json={"username": "deividsuporte2006", "password": "wrong"})
        assert r.status_code == 401

    def test_login_unknown_user(self, s):
        r = s.post(f"{API}/auth/login", json={"username": "nope", "password": "x"})
        assert r.status_code == 401

    def test_me_no_token(self):
        # Fresh session so no cookie is present
        r = requests.Session().get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, s, deivid_token):
        r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {deivid_token}"})
        assert r.status_code == 200
        assert r.json()["username"] == "deividsuporte2006"

    def test_login_sets_httponly_cookie(self):
        # Use a fresh session to inspect Set-Cookie
        sess = requests.Session()
        r = sess.post(f"{API}/auth/login", json={"username": "deividsuporte2006", "password": "83668743"})
        assert r.status_code == 200
        # Cookie present in jar
        assert "access_token" in sess.cookies.get_dict(), f"cookies: {sess.cookies.get_dict()}"
        # httpOnly + Secure flags in Set-Cookie header
        set_cookie = r.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "Secure" in set_cookie
        # /auth/me works via cookie (no Authorization header)
        me = sess.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "deividsuporte2006"

    def test_logout_clears_cookie(self):
        sess = requests.Session()
        r = sess.post(f"{API}/auth/login", json={"username": "bruno", "password": "81718608"})
        assert r.status_code == 200
        assert sess.get(f"{API}/auth/me").status_code == 200
        r = sess.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # After logout, /auth/me returns 401
        me = sess.get(f"{API}/auth/me")
        assert me.status_code == 401

    def test_bearer_fallback_still_works(self, deivid_token):
        # No cookie session — pure Authorization header
        sess = requests.Session()
        r = sess.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {deivid_token}"})
        assert r.status_code == 200
        assert r.json()["username"] == "deividsuporte2006"



# ---------- Tickets ----------
class TestTickets:
    ticket_id = None
    ticket_code = None

    def test_create_ticket(self, s):
        payload = {
            "requester_name": "TEST_User",
            "building": "TEST_BlocoA",
            "floor": "2",
            "room": "TEST_Lab01",
            "devices": {"pc": "problem", "mouse": "ok", "keyboard": "ok", "internet_projector": "ok"},
            "priority": "urgente",
            "talk_to_deivid": True,
            "notes": "Teste automatizado",
        }
        r = s.post(f"{API}/tickets", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["code"].startswith("GT-") and len(data["code"]) == 9
        assert data["status"] == "aberto"
        assert data["archived"] is False
        assert data["priority"] == "urgente"
        assert data["devices"]["pc"] == "problem"
        assert len(data["audit"]) == 1
        TestTickets.ticket_id = data["id"]
        TestTickets.ticket_code = data["code"]

    def test_create_ticket_missing_required(self, s):
        r = s.post(f"{API}/tickets", json={"requester_name": "", "building": "", "floor": "", "room": ""})
        assert r.status_code == 400

    def test_public_lookup_ok(self, s):
        assert TestTickets.ticket_code
        r = s.get(f"{API}/tickets/public/{TestTickets.ticket_code}")
        assert r.status_code == 200
        d = r.json()
        assert d["code"] == TestTickets.ticket_code
        assert d["status"] == "aberto"
        # No PII
        assert "requester_name" not in d
        assert "notes" not in d

    def test_public_lookup_not_found(self, s):
        r = s.get(f"{API}/tickets/public/GT-ZZZZZZ")
        assert r.status_code == 404

    def test_list_requires_auth(self):
        r = requests.Session().get(f"{API}/tickets")
        assert r.status_code == 401

    def test_list_tickets(self, s, deivid_token):
        r = s.get(f"{API}/tickets", headers={"Authorization": f"Bearer {deivid_token}"})
        assert r.status_code == 200
        codes = [t["code"] for t in r.json()]
        assert TestTickets.ticket_code in codes

    def test_stats(self, s, deivid_token):
        r = s.get(f"{API}/tickets/stats", headers={"Authorization": f"Bearer {deivid_token}"})
        assert r.status_code == 200
        d = r.json()
        for k in ("open", "in_progress", "urgent", "resolved", "buildings"):
            assert k in d
        assert d["urgent"] >= 1
        assert "TEST_BlocoA" in d["buildings"]

    def test_filter_by_building(self, s, deivid_token):
        r = s.get(f"{API}/tickets", params={"building": "TEST_BlocoA"}, headers={"Authorization": f"Bearer {deivid_token}"})
        assert r.status_code == 200
        assert all(t["building"] == "TEST_BlocoA" for t in r.json())

    def test_search(self, s, deivid_token):
        r = s.get(f"{API}/tickets", params={"search": "TEST_Lab01"}, headers={"Authorization": f"Bearer {deivid_token}"})
        assert r.status_code == 200
        assert any(t["code"] == TestTickets.ticket_code for t in r.json())

    def test_update_status_and_audit(self, s, deivid_token):
        h = {"Authorization": f"Bearer {deivid_token}"}
        r = s.patch(f"{API}/tickets/{TestTickets.ticket_id}/status", json={"status": "em_andamento"}, headers=h)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "em_andamento"
        assert len(d["audit"]) == 2
        assert d["audit"][-1]["action"] == "status_alterado"
        assert d["audit"][-1]["to_status"] == "em_andamento"

    def test_update_status_invalid(self, s, deivid_token):
        r = s.patch(
            f"{API}/tickets/{TestTickets.ticket_id}/status",
            json={"status": "foo"},
            headers={"Authorization": f"Bearer {deivid_token}"},
        )
        assert r.status_code == 400

    def test_archive_toggle(self, s, deivid_token):
        h = {"Authorization": f"Bearer {deivid_token}"}
        r = s.patch(f"{API}/tickets/{TestTickets.ticket_id}/archive", headers=h)
        assert r.status_code == 200
        assert r.json()["archived"] is True

        # Should not appear in active list
        r = s.get(f"{API}/tickets", headers=h)
        assert TestTickets.ticket_code not in [t["code"] for t in r.json()]

        # But should appear in archived list
        r = s.get(f"{API}/tickets", params={"archived": True}, headers=h)
        assert TestTickets.ticket_code in [t["code"] for t in r.json()]

        # Still exists (never deleted) — public lookup still works
        r = s.get(f"{API}/tickets/public/{TestTickets.ticket_code}")
        assert r.status_code == 200


# ---------- Chat ----------
class TestChat:
    def test_chat_public_streams(self, s):
        r = s.post(f"{API}/chat", json={"message": "Olá, quantos chamados existem?", "scope": "public"}, stream=True, timeout=60)
        assert r.status_code == 200
        text = "".join(chunk.decode("utf-8", errors="ignore") for chunk in r.iter_content(chunk_size=None))
        assert len(text.strip()) > 0

    def test_chat_admin_streams(self, s):
        r = s.post(f"{API}/chat", json={"message": "Resuma os chamados abertos", "scope": "admin"}, stream=True, timeout=60)
        assert r.status_code == 200
        text = "".join(chunk.decode("utf-8", errors="ignore") for chunk in r.iter_content(chunk_size=None))
        assert len(text.strip()) > 0
