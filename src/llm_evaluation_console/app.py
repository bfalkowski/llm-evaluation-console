from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from llm_evaluation_console.client import ServiceClient, get_configured_api_base_url
from llm_evaluation_console.metrics import parse_prometheus_text, sum_metric

st.set_page_config(
    page_title="LLM Evaluation Console",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

STATUS_ORDER = ["queued", "running", "succeeded", "failed"]
STATUS_COLORS = {
    "queued": "#64748b",
    "running": "#2563eb",
    "succeeded": "#047857",
    "failed": "#b42318",
}


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_age(value: str | None) -> str:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return "-"
    delta = datetime.now(UTC) - timestamp
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, "#475569")


def score_value(row: dict[str, Any]) -> int | None:
    score = row.get("score")
    if score is not None:
        return int(score)
    result = row.get("result")
    if isinstance(result, dict) and result.get("score") is not None:
        return int(result["score"])
    return None


def render_global_styles() -> None:
    st.markdown(
        """
        <style>
          div[data-testid="stMetric"] {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            background: #ffffff;
          }
          div[data-testid="stMetric"] label {
            color: #475569;
          }
          .console-header {
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 1rem;
            margin-bottom: 1rem;
          }
          .console-header h1 {
            font-size: 1.85rem;
            letter-spacing: 0;
            margin: 0;
          }
          .console-header p {
            color: #475569;
            margin: 0.25rem 0 0 0;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(api_status: str, base_url: str, auth_mode: str) -> None:
    st.markdown(
        f"""
        <div class="console-header">
          <h1>LLM Evaluation Console</h1>
          <p>{api_status} · {base_url} · {auth_mode}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_badge(status: str) -> None:
    color = status_color(status)
    st.markdown(
        f"""
        <span style="
          display:inline-flex;
          align-items:center;
          border-radius:999px;
          padding:0.25rem 0.55rem;
          background:{color}18;
          color:{color};
          font-size:0.82rem;
          font-weight:700;
        ">{status}</span>
        """,
        unsafe_allow_html=True,
    )


def render_score_chart(rows: list[dict[str, Any]], *, key: str) -> None:
    chart_rows = [
        {
            "job_id": row["job_id"][:8],
            "score": score_value(row),
            "status": row["status"],
            "updated_at": parse_timestamp(row.get("updated_at")),
        }
        for row in rows
        if score_value(row) is not None
    ]
    if not chart_rows:
        st.info("No scored evaluations yet.")
        return

    frame = pd.DataFrame(chart_rows).sort_values("updated_at")
    fig = px.bar(
        frame,
        x="job_id",
        y="score",
        color="status",
        color_discrete_map={
            "succeeded": "#047857",
            "failed": "#b42318",
            "queued": "#64748b",
            "running": "#2563eb",
        },
        height=260,
    )
    fig.update_layout(
        margin=dict(l=12, r=12, t=12, b=12),
        xaxis_title=None,
        yaxis_title="Score",
        legend_title=None,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def render_status_distribution(rows: list[dict[str, Any]], *, key: str) -> None:
    counts = {status: 0 for status in STATUS_ORDER}
    for row in rows:
        status = str(row.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1

    labels = [status for status, count in counts.items() if count]
    values = [counts[status] for status in labels]
    if not values:
        st.info("No evaluation activity yet.")
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.62,
                marker={"colors": [status_color(label) for label in labels]},
                textinfo="label+value",
            )
        ]
    )
    fig.update_layout(
        height=260,
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def render_score_distribution(rows: list[dict[str, Any]], *, key: str) -> None:
    scored = [
        {"score": score_value(row), "job_id": row["job_id"][:8]}
        for row in rows
        if score_value(row) is not None
    ]
    if not scored:
        st.info("No scored evaluations yet.")
        return

    frame = pd.DataFrame(scored)
    fig = px.histogram(frame, x="score", nbins=10, height=260)
    fig.update_traces(marker_color="#2563eb")
    fig.update_layout(
        margin=dict(l=12, r=12, t=12, b=12),
        xaxis_title="Score",
        yaxis_title="Runs",
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def render_overview(rows: list[dict[str, Any]]) -> None:
    total = len(rows)
    succeeded = sum(1 for row in rows if row.get("status") == "succeeded")
    failed = sum(1 for row in rows if row.get("status") == "failed")
    running = sum(1 for row in rows if row.get("status") in {"queued", "running"})
    scored = [score for row in rows if (score := score_value(row)) is not None]
    average_score = sum(scored) / len(scored) if scored else 0

    metrics = st.columns(5)
    metrics[0].metric("Runs", total)
    metrics[1].metric("Succeeded", succeeded)
    metrics[2].metric("Failed", failed)
    metrics[3].metric("In flight", running)
    metrics[4].metric("Avg score", f"{average_score:.1f}" if scored else "-")

    left, right = st.columns([0.48, 0.52], vertical_alignment="top")
    with left:
        st.subheader("Status mix")
        render_status_distribution(rows, key="overview-status-distribution")
    with right:
        st.subheader("Recent scores")
        render_score_chart(rows, key="overview-score-chart")

    if rows:
        st.subheader("Latest activity")
        latest = pd.DataFrame(rows[:8]).copy()
        latest["age"] = latest["updated_at"].map(format_age)
        latest["score"] = [score_value(row) for row in rows[:8]]
        st.dataframe(
            latest[["status", "job_id", "project_id", "score", "age"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "status": st.column_config.TextColumn("Status", width="small"),
                "job_id": st.column_config.TextColumn("Job ID", width="medium"),
                "project_id": st.column_config.TextColumn("Project", width="medium"),
                "score": st.column_config.NumberColumn("Score", format="%d"),
                "age": st.column_config.TextColumn("Updated", width="small"),
            },
        )


def load_jobs(
    client: ServiceClient,
    tenant_id: str,
    project_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    response = client.list_evaluations(
        tenant_id=tenant_id,
        project_id=project_id or None,
        limit=limit,
    )
    return list(response.get("jobs", response.get("items", [])))


def render_operations_metrics(client: ServiceClient) -> None:
    try:
        samples = parse_prometheus_text(client.metrics())
    except RuntimeError as exc:
        st.error(str(exc))
        return

    total_requests = sum_metric(samples, "http_requests_total")
    queued = sum_metric(samples, "evaluation_jobs_total", {"status": "queued"})
    succeeded = sum_metric(samples, "evaluation_jobs_total", {"status": "succeeded"})
    failed = sum_metric(samples, "evaluation_jobs_total", {"status": "failed"})
    scoring_count = sum_metric(samples, "evaluation_scoring_duration_seconds_count")
    scoring_sum = sum_metric(samples, "evaluation_scoring_duration_seconds_sum")
    recovered = sum_metric(samples, "evaluation_worker_recovered_jobs_total")
    average_scoring_ms = (scoring_sum / scoring_count * 1000) if scoring_count else 0

    top = st.columns(4)
    top[0].metric("HTTP requests", f"{total_requests:.0f}")
    top[1].metric("Succeeded jobs", f"{succeeded:.0f}")
    top[2].metric("Failed jobs", f"{failed:.0f}")
    top[3].metric("Avg scoring", f"{average_scoring_ms:.1f} ms")

    lower = st.columns(3)
    lower[0].metric("Queued jobs", f"{queued:.0f}")
    lower[1].metric("Scoring samples", f"{scoring_count:.0f}")
    lower[2].metric("Recovered stale jobs", f"{recovered:.0f}")

    if samples:
        st.dataframe(
            pd.DataFrame(samples),
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Metric", width="medium"),
                "labels": st.column_config.JsonColumn("Labels"),
                "value": st.column_config.NumberColumn("Value"),
            },
        )


def main() -> None:
    render_global_styles()

    api_base_url = st.sidebar.text_input("API base URL", value=get_configured_api_base_url())
    tenant_id = st.sidebar.text_input("Tenant", value="demo-tenant")
    project_id = st.sidebar.text_input("Project", value="demo-project")
    bearer_token = st.sidebar.text_input("Bearer token", value="", type="password")
    limit = st.sidebar.slider("Rows", min_value=5, max_value=100, value=25, step=5)

    client = ServiceClient(api_base_url, bearer_token=bearer_token.strip() or None)
    auth_mode = "bearer token" if bearer_token.strip() else "tenant fallback"

    api_status = "API unavailable"
    api_available = False
    try:
        health = client.ready()
        api_status = f"API {health.get('status', 'ready')}"
        api_available = True
    except RuntimeError as exc:
        st.error(str(exc))

    render_header(api_status, client.base_url, auth_mode)

    jobs: list[dict[str, Any]] = []
    if api_available:
        try:
            jobs = load_jobs(client, tenant_id, project_id, limit)
        except RuntimeError as exc:
            st.error(str(exc))

    overview_tab, submit_tab, jobs_tab, detail_tab, operations_tab = st.tabs(
        ["Overview", "Submit", "Evaluations", "Detail", "Operations"]
    )

    with overview_tab:
        render_overview(jobs)

    with submit_tab:
        left, right = st.columns([0.62, 0.38], vertical_alignment="top")
        with left:
            with st.form("submit-evaluation"):
                question = st.text_area(
                    "Question",
                    value="What reliability signals should an LLM platform track?",
                    height=120,
                )
                answer = st.text_area(
                    "Answer",
                    value=(
                        "A useful platform tracks failures, latency, cost, throughput, "
                        "and quality trends across tenants and projects."
                    ),
                    height=150,
                )
                rubric = st.text_area(
                    "Rubric",
                    value=(
                        "Score based on whether the answer mentions failures, latency, "
                        "cost, or quality."
                    ),
                    height=110,
                )
                submitted = st.form_submit_button("Submit evaluation", type="primary")

        with right:
            st.subheader("Submission context")
            st.metric("Tenant source", "Token" if bearer_token.strip() else "Sidebar")
            st.metric("Project", project_id)
            st.metric("Recent runs", len(jobs))

        if submitted:
            try:
                created = client.submit_evaluation(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    question=question,
                    answer=answer,
                    rubric=rubric.strip() or None,
                )
                st.session_state["selected_job_id"] = created["job_id"]
                st.success(f"Queued {created['job_id']}")
            except RuntimeError as exc:
                st.error(str(exc))

    with operations_tab:
        render_operations_metrics(client)

    with jobs_tab:
        left, right = st.columns([0.68, 0.32], vertical_alignment="top")
        with left:
            if jobs:
                frame = pd.DataFrame(jobs)
                frame["age"] = frame["updated_at"].map(format_age)
                frame["score"] = [score_value(job) for job in jobs]
                visible = frame[
                    ["status", "job_id", "tenant_id", "project_id", "score", "age"]
                ].copy()
                st.dataframe(
                    visible,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "job_id": st.column_config.TextColumn("Job ID", width="medium"),
                        "tenant_id": st.column_config.TextColumn("Tenant", width="small"),
                        "project_id": st.column_config.TextColumn("Project", width="small"),
                        "score": st.column_config.NumberColumn("Score", format="%d"),
                        "age": st.column_config.TextColumn("Updated", width="small"),
                    },
                )
                selected = st.selectbox(
                    "Selected job",
                    options=[job["job_id"] for job in jobs],
                    index=0,
                )
                st.session_state["selected_job_id"] = selected
            else:
                st.info("No evaluations found.")

        with right:
            st.subheader("Score distribution")
            render_score_distribution(jobs, key="jobs-score-distribution")
            st.subheader("Status mix")
            render_status_distribution(jobs, key="jobs-status-distribution")

    with detail_tab:
        selected_job_id = st.text_input(
            "Job ID",
            value=st.session_state.get("selected_job_id", ""),
        )

        if selected_job_id:
            try:
                job = client.get_evaluation(selected_job_id, tenant_id=tenant_id)
                top = st.columns(4)
                top[0].metric(
                    "Score",
                    job.get("result", {}).get("score") if job.get("result") else "-",
                )
                top[1].metric("Tenant", job.get("tenant_id", "-"))
                top[2].metric("Project", job.get("project_id", "-"))
                with top[3]:
                    render_status_badge(job.get("status", "unknown"))

                result = job.get("result")
                if result:
                    left, right = st.columns([0.35, 0.65], vertical_alignment="top")
                    with left:
                        st.subheader("Score")
                        st.metric("Value", result.get("score", "-"))
                        st.metric("Rubric used", str(result.get("rubric_used", "-")))
                    with right:
                        st.subheader("Justification")
                        st.write(result.get("justification", ""))

                with st.expander("Evaluation payload"):
                    details = client.get_evaluation_details(
                        job_id=selected_job_id,
                        tenant_id=job.get("tenant_id") or tenant_id,
                    )
                    st.markdown("#### Question")
                    st.write(details.get("question", ""))
                    st.markdown("#### Answer")
                    st.write(details.get("answer", ""))
                    st.markdown("#### Rubric")
                    st.write(details.get("rubric") or "-")
            except RuntimeError as exc:
                st.error(str(exc))
