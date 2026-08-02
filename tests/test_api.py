"""Tests for FastAPI routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_config(client: TestClient) -> None:
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert "fields" in body
    assert len(body["fields"]) > 0
    assert body["fields"][0]["key"]
    assert body["max_upload_count"] == 100
    assert "batch_concurrency" in body


def test_extract_rejects_empty_batch(client: TestClient) -> None:
    response = client.post("/api/extract", files=[])
    assert response.status_code == 422


def test_extract_rejects_unsupported_type(client: TestClient) -> None:
    response = client.post(
        "/api/extract",
        files=[("files", ("bad.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@patch("api.routes.run_batch")
@patch("api.routes.build_provider")
def test_extract_returns_document_results(
    mock_build_provider: MagicMock,
    mock_run_batch: MagicMock,
    client: TestClient,
    tmp_path,
) -> None:
    from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus

    mock_build_provider.return_value = MagicMock()
    excel_path = tmp_path / "invoices_test.xlsx"
    csv_path = tmp_path / "invoices_test.csv"
    excel_path.write_bytes(b"xlsx")
    csv_path.write_bytes(b"csv")
    mock_run_batch.return_value = (
        excel_path,
        csv_path,
        [
            DocumentResult(
                source_filename="invoice.pdf",
                fields={
                    "supplier_gstin": FieldResult(
                        value="22AAAAA0000A1Z5",
                        status=FieldStatus.OK,
                    )
                },
                overall_status=DocumentStatus.OK,
            )
        ],
    )

    response = client.post(
        "/api/extract",
        files=[("files", ("invoice.pdf", b"%PDF-1.4", "application/pdf"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["excel_path"].endswith("invoices_test.xlsx")
    assert body["csv_path"].endswith("invoices_test.csv")
    assert len(body["results"]) == 1
    assert body["results"][0]["source_filename"] == "invoice.pdf"
    assert body["results"][0]["overall_status"] == "OK"
    assert body["results"][0]["fields"]["supplier_gstin"]["status"] == "OK"
    assert body["results"][0]["fields"]["supplier_gstin"]["value"] == "22AAAAA0000A1Z5"

    mock_run_batch.assert_called_once()
    call_kwargs = mock_run_batch.call_args.kwargs
    assert call_kwargs["max_concurrency"] >= 1
