from __future__ import annotations

from typing import Any

from llm_evaluation_console.app import load_jobs, score_value


class FakeClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def list_evaluations(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        limit: int,
    ) -> dict[str, Any]:
        assert tenant_id == "tenant-a"
        assert project_id == "project-a"
        assert limit == 25
        return self.response


def test_load_jobs_uses_service_jobs_contract() -> None:
    jobs = [{"job_id": "job-1", "status": "succeeded"}]
    client = FakeClient({"jobs": jobs})

    assert load_jobs(client, "tenant-a", "project-a", 25) == jobs


def test_load_jobs_keeps_legacy_items_fallback() -> None:
    jobs = [{"job_id": "job-1", "status": "succeeded"}]
    client = FakeClient({"items": jobs})

    assert load_jobs(client, "tenant-a", "project-a", 25) == jobs


def test_score_value_reads_nested_service_result() -> None:
    assert score_value({"result": {"score": 42}}) == 42


def test_score_value_keeps_legacy_top_level_score() -> None:
    assert score_value({"score": 17}) == 17
