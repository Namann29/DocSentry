import pytest

from app.extraction.service import ocr_engine, run_extraction
from corpus.generate import build_scenario, render_scenario
from corpus.make_images import rasterise

pytestmark = pytest.mark.skipif(ocr_engine() is None, reason="no OCR engine installed")


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    d = tmp_path_factory.mktemp("ocr")
    scn = build_scenario(1)
    files = render_scenario(scn, d / "src")
    return scn, {"pan": rasterise(files["pan_card"], d / "pan.png"), "aadhaar": rasterise(files["aadhaar"], d / "aad.png", rotate=1.5),
                 "slip": rasterise(files["salary_slip"], d / "slip.png")}


def test_pan_image_is_ocrd_and_classified(images):
    scn, imgs = images
    out = run_extraction(imgs["pan"])
    assert out.method.startswith("ocr_")
    assert out.classification.doc_type == "pan_card"
    assert out.result and out.result.data.get("pan") == scn.person.pan
    assert all(0 <= w.conf <= 1 for p in out.pages for w in p.words)
    assert out.pages[0].quality and "blur_variance" in out.pages[0].quality


def test_rotated_aadhaar_image_is_read_and_masked(images):
    scn, imgs = images
    out = run_extraction(imgs["aadhaar"])
    assert out.method.startswith("ocr_") and out.classification.doc_type == "aadhaar"
    assert out.result.data["aadhaar_masked"].endswith(scn.person.aadhaar_last4)


def test_slip_image_extracts_net_pay(images):
    scn, imgs = images
    out = run_extraction(imgs["slip"])
    assert out.classification.doc_type == "salary_slip"
    assert "net_pay" in out.result.data
    assert any(w.conf < 0.99 for p in out.pages for w in p.words)