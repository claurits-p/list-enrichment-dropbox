"""List Enrichment Dropbox — Streamlit UI."""
import hashlib
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from clay_client import get_webhook_url, send_rows_to_clay, webhook_env_name
from config import (
    APP_TITLE,
    DOMAIN_DISPLAY_HEADER,
    LIST_TYPE_COMPANY,
    LIST_TYPE_CONTACTS,
    LIST_TYPES,
    name_headers_for,
    optional_headers_for,
    required_headers_for,
    threshold_for,
)
from list_id_store import (
    add_to_approval_queue,
    clear_history,
    delete_pending_approval,
    get_pending_approval,
    list_pending_approvals,
    next_list_id,
    recent_submissions,
    record_submission,
)
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
    /* Post-submission info block */
    .next-steps {
        padding: 16px 18px;
        background: #eaf3ff;
        border-left: 4px solid #1B6AC9;
        border-radius: 6px;
        color: #0a3573;
        margin: 12px 0 4px 0;
        line-height: 1.55;
        font-size: 0.95rem;
    }
    .next-steps b { color: #082858; }
    .next-steps .eyebrow {
        display: block;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #1B6AC9;
        margin-bottom: 6px;
    }
    </style>""",
    unsafe_allow_html=True,
)

ASSETS = Path(__file__).parent / "assets"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def format_image_for(list_type: str) -> Path:
    if list_type == LIST_TYPE_COMPANY:
        return ASSETS / "format_guide_company.png"
    return ASSETS / "format_guide_contacts.png"


def sample_csv_for(list_type: str) -> Path:
    if list_type == LIST_TYPE_COMPANY:
        return ASSETS / "sample_template_company.csv"
    return ASSETS / "sample_template_contacts.csv"


def chips_for(list_type: str) -> tuple[list[str], list[str], list[str]]:
    """Return (required_chips, name_chips, optional_chips) for display.

    The domain column is shown as the friendlier "Website" label everywhere
    (canonical internal name stays "Company Domain Name").
    """
    required = [
        DOMAIN_DISPLAY_HEADER if h == "Company Domain Name" else h
        for h in required_headers_for(list_type)
    ]
    return required, name_headers_for(list_type), optional_headers_for(list_type)


def render_header():
    import base64
    logo_path = Path(__file__).parent / "paystand_logo.png"
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode() if logo_path.exists() else ""
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:14px; margin: 0 0 4px 0;">
            <img src="data:image/png;base64,{logo_b64}" width="52" height="52"
                 style="display:block; border-radius:12px;" />
            <h1 style="color:#001F5B; margin:0; padding:0; line-height:1.1;
                       font-size:2.4rem; font-weight:700;">{APP_TITLE}</h1>
        </div>
        <div class="section-sub" style="margin-top:0;">
            Upload a CSV of contacts or target accounts. Rows are sent to Clay for enrichment.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_notice():
    contact_threshold = threshold_for(LIST_TYPE_CONTACTS)
    company_threshold = threshold_for(LIST_TYPE_COMPANY)
    st.markdown(
        '<div class="notice">'
        "<b>Heads up before you upload:</b><br>"
        "Rows you submit go through Clay enrichment and qualification. "
        "<b>Not every row will make it through.</b> Some may be filtered out, "
        "deduped, or removed if they don't meet our criteria. "
        "<b>Ownership won't always land with you.</b> Existing contact or company owners "
        "in HubSpot won't be overwritten, so some records will stay with their current owner.<br>"
        f"<b>Contact lists over {contact_threshold:,} rows and company lists over "
        f"{company_threshold:,} rows need admin approval.</b> Company lists fan out via "
        "ZoomInfo's Find Contacts, so each company can become many contacts — that's why "
        "the threshold is lower. Larger lists go into the approval queue and Kit or "
        "Marcelo will release them. Thanks for understanding!"
        "</div>",
        unsafe_allow_html=True,
    )


def render_webhook_status(list_type: str):
    if get_webhook_url(list_type):
        st.markdown(
            f'<span class="status-pill status-ok">Clay webhook configured '
            f'({list_type})</span>',
            unsafe_allow_html=True,
        )
    else:
        env_name = webhook_env_name(list_type)
        st.markdown(
            f'<span class="status-pill status-warn">Clay webhook not configured '
            f'({list_type})</span>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Add `{env_name}` to Streamlit Secrets (or `.env` locally) "
            f"before {list_type.lower()} list submissions can be sent."
        )


def render_format_section(list_type: str):
    is_company = list_type == LIST_TYPE_COMPANY
    label_for = "Company list" if is_company else "Contact list"
    st.subheader(f"Required CSV format — {label_for}")
    st.markdown(
        '<div class="section-sub">'
        "Headers must match exactly. Required fields cannot be blank. "
        "Switch the <b>List type</b> above to see the other format."
        "</div>",
        unsafe_allow_html=True,
    )

    format_image = format_image_for(list_type)
    if format_image.exists():
        st.image(str(format_image), width=540)

    chips_required, chips_name, chips_optional = chips_for(list_type)

    st.markdown("**Required columns**", unsafe_allow_html=True)
    st.markdown(
        "".join(f'<span class="chip">{h}</span>' for h in chips_required),
        unsafe_allow_html=True,
    )

    st.caption(
        f"**{DOMAIN_DISPLAY_HEADER}** also accepts these headers: "
        "**Company Domain Name**, **Domain**, **Company Website**, **URL**. "
        "Bare domains, full URLs, and `www.` prefixes all work — "
        "they're normalized on the Clay side."
    )

    if chips_name:
        st.markdown(
            "**Name columns** — include either **Full Name** OR both "
            "**First Name** and **Last Name** per row",
            unsafe_allow_html=True,
        )
        st.markdown(
            "".join(f'<span class="chip chip-name">{h}</span>' for h in chips_name),
            unsafe_allow_html=True,
        )

    st.markdown("**Optional columns**", unsafe_allow_html=True)
    st.markdown(
        "".join(f'<span class="chip chip-opt">{h}</span>' for h in chips_optional),
        unsafe_allow_html=True,
    )

    sample_csv = sample_csv_for(list_type)
    if sample_csv.exists():
        st.download_button(
            label=f"Download sample {label_for.lower()} CSV",
            data=sample_csv.read_bytes(),
            file_name=sample_csv.name,
            mime="text/csv",
        )


def _file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()[:10]


def _is_valid_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s))


def render_next_steps(
    list_type: str, list_name: str, identifier: str, row_count: int, *, queued: bool
) -> None:
    fan_out_line = ""
    if list_type == LIST_TYPE_COMPANY:
        est_low = row_count * 5
        est_high = row_count * 15
        fan_out_line = (
            f"<br><b>Expected fan-out:</b> ~{est_low:,}–{est_high:,} contacts after "
            "ZoomInfo's Find Contacts step (varies by titles found per company)."
        )

    if queued:
        first_line = (
            f"Your list <b>“{list_name}”</b> ({identifier}) is in the approval queue. "
            "Once <b>Kit</b> or <b>Marcelo</b> approves it, enrichment in Clay will start."
        )
    else:
        first_line = (
            f"Your list <b>“{list_name}”</b> ({identifier}) is now being enriched in Clay."
        )

    st.markdown(
        f'<div class="next-steps">'
        f'<span class="eyebrow">What to expect next</span>'
        f"{first_line}{fan_out_line}<br><br>"
        "<b>Expect 24–48 hours</b> for enrichment to finish, depending on current backlog.<br>"
        "When it's complete, <b>reach out to Kit or Marcelo</b> so they can review the "
        "enriched list and import it into HubSpot.<br><br>"
        "Thanks for using the dropbox!"
        "</div>",
        unsafe_allow_html=True,
    )


def summarize_record_types(df) -> str:
    """Build a compact 'Prospect: 45, Partner: 10' summary from a validated df."""
    if "Record Type" not in df.columns:
        return ""
    counts = df["Record Type"].value_counts().to_dict()
    if not counts:
        return ""
    parts = [f"{rt}: {n}" for rt, n in counts.items()]
    return ", ".join(parts)


def render_queue_submit(
    list_type: str,
    file_bytes: bytes,
    df,
    submitted_by: str,
    submitted_by_email: str,
    submission_list_name: str,
    filename: str,
) -> bool:
    """Show large-list queue submit. Returns True when row was queued this run."""
    row_count = len(df)
    threshold = threshold_for(list_type)
    fh = _file_hash(file_bytes)
    queued_flag = f"queued_{fh}"

    if st.session_state.get(queued_flag):
        queue_id = st.session_state.get(f"queued_id_{fh}")
        st.success(
            f"Queued for approval (queue #{queue_id}). "
            f"Reach out to **Kit** or **Marcelo** so they can approve it."
        )
        render_next_steps(
            list_type, submission_list_name, f"queue #{queue_id}", row_count,
            queued=True,
        )
        return True

    type_label = "company" if list_type == LIST_TYPE_COMPANY else "contact"
    st.markdown(
        f'<div class="notice">'
        f"<b>Large list — over the {threshold:,} {type_label}-row limit</b><br>"
        f"This list has <b>{row_count:,}</b> rows. Lists this big can't be sent "
        f"straight to Clay — they go into an approval queue first.<br><br>"
        f"<b>Reach out to Kit or Marcelo</b> to approve the list enrichment. "
        f"They can log in, enter the admin password, and approve it from the "
        f"<i>Pending approvals</i> section."
        f"</div>",
        unsafe_allow_html=True,
    )

    if st.button("Submit to approval queue", type="primary", use_container_width=True):
        queue_id = add_to_approval_queue(
            submitted_by=submitted_by,
            submitted_by_email=submitted_by_email,
            list_name=submission_list_name,
            list_type=list_type,
            row_count=row_count,
            filename=filename,
            csv_bytes=file_bytes,
            record_type=summarize_record_types(df),
        )
        st.session_state[queued_flag] = True
        st.session_state[f"queued_id_{fh}"] = queue_id
        st.rerun()

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


def render_list_type_picker() -> str:
    st.subheader("List type")
    st.markdown(
        '<div class="section-sub">'
        "Choose what kind of list you're uploading. This drives the required "
        "columns and where the data gets sent in Clay."
        "</div>",
        unsafe_allow_html=True,
    )
    list_type = st.radio(
        "List type",
        options=list(LIST_TYPES),
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="list_type_choice",
    )
    if list_type == LIST_TYPE_COMPANY:
        st.caption(
            "Company list — provides target accounts only. ZoomInfo's Find "
            "Contacts will discover contacts at each account."
        )
    else:
        st.caption(
            "Contact list — provides specific people to enrich. The standard flow."
        )
    return list_type


def render_upload_section(list_type: str):
    st.subheader("Upload list")
    st.markdown(
        '<div class="section-sub">'
        "Tell us who you are and name the list, then drop the CSV."
        "</div>",
        unsafe_allow_html=True,
    )

    name_col, email_col, list_col = st.columns(3)
    with name_col:
        submitted_by = st.text_input(
            "Your name *",
            placeholder="e.g. Steve Jobs",
            help="So we know who submitted this list.",
        ).strip()
    with email_col:
        submitted_by_email = st.text_input(
            "Your email *",
            placeholder="e.g. steve@paystand.com",
            help="We'll attach this to the submission for follow-up.",
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
    if not submitted_by_email:
        missing_meta.append("Your email")
    elif not _is_valid_email(submitted_by_email):
        missing_meta.append("a valid email")
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
        key=f"uploader_{list_type}",
    )
    if uploaded is None:
        return

    file_bytes = uploaded.getvalue()
    result = validate_upload(file_bytes, list_type=list_type)

    if not result.is_valid:
        render_validation_errors(result)
        return

    df = result.df
    assert df is not None
    type_label = "companies" if list_type == LIST_TYPE_COMPANY else "contacts"
    st.success(f"Valid CSV — **{len(df)}** {type_label} ready.")
    with st.expander("Preview (first 5 rows)"):
        st.dataframe(df.head(), use_container_width=True, hide_index=True)

    threshold = threshold_for(list_type)
    if len(df) > threshold:
        render_queue_submit(
            list_type,
            file_bytes,
            df,
            submitted_by,
            submitted_by_email,
            submission_list_name,
            uploaded.name,
        )
        return

    webhook_set = bool(get_webhook_url(list_type))
    submit = st.button(
        f"Send to Clay ({list_type})",
        type="primary",
        disabled=not webhook_set,
        use_container_width=True,
    )

    if not submit:
        return

    list_id = next_list_id()
    filename = uploaded.name
    record_type_summary = summarize_record_types(df)
    with st.spinner(f"Sending list **{list_id}** ({len(df)} rows)…"):
        sent, errors = send_rows_to_clay(
            df,
            list_id,
            list_type=list_type,
            submitted_by=submitted_by,
            submitted_by_email=submitted_by_email,
            submission_list_name=submission_list_name,
        )

    if sent == len(df):
        record_submission(
            list_id, len(df), filename, "sent",
            list_name=submission_list_name,
            submitted_by=submitted_by,
            submitted_by_email=submitted_by_email,
            list_type=list_type,
            record_type=record_type_summary,
        )
        st.success(
            f"**List {list_id} — “{submission_list_name}”** — all **{sent}** "
            f"rows sent to Clay for enrichment ({record_type_summary})."
        )
        render_next_steps(
            list_type, submission_list_name, list_id, len(df), queued=False,
        )
    elif sent > 0:
        msg = "; ".join(errors[:5])
        record_submission(
            list_id, len(df), filename, "partial",
            list_name=submission_list_name,
            submitted_by=submitted_by,
            submitted_by_email=submitted_by_email,
            list_type=list_type,
            record_type=record_type_summary,
            error_message=msg,
        )
        st.warning(f"**List {list_id}** — sent **{sent}/{len(df)}** rows. Some failed.")
        for err in errors:
            st.markdown(f"- {err}")
    else:
        msg = "; ".join(errors[:5])
        record_submission(
            list_id, len(df), filename, "failed",
            list_name=submission_list_name,
            submitted_by=submitted_by,
            submitted_by_email=submitted_by_email,
            list_type=list_type,
            record_type=record_type_summary,
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
        render_admin_section()
        return

    df = pd.DataFrame(recent)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    try:
        local = df["created_at"].dt.tz_convert("US/Pacific")
        df["Submitted"] = local.dt.strftime("%Y-%m-%d %I:%M %p") + " PT"
    except Exception:
        df["Submitted"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M") + " UTC"

    if "list_type" not in df.columns:
        df["list_type"] = ""
    df["list_type"] = df["list_type"].fillna("").replace("", LIST_TYPE_CONTACTS)
    if "submitted_by_email" not in df.columns:
        df["submitted_by_email"] = ""

    display = df.rename(
        columns={
            "list_id": "List ID",
            "list_name": "List name",
            "list_type": "List type",
            "submitted_by": "Submitted by",
            "submitted_by_email": "Email",
            "record_type": "Record type",
            "row_count": "Rows",
            "status": "Status",
        }
    )[
        ["List ID", "List name", "List type", "Record type", "Submitted by",
         "Email", "Rows", "Status", "Submitted"]
    ]

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
        return

    pending_count = len(list_pending_approvals())
    expander_label = "Admin"
    if pending_count > 0:
        expander_label = f"Admin — {pending_count} pending approval(s)"

    with st.expander(expander_label):
        if not st.session_state.get("admin_unlocked"):
            st.caption(
                "Admin can approve large list uploads in the approval queue and "
                "clear submission history. Enter the admin password to unlock."
            )
            if pending_count:
                st.info(f"There are **{pending_count}** list(s) waiting for approval.")
            pw = st.text_input(
                "Admin password",
                type="password",
                key="admin_pw_input",
                placeholder="Enter password to unlock admin",
            )
            if st.button("Unlock"):
                if pw == admin_password:
                    st.session_state["admin_unlocked"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            return

        st.success("Admin unlocked for this session.")
        if st.button("Lock admin"):
            st.session_state["admin_unlocked"] = False
            st.rerun()

        st.markdown("---")
        render_pending_approvals_panel()

        st.markdown("---")
        render_clear_history_panel()


def render_pending_approvals_panel() -> None:
    st.markdown("#### Pending approvals")
    pending = list_pending_approvals()
    if not pending:
        st.caption("No lists waiting for approval.")
        return

    for item in pending:
        qid = item["queue_id"]
        with st.container(border=True):
            cols = st.columns([2, 2, 1, 2])
            cols[0].markdown(f"**{item['list_name']}**")
            list_type_label = item.get("list_type") or LIST_TYPE_CONTACTS
            cols[0].caption(
                f"by {item['submitted_by']} · {list_type_label} · "
                f"{item.get('record_type') or '—'}"
            )
            cols[1].markdown(f"`{item['filename']}`")
            cols[1].caption(item["submitted_at"][:19].replace("T", " ") + " UTC")
            cols[2].metric("Rows", f"{item['row_count']:,}")
            with cols[3]:
                if st.button("Approve & send", key=f"approve_{qid}", type="primary"):
                    approve_pending(qid)
                if st.button("Decline", key=f"decline_open_{qid}"):
                    st.session_state[f"confirm_decline_{qid}"] = True
                    st.rerun()

            if st.session_state.get(f"confirm_decline_{qid}"):
                st.markdown("")
                st.warning(
                    f"**Decline this list?**  "
                    f"`{item['list_name']}` from {item['submitted_by']} "
                    f"will be permanently deleted from the queue."
                )
                reason = st.text_input(
                    "Reason (optional, shown nowhere yet but good record):",
                    key=f"decline_reason_{qid}",
                    placeholder="e.g. wrong format / out-of-ICP / duplicates",
                )
                d_cols = st.columns([1, 1, 4])
                with d_cols[0]:
                    if st.button(
                        "Yes, decline",
                        key=f"decline_confirm_{qid}",
                        type="primary",
                    ):
                        delete_pending_approval(qid)
                        msg = (
                            f"Declined and deleted **{item['list_name']}** "
                            f"(queue #{qid})."
                        )
                        if reason:
                            msg += f" Reason: _{reason}_"
                        st.session_state.pop(f"confirm_decline_{qid}", None)
                        st.session_state.pop(f"decline_reason_{qid}", None)
                        st.warning(msg)
                        st.rerun()
                with d_cols[1]:
                    if st.button("Cancel", key=f"decline_cancel_{qid}"):
                        st.session_state.pop(f"confirm_decline_{qid}", None)
                        st.session_state.pop(f"decline_reason_{qid}", None)
                        st.rerun()


def approve_pending(queue_id: int) -> None:
    item = get_pending_approval(queue_id)
    if not item:
        st.error("Queue item not found.")
        return

    list_type = item.get("list_type") or LIST_TYPE_CONTACTS
    result = validate_upload(item["csv_bytes"], list_type=list_type)
    if not result.is_valid:
        st.error("Stored CSV failed re-validation. Ask the submitter to re-upload.")
        render_validation_errors(result)
        return

    df = result.df
    assert df is not None
    list_id = next_list_id()
    record_type_summary = summarize_record_types(df) or (item.get("record_type") or "")
    submitter_email = item.get("submitted_by_email") or ""

    with st.spinner(
        f"Approving and sending **{item['list_name']}** "
        f"({len(df):,} rows) as list {list_id}…"
    ):
        sent, errors = send_rows_to_clay(
            df,
            list_id,
            list_type=list_type,
            submitted_by=item["submitted_by"],
            submitted_by_email=submitter_email,
            submission_list_name=item["list_name"],
        )

    status = "sent" if sent == len(df) else ("partial" if sent > 0 else "failed")
    record_submission(
        list_id,
        len(df),
        item["filename"],
        status,
        list_name=item["list_name"],
        submitted_by=item["submitted_by"],
        submitted_by_email=submitter_email,
        list_type=list_type,
        record_type=record_type_summary,
        error_message="; ".join(errors[:5]) if errors else None,
    )
    delete_pending_approval(queue_id)

    if status == "sent":
        st.success(
            f"Approved and sent **{item['list_name']}** as list **{list_id}** "
            f"({sent:,} rows)."
        )
    else:
        st.warning(
            f"List **{list_id}** — sent **{sent}/{len(df)}** rows. Some failed."
        )
        for err in errors:
            st.markdown(f"- {err}")
    st.rerun()


def render_clear_history_panel() -> None:
    st.markdown("#### Clear submission history")
    st.caption(
        "Wipes the submissions table and resets the list ID counter back "
        "to 000001. This can't be undone."
    )
    confirm = st.checkbox(
        "I understand this deletes all submission history.",
        key="confirm_clear",
    )
    if st.button("Clear all submissions", disabled=not confirm, type="primary"):
        removed = clear_history(reset_counter=True)
        st.success(
            f"Cleared {removed} submission(s). Next list ID will be 000001."
        )
        st.rerun()


def main():
    render_header()
    render_notice()
    list_type = render_list_type_picker()
    render_webhook_status(list_type)
    st.divider()
    render_format_section(list_type)
    st.divider()
    render_upload_section(list_type)
    st.divider()
    render_history_section()


if __name__ == "__main__":
    main()
