import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock, ANY
from main import app
import io

client = TestClient(app)

@pytest.fixture(autouse=True)
def override_auth():
    from core.security import get_supabase_client
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "mock_test_uid_123"
    mock_client.user = mock_user
    app.dependency_overrides[get_supabase_client] = lambda: mock_client
    yield
    app.dependency_overrides.clear()

def test_missing_pdf_file():
    response = client.post("/api/v1/search-initial-jobs", data={"country": "Malaysia"})
    assert response.status_code == 400
    assert "Must upload resume pdf or enter search query" in response.json()["detail"]

def test_invalid_file_type():
    file_content = b"This is a text file."
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    response = client.post("/api/v1/search-initial-jobs", data={"country": "Malaysia"}, files=files)
    assert response.status_code == 400
    assert "Valid Resume PDF file required" in response.json()["detail"]

@patch("api.routes.AIOrganiser.resume_analysis")
def test_invalid_country_parameter(mock_resume_analysis):
    mock_resume_obj = MagicMock()
    mock_resume_obj.is_valid_resume = True
    mock_resume_obj.target_job_roles = ["Software Engineer"]
    mock_resume_analysis.return_value = mock_resume_obj
    
    file_content = b"Dummy PDF content"
    files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
    response = client.post("/api/v1/search-initial-jobs", data={"country": "InvalidCountry"}, files=files)
    assert response.status_code == 400
    assert "Invalid country name" in response.json()["detail"]

@patch("api.routes.AIOrganiser.resume_analysis")
@patch("api.routes.fetch_job_list", new_callable=AsyncMock)
def test_valid_extract_n_group_jobs(
    mock_fetch_job_list, mock_resume_analysis
):
    mock_resume_obj = MagicMock()
    mock_resume_obj.is_valid_resume = True
    mock_resume_obj.target_job_roles = ["Software Engineer"]
    mock_resume_obj.model_dump.return_value = {"target_job_roles": ["Software Engineer"]}
    mock_resume_analysis.return_value = mock_resume_obj
    
    mock_fetch_job_list.return_value = [{"job_id": "123", "target_job_role": "Software Engineer", "title": "SE at Google", "description": "Code"}]
    
    file_content = b"Dummy PDF content"
    files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
    
    response = client.post("/api/v1/search-initial-jobs", data={"country": "Malaysia", "state": "KL"}, files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "uid" in data
    assert "user_data_dict" in data
    assert "raw_job_result" in data
    assert len(data["raw_job_result"]) == 1
    assert data["raw_job_result"][0]["job_id"] == "123"

@patch("api.routes.store_data", new_callable=AsyncMock)
@patch("api.routes.embed_job_data", new_callable=AsyncMock)
@patch("api.routes.organise_user_data")
def test_valid_remap_n_sort_jobs(
    mock_organise_user_data, mock_embed_job_data, mock_store_data
):
    mock_organise_user_data.return_value = ["123"]

    payload = {
        "user_data_dict": {"target_job_roles": ["Software Engineer"]},
        "organised_job_result": [{"job_id": "123", "title": "SE at Google", "description": "Code"}]
    }
    
    response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "123"
    assert data["remap_applied"] == False
    mock_store_data.assert_any_call([{"job_id": "123", "title": "SE at Google", "description": "Code"}], "job_data", "mock_test_uid_123", supabase_client=ANY)
    mock_embed_job_data.assert_called_once()
    mock_organise_user_data.assert_called_once()

@patch("api.routes.AIOrganiser.batch_job_result_extraction", new_callable=AsyncMock)
def test_extract_batch_jobs(mock_batch_extract):
    mock_batch_extract.return_value = [{"job_id": "1", "title": "Job 1", "extracted": True}]
    
    payload = {
        "raw_jobs": [{"job_id": "1", "title": "Job 1"}]
    }
    
    response = client.post("/api/v1/extract-batch-jobs", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["extracted"] == True
    mock_batch_extract.assert_called_once()

@patch("api.routes.AIOrganiser.batch_job_remap", new_callable=AsyncMock)
@patch("api.routes.check_cached_remap", new_callable=AsyncMock)
@patch("api.routes.upsert_job_batch", new_callable=AsyncMock)
def test_remap_batch_jobs(mock_upsert, mock_check_cache, mock_batch_remap):
    mock_check_cache.return_value = []
    mock_batch_remap.return_value = [{"job_id": "1", "logical_match_score": 85}]
    
    payload = {
        "user_data_dict": {"skills": ["Python"]},
        "jobs_to_evaluate": [{"job_id": "1", "title": "Job 1"}]
    }
    
    response = client.post("/api/v1/remap-batch-jobs", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["logical_match_score"] == 85
    mock_batch_remap.assert_called_once()
    mock_check_cache.assert_called_once()
    mock_upsert.assert_called_once()
