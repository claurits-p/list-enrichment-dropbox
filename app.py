"""List Enrichment Dropbox — Streamlit UI."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from clay_client import get_webhook_url, send_rows_to_clay
from config import APP_TITLE, OPTIONAL_HEADERS, REQUIRED_HEADERS
from list_id_store import next_list_id, recent_submissions, record_submission
from validator import normalize_columns, validate_rows

load_dotenv()

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="paystand_logo.png",
    layout="wide",
)

st.markdown(
    """<style>
    /* Navy blue subheaders to match title */
    h2, h3, [data-testid="stSubheader"] {
        color: #001F5B !important;
    }
    /* Paystand blue primary button */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #003B91 !important;
        border-color: #003B91 !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #002D6F !important;
        border-color: #002D6F !important;
    }
    /* Tighter section subtitle (gray) */
    .section-sub {
        color: #6c7280;
        font-size: 0.92rem;
        margin-top: -8px;
        margin-bottom: 14px;
    }
    /* Status pill */
    .status-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-ok   { background:#e8fde8; color:#1B8A4E; border:1px solid #c5edc5; }
    .status-warn { background:#fef3e8; color:#a85d1a; border:1px solid #f4d4ad; }
    /* Required-field chip */
    .chip {
        display: inline-block;
        padding: 3px 9px;
        margin: 2px 4px 2px 0;
        border-radius: 6px;
        font-size: 0.85rem;
        background: #eaf0fb;
        color: #003B91;
        border: 1px solid #cdddf6;
    }
    .chip-opt {
        background: #f4f5f7;
        color: #4a5363;
        border: 1px solid #dde0e6;
    }
    </style>""",
    unsafe_allow_html=True,
)

ASSETS = Path(__file__).parent / "assets"
FORMAT_IMAGE = ASSETS / "format_guide.png"
SAMPLE_CSV = ASSETS / "sample_template.csv"


def render_header():
    logo_col, title_col = st.columns([0.06, 0.94], gap="small")
    with logo_col:
        st.image("paystand_logo.png", width=55)
    with title_col:
        st.markdown(
            '<h1 style="color: #001F5B; margin-top: -5px;">'
            f"{APP_TITLE}</h1>",
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="section-sub">'
        "Upload a CSV in the required format. Rows are sent to Clay for enrichment."
        "</div>",
        unsafe_allow_html=True,
    )


def render_webhook_status():
    if get_webhook_url():
        st.markdown(
            '<span class="status-pill status-ok">Clay webhook configured</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-pill status-warn">Clay webhook not configured</span>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Add `CLAY_WEBHOOK_URL` to Streamlit Secrets (or `.env` locally) "
            "before submissions can be sent."
        )


def render_format_section():
    st.subheader("Required CSV format")
    st.markdown(
        '<div class="section-sub">'
        "Headers must match exactly. Required fields cannot be blank."
        "</div>",
        unsafe_allow_html=True,
    )

    if FORMAT_IMAGE.exists():
        img_col, _ = st.columns([0.6, 0.4])
        with img_col:
            st.image(str(FORMAT_IMAGE), use_container_width=True)

    chips_required = "".join(f'<span class="chip">{h}</span>' for h in REQUIRED_HEADERS)
    chips_optional = "".join(f'<span class="chip chip-opt">{h}</span>' for h in OPTIONAL_HEADERS)
    st.markdown("**Required columns**", unsafe_allow_html=True)
    st.markdown(chips_required, unsafe_allow_html=True)
    st.markdown("**Optional columns**", unsafe_allow_html=True)
    st.markdown(chips_optional, unsafe_allow_html=True)

    if SAMPLE_CSV.exists():
        st.download_button(
            label="Download sample CSV",
            data=SAMPLE_CSV.read_bytes(),
            file_name="list_enrichment_template.csv",
            mime="text/csv",
        )


def render_upload_section():
    st.subheader("Upload list")
    st.markdown(
        '<div class="section-sub">'
        "Tell us who you are and name the list, then drop the CSV."
        "</div>",
        unsafe_allow_html=True,
    )

    name_col, list_col = st.columns(2)
    with name_col:
        submitted_by = st.text_input(
            "Your name *",
            placeholder="e.g. Chris Laurits",
            help="So we know who submitted this list.",
        ).strip()
    with list_col:
        submission_list_name = st.text_input(
            "List name *",
            placeholder="e.g. Q2 Partner Webinar Attendees",
            help="A short label for this list (shown in recent submissions).",
        ).strip()

    missing_meta = []
    if not submitted_by:
        missing_meta.append("Your name")
    if not submission_list_name:
        missing_meta.append("List name")

    if missing_meta:
        st.info(
            f"Fill in **{', '.join(missing_meta)}** before uploading a CSV."
        )

    uploaded = st.file_uploader(
        "Drop your CSV here",
        type=["csv"],
        disabled=bool(missing_meta),
    )
    if uploaded is None:
        return

    try:
        raw_df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    if raw_df.empty:
        st.error("CSV has no data rows.")
        return

    df, col_errors = normalize_columns(raw_df)
    if col_errors:
        st.error("Column problems:")
        for err in col_errors:
            st.markdown(f"- {err}")
        return

    row_errors = validate_rows(df)
    if row_errors:
        st.error("Row problems:")
        for err in row_errors:
            st.markdown(f"- {err}")
        return

    st.success(f"Valid CSV — **{len(df)}** rows ready.")
    with st.expander("Preview (first 5 rows)"):
        st.dataframe(df.head(), use_container_width=True, hide_index=True)

    webhook_set = bool(get_webhook_url())
    submit = st.button(
        "Send to Clay",
        type="primary",
        disabled=not webhook_set,
        use_container_width=True,
    )

    if not submit:
        return

    list_id = next_list_id()
    filename = uploaded.name
    with st.spinner(f"Sending list **{list_id}** ({len(df)} rows)…"):
        sent, errors = send_rows_to_clay(
            df,
            list_id,
            submitted_by=submitted_by,
            submission_list_name=submission_list_name,
        )

    if sent == len(df):
        record_submission(
            list_id, len(df), filename, "sent",
            list_name=submission_list_name, submitted_by=submitted_by,
        )
        st.success(
            f"**List {list_id} — “{submission_list_name}”** — all **{sent}** "
            f"rows sent to Clay for enrichment."
        )
    elif sent > 0:
        msg = "; ".join(errors[:5])
        record_submission(
            list_id, len(df), filename, "partial",
            list_name=submission_list_name, submitted_by=submitted_by,
            error_message=msg,
        )
        st.warning(f"**List {list_id}** — sent **{sent}/{len(df)}** rows. Some failed.")
        for err in errors:
            st.markdown(f"- {err}")
    else:
        msg = "; ".join(errors[:5])
        record_submission(
            list_id, len(df), filename, "failed",
            list_name=submission_list_name, submitted_by=submitted_by,
            error_message=msg,
        )
        st.error(f"**List {list_id}** — nothing sent.")
        for err in errors:
            st.markdown(f"- {err}")


def render_history_section():
    st.subheader("Recent submissions")
    st.markdown(
        '<div class="section-sub">'
        "Latest lists submitted from this app instance."
        "</div>",
        unsafe_allow_html=True,
    )
    recent = recent_submissions()
    if not recent:
        st.caption("No submissions yet.")
        return

    df = pd.DataFrame(recent)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["Submitted"] = df["created_at"].dt.tz_convert("US/Pacific").dt.strftime(
        "%Y-%m-%d %I:%M %p"
    )
    display = df.rename(
        columns={
            "list_id": "List ID",
            "list_name": "List name",
            "submitted_by": "Submitted by",
            "row_count": "Rows",
            "status": "Status",
        }
    )[["List ID", "List name", "Submitted by", "Rows", "Status", "Submitted"]]

    st.dataframe(display, use_container_width=True, hide_index=True)

    errors_only = df[df["error_message"].notna() & (df["error_message"] != "")]
    if not errors_only.empty:
        with st.expander("Submissions with errors"):
            st.dataframe(
                errors_only[
                    ["list_id", "list_name", "submitted_by", "status", "error_message"]
                ].rename(
                    columns={
                        "list_id": "List ID",
                        "list_name": "List name",
                        "submitted_by": "Submitted by",
                        "status": "Status",
                        "error_message": "Error",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )


def main():
    render_header()
    render_webhook_status()
    st.divider()
    render_format_section()
    st.divider()
    render_upload_section()
    st.divider()
    render_history_section()


if __name__ == "__main__":
    main()
