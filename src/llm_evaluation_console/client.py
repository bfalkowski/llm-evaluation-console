from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_API_BASE_URL = "http://localhost:8000"


def get_configured_api_base_url() -> str:
    return os.getenv("LLM_EVALUATION_API_BASE_URL") or DEFAULT_API_BASE_URL


class ServiceClient:
    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        configured_url = base_url or get_configured_api_base_url()
        self.base_url = configured_url.rstrip("/")
        self._transport = transport

    def ready(self) -> dict[str, Any]:
        return self._request("GET", "/health/ready")

    def submit_evaluation(
        self,
        *,
        tenant_id: str,
        project_id: str,
        question: str,
        answer: str,
        rubric: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "question": question,
            "answer": answer,
        }
        if rubric:
            payload["rubric"] = rubric

        return self._request("POST", "/v1/evaluations", json=payload)

    def list_evaluations(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        limit: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        if project_id:
            params["project_id"] = project_id

        return self._request("GET", "/v1/evaluations", params=params)

    def get_evaluation(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/evaluations/{job_id}")

    def get_evaluation_details(self, *, job_id: str, tenant_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/evaluations/{job_id}/details",
            params={"tenant_id": tenant_id},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise RuntimeError(detail or f"Service returned {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Unable to reach service at {self.base_url}") from exc
