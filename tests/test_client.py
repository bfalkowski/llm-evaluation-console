from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from llm_evaluation_console.client import ServiceClient, get_configured_api_base_url


def make_client(handler: httpx.MockTransport) -> ServiceClient:
    return ServiceClient(base_url="http://service.test", transport=handler)


def json_response(payload: dict[str, Any], status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def test_submit_evaluation_sends_expected_payload() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["payload"] = json.loads(request.content)
        return json_response(
            {
                "job_id": "job-1",
                "status": "queued",
                "request_id": "request-1",
            }
        )

    client = make_client(httpx.MockTransport(handler))

    response = client.submit_evaluation(
        tenant_id="tenant-a",
        project_id="project-a",
        question="question",
        answer="answer",
        rubric="rubric",
    )

    assert response["job_id"] == "job-1"
    assert seen == {
        "method": "POST",
        "path": "/v1/evaluations",
        "payload": {
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "question": "question",
            "answer": "answer",
            "rubric": "rubric",
        },
    }


def test_list_evaluations_sets_tenant_project_and_limit_query_params() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return json_response({"items": []})

    client = make_client(httpx.MockTransport(handler))

    response = client.list_evaluations(
        tenant_id="tenant-a",
        project_id="project-a",
        limit=10,
    )

    assert response == {"items": []}
    assert seen == {
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "limit": "10",
    }


def test_get_evaluation_details_uses_tenant_scope() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["tenant_id"] = request.url.params["tenant_id"]
        return json_response({"job_id": "job-1", "question": "q", "answer": "a"})

    client = make_client(httpx.MockTransport(handler))

    response = client.get_evaluation_details(job_id="job-1", tenant_id="tenant-a")

    assert response["job_id"] == "job-1"
    assert seen == {
        "path": "/v1/evaluations/job-1/details",
        "tenant_id": "tenant-a",
    }


def test_http_errors_raise_runtime_error_with_response_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = make_client(httpx.MockTransport(handler))

    with pytest.raises(RuntimeError, match="not found"):
        client.get_evaluation("missing-job")


def test_configured_api_base_url_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_EVALUATION_API_BASE_URL", "http://cluster-service:80")

    assert get_configured_api_base_url() == "http://cluster-service:80"
