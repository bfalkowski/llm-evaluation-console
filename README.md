# LLM Evaluation Console

Streamlit operator console for submitting LLM evaluation jobs, reviewing service results,
and checking operational health.

## Local Setup

With `uv`:

```bash
uv run --python 3.12 --extra dev streamlit run streamlit_app.py
```

With an existing Python 3.12 environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
streamlit run streamlit_app.py
```

The console expects the service API at `http://localhost:8000` by default.

```bash
LLM_EVALUATION_API_BASE_URL=http://localhost:8000 streamlit run streamlit_app.py
```

If the service is running with `APP_AUTH_ENABLED=true`, generate a demo token in the
service repository and paste it into the console sidebar's bearer token field:

```bash
APP_AUTH_DEMO_SECRET=local-demo-secret \
python scripts/create_demo_jwt.py --tenant-id demo-tenant --subject local-user
```

When a bearer token is configured, the console sends `Authorization: Bearer <token>`
and lets the service derive tenant context from the token claims. Without a token, the
console keeps sending the sidebar tenant field for auth-disabled local workflows.

## Docker

```bash
docker build -t llm-evaluation-console .
docker run --rm -p 8501:8501 \
  -e LLM_EVALUATION_API_BASE_URL=http://host.docker.internal:8000 \
  llm-evaluation-console
```

The GitHub Actions workflow builds the image on pull requests and publishes images from `main` to:

```text
ghcr.io/bfalkowski/llm-evaluation-console
```

CI also runs dependency auditing with `pip-audit` and validates the Dockerfile policy
for non-root runtime, no `latest` base image tag, no-cache package installs, and
exec-form `CMD`.

## Service Contract

The console calls:

- `GET /health/ready`
- `POST /v1/evaluations`
- `GET /v1/evaluations`
- `GET /v1/evaluations/{job_id}`
- `GET /v1/evaluations/{job_id}/details`
- `GET /metrics`

Evaluation routes use bearer-token tenant context when a token is supplied. Tenant
query/body parameters are only used as the auth-disabled local fallback.

## Console Views

- Overview dashboard with run counts, status mix, recent scores, and latest activity.
- Submit form for evaluation requests.
- Evaluation table with tenant/project/status/score context.
- Detail view with result justification and request payload inspection.
- Operations view backed by the service `/metrics` endpoint.

Do not commit secrets, credentials, private URLs, or environment-specific config.
