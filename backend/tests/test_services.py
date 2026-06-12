import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from schemas.resume_schema import ResumeSearchData

# Test AI_extract_service
from services.AI_extract_service import AIOrganiser

@pytest.fixture(autouse=True)
def clear_llm_cache():
    from services.AI_extract_service import _structured_llm_cache
    _structured_llm_cache.clear()
    yield

@pytest.mark.asyncio
@patch("services.AI_extract_service._llm_instance")
async def test_resume_extraction_success(mock_llm):
    mock_structured_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm
    mock_structured_llm.ainvoke = AsyncMock(return_value=ResumeSearchData(
        is_valid_resume=True,
        target_job_roles=["Dev"],
        years_of_experience=5,
        primary_competencies=["Python"],
        secondary_competencies=[],
        experience_and_projects=[],
        languages=[],
        honours_and_awards=[],
        growth_intent=[],
        operational_style=[]
    ))

    mock_pdf = MagicMock()
    mock_pdf.file.read.return_value = b"Dummy content"

    result = await AIOrganiser.resume_analysis(mock_pdf)
    assert result.target_job_roles == ["Dev"]

@pytest.mark.asyncio
@patch("services.AI_extract_service._llm_instance")
async def test_job_result_extraction_success(mock_llm):
    mock_structured_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {"key_responsibilities": ["Code"]}
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)

    job_result = {"title": "SE", "description": "Do stuff", "salary": "100k"}
    result = await AIOrganiser.job_result_extraction(job_result)
    
    assert "key_responsibilities" in result
    assert result["title"] == "SE"
    assert result["salary"] == "100k"

@pytest.mark.asyncio
@patch("services.AI_extract_service._llm_instance")
async def test_llm_api_failure_handling(mock_llm):
    mock_structured_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm
    mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))

    mock_pdf = MagicMock()
    mock_pdf.file.read.return_value = b"Dummy content"

    with pytest.raises(HTTPException) as excinfo:
        await AIOrganiser.resume_analysis(mock_pdf)
    
    assert excinfo.value.status_code == 500
    assert "Error analysing resume: API Error" in str(excinfo.value.detail)

# Test supabase_service
from services.supabase_service import store_data, retrieve_data

@pytest.mark.asyncio
@patch("services.supabase_service._get_supabase")
async def test_store_user_data(mock_get_supabase):
    mock_supabase = MagicMock()
    mock_get_supabase.return_value = mock_supabase
    
    mock_data = MagicMock()
    mock_data.model_dump.return_value = {"user": "test"}
    
    await store_data(mock_data, "user_data", "test_uid_123")
    mock_supabase.table.assert_called_with('user_data')
    mock_supabase.table().upsert.assert_called_with({"user_id": "test_uid_123", "data": {"user": "test"}})

@pytest.mark.asyncio
@patch("services.supabase_service._get_supabase")
async def test_store_job_data(mock_get_supabase):
    mock_supabase = MagicMock()
    mock_get_supabase.return_value = mock_supabase
    
    data = [{"job_id": "job1", "job": "1"}, {"job_id": "job2", "job": "2"}]
    await store_data(data, "job_data", "test_uid_123")
    
    mock_supabase.table.assert_any_call('user_jobs')
    mock_supabase.table().delete.assert_called()
    mock_supabase.table().insert.assert_called()

@pytest.mark.asyncio
@patch("services.supabase_service._get_supabase")
async def test_retrieve_data(mock_get_supabase):
    mock_supabase = MagicMock()
    mock_get_supabase.return_value = mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [{"data": {"some": "data"}}]
    mock_supabase.table().select().eq().execute.return_value = mock_response
    mock_supabase.table().select().eq().eq().execute.return_value = mock_response
    
    user_data = await retrieve_data("user", "test_uid_123")
    assert user_data == {"some": "data"}
    
    job_data = await retrieve_data("job", "test_uid_123")
    assert job_data == [{"some": "data"}]

# Test job_fetcher and pinecone_service
from services.job_fetcher import fetch_job_list
from services.pinecone_service import embed_job_data

@pytest.mark.asyncio
@patch("services.job_fetcher.client.search")
async def test_job_fetching_logic(mock_search):
    mock_search.return_value = {
        "jobs_results": [
            {
                "job_id": "1",
                "title": "SE",
                "company_name": "Tech Corp",
                "description": "desc",
                "detected_extensions": {"salary": "100k"}
            }
        ]
    }
    
    result = await fetch_job_list(["SE"], "Malaysia", "my")
    assert len(result) == 1
    assert result[0]["title"] == "SE"
    assert result[0]["salary"] == "100k"

@pytest.mark.asyncio
@patch("services.pinecone_service.asyncio.sleep", new_callable=AsyncMock)
@patch("services.pinecone_service.pc")
async def test_pinecone_organize_and_embed(mock_pc, mock_sleep):
    mock_dense_index = MagicMock()
    mock_pc.Index.return_value = mock_dense_index
    mock_stats = MagicMock()
    mock_stats.namespaces = {"job-detail": {"vector_count": 0}}
    mock_dense_index.describe_index_stats.return_value = mock_stats
    mock_pc.has_index.return_value = True
    
    job_data = [
        {
            "job_id": "1",
            "title": "SE",
            "core_skills": ["Python"],
            "soft_skills": ["Comm"],
            "key_responsibilities": ["Code"],
            "salary_parsed": {"min_salary": 50, "max_salary": 100}
        }
    ]
    
    await embed_job_data(job_data, "test_uid_123")
    mock_dense_index.upsert_records.assert_called()
