"""CV upload validation, extraction, storage and deletion (spec E07-E10, S-06 - S-10)."""

import io
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import CV, InterviewSession
from tests.factories import make_docx, make_pdf
from tests.helpers import create_interview, upload_cv


def _stored_files() -> list[Path]:
    folder = get_settings().cv_storage_dir
    return sorted(folder.glob("*")) if folder.exists() else []


@pytest.mark.parametrize(
    ("filename", "data", "content_type", "extension"),
    [("my cv.pdf", make_pdf(), "application/pdf", "pdf"),
     ("Resume.DOCX", make_docx(), "application/octet-stream", "docx")],
)
def test_upload_pdf_and_docx(client, user_a, filename, data, content_type, extension):
    response = upload_cv(client, user_a, filename, data, content_type)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["cv"]["extension"] == extension
    assert body["cv"]["original_filename"] == filename
    assert body["cv"]["size_bytes"] == len(data)
    assert body["cv"]["parse_status"] == "parsed"
    assert {"Python", "PyTorch", "FastAPI", "Docker"} <= set(body["extracted"]["skills"])
    assert body["extracted"]["education"] == ["B.Sc. Computer Science - Example University"]
    # Private storage: a random name, never returned to the client.
    files = _stored_files()
    assert len(files) == 1 and files[0].name.endswith(f".{extension}")
    assert files[0].name not in response.text and filename not in files[0].name


def test_wrong_extension_rejected(client, user_a):
    response = upload_cv(client, user_a, "cv.doc", make_pdf())
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.parametrize(
    ("filename", "data"),
    [("fake.pdf", b"MZ\x90\x00 this is really an executable" * 10),
     ("fake.docx", make_pdf()),
     ("fake.pdf", make_docx())],
    ids=["exe-named-pdf", "pdf-named-docx", "docx-named-pdf"],
)
def test_content_must_match_extension(client, user_a, filename, data):
    response = upload_cv(client, user_a, filename, data)
    assert response.status_code == 415
    assert _stored_files() == []


def test_zip_that_is_not_a_docx_rejected(client, user_a):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "not a word document")
    assert upload_cv(client, user_a, "cv.docx", buffer.getvalue()).status_code == 415


def test_file_over_5_mb_rejected(client, user_a):
    big = make_pdf() + b"0" * (5 * 1024 * 1024)
    response = upload_cv(client, user_a, "big.pdf", big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert _stored_files() == []


def test_cv_without_text_rejected(client, user_a):
    response = upload_cv(client, user_a, "blank.pdf", make_pdf(["Hi"]))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CV_UNREADABLE"
    assert _stored_files() == []


def test_corrupt_pdf_rejected(client, user_a):
    response = upload_cv(client, user_a, "broken.pdf", b"%PDF-1.4\n garbage without objects")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CV_UNREADABLE"


def test_extra_or_missing_multipart_parts_rejected(client, user_a):
    extra = client.post("/api/v1/cvs", headers=user_a,
                        files={"file": ("cv.pdf", make_pdf(), "application/pdf")}, data={"note": "hi"})
    missing = client.post("/api/v1/cvs", headers=user_a, files={"other": ("cv.pdf", make_pdf(), "application/pdf")})
    assert extra.status_code == 422 and missing.status_code == 422


def test_unsafe_filename_is_sanitised(client, user_a):
    response = upload_cv(client, user_a, "../../etc/<script>cv.pdf", make_pdf())
    assert response.status_code == 201
    assert response.json()["cv"]["original_filename"] == "_script_cv.pdf"


def test_list_get_and_delete(client, user_a, api_session_factory):
    first = upload_cv(client, user_a, "first.pdf").json()["cv"]
    second = upload_cv(client, user_a, "second.docx", make_docx()).json()["cv"]
    interview = create_interview(client, user_a, second["id"]).json()

    listing = client.get("/api/v1/cvs", headers=user_a).json()
    assert listing["total"] == 2
    assert {item["id"] for item in listing["items"]} == {first["id"], second["id"]}
    detail = client.get(f"/api/v1/cvs/{second['id']}", headers=user_a)
    assert detail.status_code == 200 and "Python" in detail.json()["extracted"]["skills"]

    deleted = client.delete(f"/api/v1/cvs/{second['id']}", headers=user_a)
    assert deleted.status_code == 204
    assert client.delete(f"/api/v1/cvs/{second['id']}", headers=user_a).status_code == 404
    assert len(_stored_files()) == 1
    with api_session_factory() as db:
        assert db.scalar(select(CV).where(CV.id == uuid.UUID(second["id"]))) is None
        # The interview that used it is kept, with cv_id cleared.
        assert db.get(InterviewSession, uuid.UUID(interview["id"])).cv_id is None
