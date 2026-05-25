# LLM Evaluation Console

Streamlit operator console for submitting LLM evaluation jobs and reviewing service results.

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

## Service Contract

The console calls:

- `GET /health/ready`
- `POST /v1/evaluations`
- `GET /v1/evaluations`
- `GET /v1/evaluations/{job_id}`
- `GET /v1/evaluations/{job_id}/details?tenant_id=...`

Do not commit secrets, credentials, private URLs, or environment-specific config.
