"""List Enrichment Dropbox — Streamlit UI."""
import hashlib
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from clay_client import get_webhook_url, send_rows_to_clay
from config import (
    APP_TITLE,
    LARGE_LIST_THRESHOLD,
    NAME_HEADERS,
    OPTIONAL_HEADERS,
    REQUIRED_HEADERS,
)
from list_id_store import clear_history, next_list_id, recent_submissions, record_submission
from validator import validate_upload

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
    /* Notice banner */
    .notice {
        padding: 14px 18px;
        background: #fff8e6;
        border-left: 4px solid #f0a83d;
        border-radius: 6px;
        color: #7a4c0b;
        font-size: 0.93rem;
        margin: 6px 0 18px 0;
        line-height: 1.5;
    }
    .notice b { color: #5a3a08; }
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
    .chip-name {
        background: #fff4dc;
        color: #7a4c0b;
        border: 1px solid #f4dca0;
    }
    /* Validation error block */
    .csv-error {
        padding: 16px 18px;
        background: #fff1f1;
        border-left: 4px solid #d6394d;
        border-radius: 6px;
        color: #5b1018;
        margin: 12px 0 8px 0;
    }
    .csv-error h4 {
        margin: 0 0 8px 0;
        color: #8a1424;
        font-size: 1.02rem;
    }
    .csv-error ul { margin: 4px 0 0 20px; padding: 0; }
    .csv-error li { margin: 2px 0; }
    .csv-error code {
        background: #ffe3e3;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 0.88em;
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


def render_notice():
    st.markdown(
        '<div class="notice">'
        "<b>Heads up before you upload:</b><br>"
        "Contacts you submit go through Clay enrichment and qualification. "
        "<b>Not every contact will make it through.</b> Some may be filtered out, "
        "deduped, or removed if they don't meet our criteria. "
        "<b>Ownership won't always land with you.</b> Existing contact or company owners "
        "in HubSpot won't be overwritten, so some records will stay with their current owner. "
        "Thanks for understanding!"
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
        st.image(str(FORMAT_IMAGE), width=470)

    chips_required = "".join(f'<span class="chip">{h}</span>' for h in REQUIRED_HEADERS)
    chips_name = "".join(f'<span class="chip chip-name">{h}</span>' for h in NAME_HEADERS)
    chips_optional = "".join(f'<span class="chip chip-opt">{h}</span>' for h in OPTIONAL_HEADERS)
    st.markdown("**Required columns**", unsafe_allow_html=True)
    st.markdown(chips_required, unsafe_allow_html=True)
    st.caption(
        "`Company Domain Name` also accepts these headers: "
        "**Domain**, **Website**, **Company Website**, **URL**."
    )
    st.markdown(
        "**Name columns** — include either **Full Name** OR both "
        "**First Name** and **Last Name** per row",
        unsafe_allow_html=True,
    )
    st.markdown(chips_name, unsafe_allow_html=True)
    st.markdown("**Optional columns**", unsafe_allow_html=True)
    st.markdown(chips_optional, unsafe_allow_html=True)

    if SAMPLE_CSV.exists():
        st.download_button(
            label="Download sample CSV",
            data=SAMPLE_CSV.read_bytes(),
            file_name="list_enrichment_template.csv",
            mime="text/csv",
        )


def _file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()[:10]


def render_approval_gate(file_bytes: bytes, row_count: int) -> bool:
    """Show admin approval UI for large lists. Returns True when approved."""
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    fh = _file_hash(file_bytes)
    key_approved = f"large_approved_{fh}"

    if st.session_state.get(key_approved):
        st.success(
            f"Admin approved — sending **{row_count:,}** rows "
            f"(over the {LARGE_LIST_THRESHOLD:,} threshold)."
        )
        return True

    st.markdown(
        f'<div class="notice">'
        f"<b>Large list — admin approval required</b><br>"
        f"This list has <b>{row_count:,}</b> rows, which is over the "
        f"<b>{LARGE_LIST_THRESHOLD:,}</b> threshold. An admin must approve "
        f"before it can be sent to Clay."
        f"</div>",
        unsafe_allow_html=True,
    )

    if not admin_password:
        st.error(
            "Admin password is not configured on the server. Set "
            "`ADMIN_PASSWORD` in Streamlit Secrets to allow approvals."
        )
        return False

    col_a, col_b = st.columns([2, 1])
    with col_a:
        pw = st.text_input(
            "Admin password",
            type="password",
            key=f"approval_pw_{fh}",
            placeholder="Have an admin enter the password",
        )
    with col_b:
        st.write("")
        st.write("")
        if st.button("Approve list", key=f"approve_btn_{fh}", type="primary"):
            if pw == admin_password:
                st.session_state[key_approved] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


def render_validation_errors(result) -> None:
    def _li(items: list[str]) -> str:
        return "".join(f"<li>{i}</li>" for i in items)

    sections = []
    if result.column_errors:
        sections.append(
            "<h4>Column issues</h4><ul>" + _li(result.column_errors) + "</ul>"
        )
    if result.row_errors:
        sections.append(
            "<h4>Row issues</h4><ul>" + _li(result.row_errors) + "</ul>"
        )
    body = "".join(sections) or "<p>Your file is not in the required format.</p>"

    st.markdown(
        f'<div class="csv-error">'
        f"<h4>Your CSV is not in the required format</h4>"
        f"<p>Fix the issues below and re-upload. Download the sample CSV "
        f"in the section above if it helps.</p>"
        f"{body}"
        f"</div>",
        unsafe_allow_html=True,
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
            placeholder="e.g. Steve Jobs",
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

    file_bytes = uploaded.getvalue()
    result = validate_upload(file_bytes)

    if not result.is_valid:
        render_validation_errors(result)
        return

    df = result.df
    assert df is not None
    st.success(f"Valid CSV — **{len(df)}** rows ready.")
    with st.expander("Preview (first 5 rows)"):
        st.dataframe(df.head(), use_container_width=True, hide_index=True)

    if len(df) > LARGE_LIST_THRESHOLD:
        if not render_approval_gate(file_bytes, len(df)):
            return

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
    try:
        local = df["created_at"].dt.tz_convert("US/Pacific")
        df["Submitted"] = local.dt.strftime("%Y-%m-%d %I:%M %p") + " PT"
    except Exception:
        df["Submitted"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M") + " UTC"
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

    render_admin_section()


def render_admin_section() -> None:
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        return  # not configured -> hide admin entirely

    with st.expander("Admin: Clear submission history"):
        st.caption(
            "Wipes the submissions table and resets the list ID counter back "
            "to 000001. This can't be undone."
        )
        if not st.session_state.get("admin_unlocked"):
            pw = st.text_input(
                "Admin password",
                type="password",
                key="admin_pw_input",
                placeholder="Enter password to enable clear",
            )
            if st.button("Unlock"):
                if pw == admin_password:
                    st.session_state["admin_unlocked"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            return

        st.success("Admin unlocked for this session.")
        confirm = st.checkbox(
            "I understand this deletes all submission history.",
            key="confirm_clear",
        )
        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("Clear all submissions", disabled=not confirm, type="primary"):
                removed = clear_history(reset_counter=True)
                st.success(
                    f"Cleared {removed} submission(s). Next list ID will be 000001."
                )
                st.session_state["admin_unlocked"] = False
                st.rerun()
        with col_b:
            if st.button("Lock admin"):
                st.session_state["admin_unlocked"] = False
                st.rerun()


def main():
    render_header()
    render_notice()
    render_webhook_status()
    st.divider()
    render_format_section()
    st.divider()
    render_upload_section()
    st.divider()
    render_history_section()


if __name__ == "__main__":
    main()
