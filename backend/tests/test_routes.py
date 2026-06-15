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
@patch("api.routes.organise_user_data", new_callable=AsyncMock)
@patch("api.routes.AIOrganiser.job_batch_remap", new_callable=AsyncMock)
def test_valid_remap_n_sort_jobs(
    mock_job_batch_remap, mock_organise_user_data, mock_embed_job_data, mock_store_data
):
    mock_organise_user_data.return_value = ["123"]
    mock_job_batch_remap.return_value = [{"job_id": "123", "is_logical_match": "High", "logical_match_score": 90}]

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
    mock_store_data.assert_any_call([{"job_id": "123", "title": "SE at Google", "description": "Code"}], "job_data", "mock_test_uid_123", supabase_client=ANY)
    mock_embed_job_data.assert_called_once()
    mock_organise_user_data.assert_called_once()
    mock_job_batch_remap.assert_called_once()

# --- New Comprehensive Tests for search_initial_jobs ---

@patch("api.routes.clear_all_user_data", new_callable=AsyncMock)
@patch("api.routes.fetch_job_list", new_callable=AsyncMock)
def test_search_initial_jobs_no_file_with_query(mock_fetch_job_list, mock_clear_all_user_data):
    mock_fetch_job_list.return_value = [{"job_id": "999", "title": "PM"}]
    
    response = client.post("/api/v1/search-initial-jobs", data={"country": "Malaysia", "search_query": "Product Manager"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["auto_match_enabled"] is False
    assert data["user_data_dict"] is None
    assert len(data["raw_job_result"]) == 1
    mock_clear_all_user_data.assert_called_once()
    mock_fetch_job_list.assert_called_once_with(["Product Manager"], "Malaysia", "my", None, False)

@patch("api.routes.AIOrganiser.resume_analysis", new_callable=AsyncMock)
@patch("api.routes.clear_all_user_data", new_callable=AsyncMock)
def test_search_initial_jobs_invalid_resume(mock_clear_all, mock_resume_analysis):
    mock_resume_obj = MagicMock()
    mock_resume_obj.is_valid_resume = False
    mock_resume_analysis.return_value = mock_resume_obj
    
    file_content = b"Invalid PDF content"
    files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
    
    response = client.post("/api/v1/search-initial-jobs", data={"country": "Malaysia"}, files=files)
    
    assert response.status_code == 400
    assert "Invalid PDF file" in response.json()["detail"]

# --- New Comprehensive Tests for extract_single_job ---

@patch("api.routes.AIOrganiser.job_result_extraction", new_callable=AsyncMock)
def test_extract_single_job_success(mock_job_result_extraction):
    mock_job_result_extraction.return_value = {"extracted_key": "extracted_value"}
    payload = {"raw_job": {"job_id": "1", "title": "Raw"}}
    
    response = client.post("/api/v1/extract-single-job", json=payload)
    
    assert response.status_code == 200
    assert response.json() == {"extracted_key": "extracted_value"}
    mock_job_result_extraction.assert_called_once()

@patch("api.routes.asyncio.sleep", new_callable=AsyncMock)
@patch("api.routes.AIOrganiser.job_result_extraction", new_callable=AsyncMock)
def test_extract_single_job_retry_and_fallback(mock_extract, mock_sleep):
    # Simulate a timeout exception every time to force a fallback
    import asyncio
    mock_extract.side_effect = asyncio.TimeoutError("Timeout")
    
    payload = {"raw_job": {"job_id": "1", "title": "Raw"}}
    response = client.post("/api/v1/extract-single-job", json=payload)
    
    assert response.status_code == 200
    # Should fallback to raw_job
    assert response.json() == {"job_id": "1", "title": "Raw"}
    assert mock_extract.call_count == 3

# --- New Comprehensive Tests for remap_n_sort_jobs ---

@patch("api.routes.store_data", new_callable=AsyncMock)
def test_remap_n_sort_jobs_empty_user_data(mock_store_data):
    payload = {
        "user_data_dict": {},
        "organised_job_result": [{"job_id": "1", "title": "SE at Google"}]
    }
    
    response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["remap_applied"] is False
    assert len(data["jobs"]) == 1
    # Store data should be called twice (job_data and final_job_data)
    assert mock_store_data.call_count == 2

@patch("api.routes.store_data", new_callable=AsyncMock)
@patch("api.routes.embed_job_data", new_callable=AsyncMock)
@patch("api.routes.organise_user_data", new_callable=AsyncMock)
def test_remap_n_sort_jobs_zero_matches(mock_organise_user_data, mock_embed_job_data, mock_store_data):
    # Pinecone returns empty list
    mock_organise_user_data.return_value = []
    
    payload = {
        "user_data_dict": {"target_job_roles": ["Dev"]},
        "organised_job_result": [{"job_id": "1", "title": "SE"}]
    }
    
    response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["remap_applied"] is False
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "1"

# --- New Comprehensive Tests for get_saved_jobs ---

@patch("api.routes.retrieve_data", new_callable=AsyncMock)
def test_get_saved_jobs_success(mock_retrieve_data):
    # Returns (user_data, job_data, final_job_data)
    mock_retrieve_data.side_effect = [{"user": "data"}, [{"job": "data"}], [{"final": "data"}]]
    
    response = client.get("/api/v1/get-saved-jobs")
    
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "mock_test_uid_123"
    assert data["user_data"] == {"user": "data"}
    assert data["job_data"] == [{"job": "data"}]
    assert data["final_job_data"] == [{"final": "data"}]
    assert mock_retrieve_data.call_count == 3

@patch("api.routes.retrieve_data", new_callable=AsyncMock)
def test_get_saved_jobs_failure(mock_retrieve_data):
    mock_retrieve_data.side_effect = Exception("DB Error")
    
    response = client.get("/api/v1/get-saved-jobs")
    
    assert response.status_code == 500
    assert "Error retrieving saved jobs: DB Error" in response.json()["detail"]
