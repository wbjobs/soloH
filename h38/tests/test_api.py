import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_validate_sgrna_valid():
    valid_sgrna = "GACCCCCTCCACCCCGCCTCGGG"
    response = client.post(
        "/api/v1/offtarget/validate",
        params={"sgrna": valid_sgrna},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["sgrna"] == valid_sgrna[:20]
    assert data["pam"] == valid_sgrna[20:]


def test_validate_sgrna_invalid_length():
    invalid_sgrna = "GACCCCCTCCACCCCGCCT"
    response = client.post(
        "/api/v1/offtarget/validate",
        params={"sgrna": invalid_sgrna},
    )
    assert response.status_code == 422


def test_validate_sgrna_invalid_pam():
    invalid_sgrna = "GACCCCCTCCACCCCGCCTCAAA"
    response = client.post(
        "/api/v1/offtarget/validate",
        params={"sgrna": invalid_sgrna},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_predict_offtarget_validation():
    invalid_sgrna = "GACCCCCTCCACCCCGCCT"
    response = client.post(
        "/api/v1/offtarget/predict",
        json={"sgrna": invalid_sgrna},
    )
    assert response.status_code == 422


def test_api_root():
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data


def test_health_ready():
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200


def test_cache_clear():
    response = client.get("/api/v1/offtarget/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert "deleted_keys" in data


def test_batch_validation():
    invalid_request = {
        "sgrnas": []
    }
    response = client.post(
        "/api/v1/offtarget/batch",
        json=invalid_request,
    )
    assert response.status_code == 422


def test_igv_link_generation():
    request = {
        "chromosome": "chr1",
        "start": 1000000,
        "end": 1000023,
        "strand": "+",
        "expand": 50,
    }
    response = client.post(
        "/api/v1/offtarget/igv-link",
        json=request,
    )
    assert response.status_code == 200
    data = response.json()
    assert "igv_link" in data
    assert "locus" in data
    assert request["chromosome"] in data["locus"]


def test_igv_link_invalid_chromosome():
    request = {
        "chromosome": "chrInvalid",
        "start": 1000000,
        "end": 1000023,
    }
    response = client.post(
        "/api/v1/offtarget/igv-link",
        json=request,
    )
    assert response.status_code == 400
