import streamlit as st

from config import keys_configured
from csv_updater import update_influencer_csv

st.set_page_config(
    page_title="Influencer Tracker Updater",
    page_icon="📊",
    layout="centered",
)

st.title("Influencer Tracker Updater")
st.markdown(
    "Upload your influencer CSV, refresh **views & engagement** automatically, "
    "then download the updated file."
)

if not keys_configured():
    st.error(
        "API keys are not configured on the server. "
        "The site owner needs to add `YOUTUBE_API_KEY` and `APIFY_TOKEN` "
        "in the hosting dashboard."
    )
    st.stop()

with st.sidebar:
    st.header("Options")
    update_youtube = st.checkbox("Update YouTube rows", value=True)
    update_instagram = st.checkbox("Update Instagram rows", value=True)
    st.divider()
    st.caption(
        "YouTube uses the YouTube Data API. "
        "Instagram uses Apify scraping in batches of 20."
    )

uploaded = st.file_uploader(
    "Choose your CSV file",
    type=["csv"],
    help="Use the same format as your Influencer tracker sheet export.",
)

if uploaded is not None:
    st.success(f"Loaded **{uploaded.name}** ({uploaded.size:,} bytes)")

    if st.button("Update CSV", type="primary", use_container_width=True):
        if not update_youtube and not update_instagram:
            st.error("Select at least one platform to update.")
        else:
            progress_bar = st.progress(0, text="Starting…")
            status = st.empty()
            log = st.empty()

            def on_progress(kind, *args):
                if kind == "phase":
                    status.info(args[0])
                    return

                platform, current, total, message = kind, *args
                pct = min(current / max(total, 1), 1.0)
                progress_bar.progress(
                    pct,
                    text=f"{platform.title()}: {current}/{total}",
                )
                log.caption(message)

            try:
                with st.spinner("Fetching latest stats — this may take a few minutes…"):
                    result_bytes, stats = update_influencer_csv(
                        uploaded.getvalue(),
                        update_instagram=update_instagram,
                        update_youtube=update_youtube,
                        progress_callback=on_progress,
                    )

                progress_bar.progress(1.0, text="Done!")
                status.empty()

                base_name = uploaded.name.rsplit(".", 1)[0]
                output_name = f"{base_name}_updated.csv"

                st.session_state["updated_csv"] = result_bytes
                st.session_state["output_name"] = output_name
                st.session_state["stats"] = stats

            except Exception as exc:
                progress_bar.empty()
                st.error(f"Something went wrong: {exc}")

if "updated_csv" in st.session_state:
    stats = st.session_state["stats"]
    st.divider()
    st.subheader("Update complete")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total rows", stats["total_rows"])
    col2.metric("YouTube updated", stats["youtube_updated"])
    col3.metric("Instagram updated", stats["instagram_updated"])

    st.download_button(
        label="Download updated CSV",
        data=st.session_state["updated_csv"],
        file_name=st.session_state["output_name"],
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )

st.divider()
with st.expander("How to use"):
    st.markdown(
        """
1. **Upload** your CSV file.
2. Click **Update CSV** and wait for it to finish (large files may take several minutes).
3. Click **Download updated CSV**.

**What gets updated**
- **Instagram** rows: Video Views, Likes, Comments, Engagement
- **YouTube** rows: Video Views, Total Views, Likes, Comments, Engagement, Actual ER%, Actual CPV, Average Views, Target CPV, Status

Rows without a post link are skipped for Instagram. YouTube rows without a live post still get average views from the channel profile when possible.
        """
    )
