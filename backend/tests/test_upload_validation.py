import fitz
import pytest

from app.config import settings
from corpus.generate import build_scenario, render_scenario


@pytest.fixture(scope="module")
def pdf_bytes(tmp_path_factory):
    files = render_scenario(build_scenario(1), tmp_path_factory.mktemp("v"))
    return files["salary_slip"].read_bytes()


@pytest.fixture(scope="module")
def case_id(client, users):
    r = client.post("/api/cases", headers=users["analyst"], json={"title": "Upload validation case"})
    return r.json()["id"]


def _up(client, hdr, cid, name, data, password=None):
    form = {"password": password} if password else {}
    return client.post(f"/api/cases/{cid}/documents", headers=hdr, files=[("files", (name, data, "application/octet-stream"))], data=form)


def test_rejects_empty_wrong_type_and_mismatched_extension(client, users, case_id, pdf_bytes):
    assert _up(client, users["analyst"], case_id, "empty.pdf", b"").status_code == 422
    assert _up(client, users["analyst"], case_id, "evil.exe", b"MZ\x90\x00garbage").status_code == 422
    assert _up(client, users["analyst"], case_id, "notes.txt", b"hello").status_code == 422
    assert _up(client, users["analyst"], case_id, "slip.png", pdf_bytes).status_code == 422   # PDF bytes, PNG name
    assert _up(client, users["analyst"], case_id, "random.pdf", b"\x00\x01\x02" * 100).status_code == 422


def test_rejects_oversize(client, users, case_id, pdf_bytes):
    old = settings.max_upload_mb
    settings.max_upload_mb = 0
    try:
        assert _up(client, users["analyst"], case_id, "big.pdf", pdf_bytes).status_code == 422
    finally:
        settings.max_upload_mb = old


def test_safe_filename_and_traversal(client, users, case_id, pdf_bytes):
    r = _up(client, users["analyst"], case_id, "../../etc/passwd.pdf", pdf_bytes)
    assert r.status_code == 201
    assert r.json()[0]["original_filename"] == "passwd.pdf"


def test_encrypted_pdf_requires_correct_password(client, users, case_id, pdf_bytes, tmp_path):
    enc = tmp_path / "enc.pdf"
    with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
        d.save(str(enc), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner-secret", user_pw="user-secret")
    data = enc.read_bytes()
    r = _up(client, users["analyst"], case_id, "enc.pdf", data)
    assert r.status_code == 422 and r.json()["error"]["code"] == "password_required"
    assert _up(client, users["analyst"], case_id, "enc.pdf", data, "wrong").status_code == 422
    r = _up(client, users["analyst"], case_id, "enc.pdf", data, "user-secret")
    assert r.status_code == 201
    doc = r.json()[0]
    assert "decrypted_at_upload" in doc["security_flags"]
    r = client.post(f"/api/documents/{doc['id']}/extract", headers=users["analyst"])
    assert r.status_code == 200 and r.json()["doc_type"] == "salary_slip"


def test_viewer_cannot_upload_and_other_analyst_cannot_read(client, users, case_id, pdf_bytes):
    assert _up(client, users["viewer"], case_id, "x.pdf", pdf_bytes).status_code == 403
    r = _up(client, users["analyst"], case_id, "mine.pdf", pdf_bytes)
    did = r.json()[0]["id"]
    assert client.get(f"/api/documents/{did}", headers=users["analyst2"]).status_code == 403
    assert client.get(f"/api/documents/{did}/download", headers=users["analyst"]).status_code == 200
    assert client.get(f"/api/documents/{did}/pages/1", headers=users["analyst"]).headers["content-type"] == "image/png"