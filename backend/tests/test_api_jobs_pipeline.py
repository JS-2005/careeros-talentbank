import pytest
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Set dummy env vars before importing main to prevent Pinecone/Supabase init crashes
os.environ["PINECONE_API_KEY"] = "dummy-pinecone-key"
os.environ["SUPABASE_URL"] = "http://dummy-supabase.com"
os.environ["SUPABASE_KEY"] = "dummy-supabase-key"
os.environ["SERPAPI_API_KEY"] = "dummy-serpapi-key"

from main import app
from core.security import get_supabase_client
from services.AI_extract_service import AIOrganiser

# Create a test client
client = TestClient(app)

# Mocked UID
TEST_UID = "test-1234-uuid"

# Mock Supabase Dependency
async def override_get_supabase_client():
    mock_supabase = MagicMock()
    mock_supabase.user.id = TEST_UID
    return mock_supabase

app.dependency_overrides[get_supabase_client] = override_get_supabase_client

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset the dependencies if needed per test."""
    pass

@pytest.mark.asyncio
class TestSearchInitialJobs:

    @patch("api.routes.clear_all_user_data", new_callable=AsyncMock)
    @patch("api.routes.fetch_job_list", new_callable=AsyncMock)
    def test_search_initial_jobs_no_file(self, mock_fetch, mock_clear):
        mock_fetch.return_value = [{"title": "Software Engineer"}]
        
        response = client.post(
            "/api/v1/search-initial-jobs",
            data={
                "country": "United States",
                "state": "California",
                "is_intern": False,
                "search_query": "Developer"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["uid"] == TEST_UID
        assert data["raw_job_result"] == [{"title": "Software Engineer"}]
        assert data["auto_match_enabled"] is False
        assert data["user_data_dict"] is None
        
        mock_clear.assert_called_once()
        mock_fetch.assert_called_once_with(["Developer"], "United States", "us", "California", False)

    def test_search_initial_jobs_missing_inputs(self):
        response = client.post(
            "/api/v1/search-initial-jobs",
            data={
                "country": "United States",
            }
        )
        assert response.status_code == 400
        assert "Must upload resume pdf or enter search query" in response.json()["detail"]

    def test_search_initial_jobs_invalid_country(self):
        response = client.post(
            "/api/v1/search-initial-jobs",
            data={
                "country": "FakeCountryName",
                "search_query": "Developer"
            }
        )
        assert response.status_code == 400
        assert "Invalid country name" in response.json()["detail"]

    def test_search_initial_jobs_invalid_file(self):
        # Create a dummy txt file
        files = {"file": ("test.txt", b"dummy content", "text/plain")}
        response = client.post(
            "/api/v1/search-initial-jobs",
            data={
                "country": "United States",
            },
            files=files
        )
        assert response.status_code == 400
        assert "Valid Resume PDF file required" in response.json()["detail"]

    @patch("api.routes.clear_all_user_data", new_callable=AsyncMock)
    @patch("api.routes.fetch_job_list", new_callable=AsyncMock)
    @patch("services.AI_extract_service.AIOrganiser.resume_analysis", new_callable=AsyncMock)
    def test_search_initial_jobs_with_file_success(self, mock_resume_analysis, mock_fetch, mock_clear):
        mock_fetch.return_value = [{"title": "Backend Dev"}]
        
        # Mock resume response
        mock_resume_result = MagicMock()
        mock_resume_result.is_valid_resume = True
        mock_resume_result.target_job_roles = ["Software Engineer"]
        mock_resume_result.model_dump.return_value = {"skills": ["Python"]}
        mock_resume_analysis.return_value = mock_resume_result

        files = {"file": ("test.pdf", b"dummy pdf content", "application/pdf")}
        response = client.post(
            "/api/v1/search-initial-jobs",
            data={
                "country": "United States",
                "expected_salary": 100000
            },
            files=files
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_match_enabled"] is True
        assert data["user_data_dict"]["skills"] == ["Python"]
        assert data["user_data_dict"]["expected_salary"] == 100000
        
        mock_clear.assert_called_once()
        mock_resume_analysis.assert_called_once()
        mock_fetch.assert_called_once_with(["Software Engineer"], "United States", "us", None, False)


@pytest.mark.asyncio
class TestExtractSingleJob:

    @patch("services.AI_extract_service.AIOrganiser.job_result_extraction", new_callable=AsyncMock)
    def test_extract_single_job_success(self, mock_extraction):
        mock_extraction.return_value = {"extracted": True}
        
        payload = {"raw_job": {"title": "Raw Title"}}
        response = client.post("/api/v1/extract-single-job", json=payload)
        
        assert response.status_code == 200
        assert response.json() == {"extracted": True}

    @patch("services.AI_extract_service.AIOrganiser.job_result_extraction", new_callable=AsyncMock)
    def test_extract_single_job_timeout_retry(self, mock_extraction):
        # First call timeouts, second succeeds
        mock_extraction.side_effect = [asyncio.TimeoutError, {"extracted": "after_retry"}]
        
        payload = {"raw_job": {"title": "Raw Title"}}
        response = client.post("/api/v1/extract-single-job", json=payload)
        
        assert response.status_code == 200
        assert response.json() == {"extracted": "after_retry"}
        assert mock_extraction.call_count == 2

    @patch("services.AI_extract_service.AIOrganiser.job_result_extraction", new_callable=AsyncMock)
    def test_extract_single_job_complete_failure(self, mock_extraction):
        # All calls fail
        mock_extraction.side_effect = Exception("API Error")
        
        payload = {"raw_job": {"title": "Raw Title"}}
        response = client.post("/api/v1/extract-single-job", json=payload)
        
        assert response.status_code == 200
        # Falls back to raw job
        assert response.json() == {"title": "Raw Title"}
        assert mock_extraction.call_count == 3


@pytest.mark.asyncio
class TestRemapNSortJobs:

    @patch("api.routes.store_data", new_callable=AsyncMock)
    def test_remap_no_jobs(self, mock_store):
        payload = {
            "user_data_dict": {"skills": ["Python"]},
            "organised_job_result": []
        }
        response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["remap_applied"] is False

    @patch("api.routes.store_data", new_callable=AsyncMock)
    def test_remap_no_user_data(self, mock_store):
        payload = {
            "user_data_dict": {},
            "organised_job_result": [{"job_id": "1", "title": "Dev"}]
        }
        response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == [{"job_id": "1", "title": "Dev"}]
        assert data["remap_applied"] is False
        assert mock_store.call_count == 2 # job_data and final_job_data

    @patch("api.routes.store_data", new_callable=AsyncMock)
    @patch("api.routes.embed_job_data", new_callable=AsyncMock)
    @patch("api.routes.organise_user_data", new_callable=AsyncMock)
    @patch("services.AI_extract_service.AIOrganiser.job_batch_remap", new_callable=AsyncMock)
    def test_remap_success(self, mock_remap, mock_organise, mock_embed, mock_store):
        # We supply jobs without job_id to verify fallback ID logic
        payload = {
            "user_data_dict": {"skills": ["Python"]},
            "organised_job_result": [{"title": "Dev1"}, {"job_id": "job2", "title": "Dev2"}]
        }
        
        # When jobs are processed, first job gets a fallback_ uuid
        # Mock Pinecone sorting returning IDs in reverse
        def mock_organise_side_effect(user_data, uid):
            # Capture the modified jobs list which has the generated job IDs
            jobs = mock_embed.call_args[0][0]
            return [jobs[1]["job_id"], jobs[0]["job_id"]]
            
        mock_organise.side_effect = mock_organise_side_effect
        
        # Mock AI remap logic for the top 5
        mock_remap.return_value = [
            {"job_id": "job2", "title": "Dev2", "logical_match_score": 80},
            {"job_id": "fallback_x", "title": "Dev1", "logical_match_score": 90}
        ]

        response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["remap_applied"] is True
        
        jobs = data["jobs"]
        # Should be sorted by logical match score descending
        assert jobs[0]["logical_match_score"] == 90
        assert jobs[1]["logical_match_score"] == 80

    @patch("api.routes.store_data", new_callable=AsyncMock)
    @patch("api.routes.embed_job_data", new_callable=AsyncMock)
    @patch("api.routes.organise_user_data", new_callable=AsyncMock)
    def test_remap_pinecone_no_matches(self, mock_organise, mock_embed, mock_store):
        payload = {
            "user_data_dict": {"skills": ["Python"]},
            "organised_job_result": [{"job_id": "1", "title": "Dev1"}]
        }
        mock_organise.return_value = [] # Empty list from Pinecone

        response = client.post("/api/v1/remap-and-sort-jobs", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["remap_applied"] is False
        assert data["jobs"] == [{"job_id": "1", "title": "Dev1"}]


@pytest.mark.asyncio
class TestGetSavedJobs:

    @patch("api.routes.retrieve_data", new_callable=AsyncMock)
    def test_get_saved_jobs_success(self, mock_retrieve):
        # We need to return specific values for user, job, and final_job
        async def mock_retrieve_side_effect(table_name, uid, supabase_client):
            if table_name == "user":
                return {"user": "data"}
            elif table_name == "job":
                return [{"job": "data"}]
            elif table_name == "final_job":
                return [{"final": "job"}]
            return None
            
        mock_retrieve.side_effect = mock_retrieve_side_effect

        response = client.get("/api/v1/get-saved-jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["uid"] == TEST_UID
        assert data["user_data"] == {"user": "data"}
        assert data["job_data"] == [{"job": "data"}]
        assert data["final_job_data"] == [{"final": "job"}]

    @patch("api.routes.retrieve_data", new_callable=AsyncMock)
    def test_get_saved_jobs_error(self, mock_retrieve):
        mock_retrieve.side_effect = Exception("DB Connection Failed")
        
        response = client.get("/api/v1/get-saved-jobs")
        assert response.status_code == 500
        assert "Error retrieving saved jobs: DB Connection Failed" in response.json()["detail"]
