from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from llm_evaluation_console.client import ServiceClient, get_configured_api_base_url

st.set_page_config(
    page_title="LLM Evaluation Console",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def status_color(status: str) -> str:
    return {
        "queued": "#64748b",
        "running": "#2563eb",
        "succeeded": "#047857",
        "failed": "#b42318",
    }.get(status, "#475569")


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


def render_score_chart(rows: list[dict[str, Any]]) -> None:
    chart_rows = [
        {
            "job_id": row["job_id"][:8],
            "score": row.get("score"),
            "status": row["status"],
            "updated_at": parse_timestamp(row.get("updated_at")),
        }
        for row in rows
        if row.get("score") is not None
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
    st.plotly_chart(fig, use_container_width=True)


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
    return list(response.get("items", []))


api_base_url = st.sidebar.text_input("API base URL", value=get_configured_api_base_url())
tenant_id = st.sidebar.text_input("Tenant", value="demo-tenant")
project_id = st.sidebar.text_input("Project", value="demo-project")
limit = st.sidebar.slider("Rows", min_value=5, max_value=100, value=25, step=5)

client = ServiceClient(api_base_url)

st.title("LLM Evaluation Console")

health_slot = st.empty()
try:
    health = client.ready()
    health_slot.success(f"API {health.get('status', 'ready')} at {client.base_url}")
except RuntimeError as exc:
    health_slot.error(str(exc))

submit_tab, jobs_tab, detail_tab = st.tabs(["Submit", "Evaluations", "Detail"])

with submit_tab:
    with st.form("submit-evaluation"):
        question = st.text_area(
            "Question",
            value="What reliability signals should an LLM platform track?",
            height=120,
        )
        answer = st.text_area(
            "Answer",
            value=(
                "A useful platform tracks failures, latency, cost, throughput, and quality "
                "trends across tenants and projects."
            ),
            height=140,
        )
        rubric = st.text_area(
            "Rubric",
            value="Score based on whether the answer mentions failures, latency, cost, or quality.",
            height=110,
        )
        submitted = st.form_submit_button("Submit evaluation", type="primary")

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

with jobs_tab:
    left, right = st.columns([0.7, 0.3], vertical_alignment="top")
    try:
        jobs = load_jobs(client, tenant_id, project_id, limit)
    except RuntimeError as exc:
        jobs = []
        st.error(str(exc))

    with left:
        if jobs:
            frame = pd.DataFrame(jobs)
            visible = frame[
                ["status", "job_id", "tenant_id", "project_id", "score", "updated_at"]
            ].copy()
            st.dataframe(
                visible,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "job_id": st.column_config.TextColumn("Job ID", width="medium"),
                    "score": st.column_config.NumberColumn("Score", format="%d"),
                    "updated_at": st.column_config.DatetimeColumn("Updated"),
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
        st.subheader("Scores")
        render_score_chart(jobs)

with detail_tab:
    selected_job_id = st.text_input(
        "Job ID",
        value=st.session_state.get("selected_job_id", ""),
    )

    if selected_job_id:
        try:
            job = client.get_evaluation(selected_job_id)
            top = st.columns(4)
            top[0].metric("Score", job.get("result", {}).get("score") if job.get("result") else "-")
            top[1].metric("Tenant", job.get("tenant_id", "-"))
            top[2].metric("Project", job.get("project_id", "-"))
            with top[3]:
                render_status_badge(job.get("status", "unknown"))

            result = job.get("result")
            if result:
                st.subheader("Result")
                st.write(result.get("justification", ""))

            if st.button("Load payload"):
                details = client.get_evaluation_details(
                    job_id=selected_job_id,
                    tenant_id=job["tenant_id"],
                )
                st.subheader("Question")
                st.write(details.get("question", ""))
                st.subheader("Answer")
                st.write(details.get("answer", ""))
                st.subheader("Rubric")
                st.write(details.get("rubric") or "-")
        except RuntimeError as exc:
            st.error(str(exc))
