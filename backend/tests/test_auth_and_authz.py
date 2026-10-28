def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", json={"email": "admin@docsentry.local", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_no_token_rejected(client):
    assert client.get("/api/cases").status_code == 401


def test_viewer_cannot_create_case(client, users):
    r = client.post("/api/cases", headers=users["viewer"], json={"title": "Viewer case"})
    assert r.status_code == 403


def test_cross_user_access_blocked(client, users):
    r = client.post("/api/cases", headers=users["analyst"], json={"title": "Analyst private case"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.get(f"/api/cases/{cid}", headers=users["analyst2"]).status_code == 403
    assert client.get(f"/api/cases/{cid}", headers=users["viewer"]).status_code == 403
    assert client.get(f"/api/cases/{cid}", headers=users["reviewer"]).status_code == 200
    assert client.get(f"/api/cases/{cid}", headers=users["admin"]).status_code == 200
    # reviewer may read but not edit
    assert client.patch(f"/api/cases/{cid}", headers=users["reviewer"], json={"title": "xyz"}).status_code == 403
    assert client.patch(f"/api/cases/{cid}", headers=users["analyst"], json={"title": "renamed"}).status_code == 200


def test_list_is_owner_scoped(client, users):
    mine = {c["id"] for c in client.get("/api/cases", headers=users["analyst2"]).json()}
    for c in client.get("/api/cases", headers=users["admin"]).json():
        if c["title"] == "renamed":
            assert c["id"] not in mine


def test_non_admin_cannot_create_users(client, users):
    r = client.post("/api/auth/users", headers=users["analyst"],
                    json={"email": "evil@test.local", "password": "Password123!x", "role": "admin"})
    assert r.status_code == 403


def test_lockout_after_repeated_failures(client, users):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "viewer@test.local", "password": "wrong"})
    r = client.post("/api/auth/login", json={"email": "viewer@test.local", "password": "Password123!x"})
    assert r.status_code == 423