import io
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from clay_client import get_webhook_url, send_rows_to_clay
from config import ALL_HEADERS, APP_TITLE, OPTIONAL_HEADERS, REQUIRED_HEADERS
from list_id_store import next_list_id, recent_submissions, record_submission
from validator import normalize_columns, validate_rows

load_dotenv()

ASSETS = Path(__file__).parent / "assets"
FORMAT_IMAGE = ASSETS / "format_guide.png"
SAMPLE_CSV = ASSETS / "sample_template.csv"


st.set_page_config(page_title=APP_TITLE, page_icon="📋", layout="centered")

st.title(APP_TITLE)
st.caption("Upload a CSV in the required format. Rows are sent to Clay for enrichment.")

# --- Format guide ---
st.subheader("Required CSV format")
if FORMAT_IMAGE.exists():
    st.image(str(FORMAT_IMAGE), use_container_width=True)
else:
    st.info("Format image missing — see column list below.")

req = ", ".join(f"**{h}**" for h in REQUIRED_HEADERS)
opt = ", ".join(f"*{h}*" for h in OPTIONAL_HEADERS)
st.markdown(f"**Required:** {req}")
st.markdown(f"**Optional:** {opt}")

if SAMPLE_CSV.exists():
    st.download_button(
        label="Download sample CSV",
        data=SAMPLE_CSV.read_bytes(),
        file_name="list_enrichment_template.csv",
        mime="text/csv",
    )

st.divider()

# --- Webhook status ---
webhook_set = bool(get_webhook_url())
if webhook_set:
    st.success("Clay webhook configured.")
else:
    st.warning(
        "Clay webhook not configured yet. Add `CLAY_WEBHOOK_URL` to `.env` before submitting."
    )

# --- Upload ---
uploaded = st.file_uploader("Drop your CSV here", type=["csv"])

if uploaded is not None:
    try:
        raw_df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()

    if raw_df.empty:
        st.error("CSV has no data rows.")
        st.stop()

    df, col_errors = normalize_columns(raw_df)
    if col_errors:
        st.error("Column problems:")
        for err in col_errors:
            st.markdown(f"- {err}")
        st.stop()

    row_errors = validate_rows(df)
    if row_errors:
        st.error("Row problems:")
        for err in row_errors:
            st.markdown(f"- {err}")
        st.stop()

    st.success(f"Valid CSV — **{len(df)}** rows ready.")
    with st.expander("Preview (first 5 rows)"):
        st.dataframe(df.head(), use_container_width=True)

    submit = st.button("Send to Clay", type="primary", disabled=not webhook_set)

    if submit:
        list_id = next_list_id()
        filename = uploaded.name

        with st.spinner(f"Sending list **{list_id}** ({len(df)} rows)…"):
            sent, errors = send_rows_to_clay(df, list_id)

        if sent == len(df):
            record_submission(list_id, len(df), filename, "sent")
            st.success(
                f"**List {list_id}** — all **{sent}** rows sent to Clay for enrichment."
            )
        elif sent > 0:
            msg = "; ".join(errors[:5])
            record_submission(list_id, len(df), filename, "partial", msg)
            st.warning(
                f"**List {list_id}** — sent **{sent}/{len(df)}** rows. Some failed."
            )
            for err in errors:
                st.markdown(f"- {err}")
        else:
            msg = "; ".join(errors[:5])
            record_submission(list_id, len(df), filename, "failed", msg)
            st.error(f"**List {list_id}** — nothing sent.")
            for err in errors:
                st.markdown(f"- {err}")

st.divider()
st.subheader("Recent submissions")
recent = recent_submissions()
if not recent:
    st.caption("No submissions yet.")
else:
    st.dataframe(pd.DataFrame(recent), use_container_width=True, hide_index=True)
