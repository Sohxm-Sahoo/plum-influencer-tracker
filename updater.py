import pandas as pd
import requests
import time
from urllib.parse import urlparse, parse_qs
from apify_client import ApifyClient
import streamlit as st

# =====================================================
# CONFIG
# =====================================================

APIFY_TOKEN = st.secrets["APIFY_TOKEN"]
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]

BATCH_SIZE = 20

# =====================================================
# COLUMN NAMES
# =====================================================

URL_COL = "Post Link  (Main Asset)"

FOLLOWERS_COL = " Followers/Subs "
AVG_VIEWS_COL = "  Average Views "

VIEWS_COL = " Video Views "
LIKES_COL = " Likes "
COMMENTS_COL = " Comments "
ENGAGEMENT_COL = " Engagement "

ER_COL = "Actual ER%"
CPV_COL = "Actual CPV"

COST_COL = "Total Cost (Incl commission)"

# =====================================================
# YOUTUBE HELPERS
# =====================================================

def get_video_id(url):
    try:
        parsed = urlparse(url)

        if "youtube.com/watch" in url:
            return parse_qs(parsed.query).get("v", [None])[0]

        if "youtu.be" in url:
            return parsed.path[1:]

        if "youtube.com/shorts/" in url:
            return parsed.path.split("/")[-1]

    except:
        pass

    return None


def get_youtube_stats(video_url):

    video_id = get_video_id(video_url)

    if not video_id:
        return None

    video_api = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?id={video_id}&part=statistics,snippet"
        f"&key={YOUTUBE_API_KEY}"
    )

    data = requests.get(video_api).json()

    if not data.get("items"):
        return None

    video = data["items"][0]

    stats = video["statistics"]
    channel_id = video["snippet"]["channelId"]

    channel_api = (
        f"https://www.googleapis.com/youtube/v3/channels"
        f"?id={channel_id}&part=statistics,contentDetails"
        f"&key={YOUTUBE_API_KEY}"
    )

    channel_data = requests.get(channel_api).json()

    subscribers = 0
    uploads_playlist = None

    if channel_data.get("items"):

        item = channel_data["items"][0]

        subscribers = int(
            item["statistics"].get("subscriberCount", 0)
        )

        uploads_playlist = (
            item["contentDetails"]["relatedPlaylists"]["uploads"]
        )

    return {
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "followers": subscribers,
        "uploads_playlist": uploads_playlist
    }


def get_avg_views(playlist_id):

    if not playlist_id:
        return 0

    playlist_api = (
        f"https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=contentDetails"
        f"&playlistId={playlist_id}"
        f"&maxResults=10"
        f"&key={YOUTUBE_API_KEY}"
    )

    data = requests.get(playlist_api).json()

    ids = [
        item["contentDetails"]["videoId"]
        for item in data.get("items", [])
    ]

    if not ids:
        return 0

    videos_api = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=statistics"
        f"&id={','.join(ids)}"
        f"&key={YOUTUBE_API_KEY}"
    )

    videos = requests.get(videos_api).json()

    total_views = 0
    count = 0

    for v in videos.get("items", []):
        total_views += int(
            v["statistics"].get("viewCount", 0)
        )
        count += 1

    return round(total_views / count) if count else 0


# =====================================================
# MAIN FUNCTION
# =====================================================

def update_csv(input_csv):

    output_csv = "Influencer_V5_Updated.csv"

    df = pd.read_csv(
        input_csv,
        dtype=str,
        keep_default_na=False
    )

    required_cols = [
        FOLLOWERS_COL,
        AVG_VIEWS_COL,
        VIEWS_COL,
        LIKES_COL,
        COMMENTS_COL,
        ENGAGEMENT_COL,
        ER_COL,
        CPV_COL
    ]

    for col in required_cols:

        if col not in df.columns:
            df[col] = ""

        df[col] = df[col].astype("object")

    client = ApifyClient(APIFY_TOKEN)

    instagram_rows = []

    for idx, row in df.iterrows():

        url = str(row.get(URL_COL, "")).strip()

        if "instagram.com" in url:

            instagram_rows.append(
                (
                    idx,
                    url.split("?")[0].rstrip("/")
                )
            )

    for start in range(
        0,
        len(instagram_rows),
        BATCH_SIZE
    ):

        batch = instagram_rows[
            start:start + BATCH_SIZE
        ]

        urls = [u for _, u in batch]

        try:

            run = client.actor(
                "apify/instagram-scraper"
            ).call(
                run_input={
                    "directUrls": urls,
                    "resultsLimit": len(urls)
                }
            )

            dataset_id = run["defaultDatasetId"]

            items = list(
                client.dataset(
                    dataset_id
                ).iterate_items()
            )

            results = {}

            for item in items:

                source_url = (
                    item.get("inputUrl")
                    or item.get("url")
                    or item.get("postUrl")
                    or ""
                )

                source_url = (
                    str(source_url)
                    .split("?")[0]
                    .rstrip("/")
                )

                results[source_url] = {
                    "views": int(
                        item.get("videoPlayCount")
                        or item.get("videoViewCount")
                        or 0
                    ),
                    "likes": int(
                        item.get("likesCount")
                        or 0
                    ),
                    "comments": int(
                        item.get("commentsCount")
                        or 0
                    )
                }

            for idx, url in batch:

                if url not in results:
                    continue

                r = results[url]

                engagement = (
                    r["likes"] +
                    r["comments"]
                )

                er = round(
                    (
                        engagement /
                        r["views"]
                    ) * 100,
                    2
                ) if r["views"] > 0 else 0

                df.at[idx, VIEWS_COL] = str(
                    r["views"]
                )

                df.at[idx, LIKES_COL] = str(
                    r["likes"]
                )

                df.at[idx, COMMENTS_COL] = str(
                    r["comments"]
                )

                df.at[idx, ENGAGEMENT_COL] = str(
                    engagement
                )

                df.at[idx, ER_COL] = str(er)

                cost = pd.to_numeric(
                    df.at[idx, COST_COL],
                    errors="coerce"
                )

                if (
                    pd.notna(cost)
                    and r["views"] > 0
                ):
                    df.at[idx, CPV_COL] = str(
                        round(
                            cost /
                            r["views"],
                            4
                        )
                    )

        except Exception as e:
            print("Instagram Error:", e)

        time.sleep(2)

    # =================================================
    # YOUTUBE
    # =================================================

    for idx, row in df.iterrows():

        url = str(
            row.get(
                URL_COL,
                ""
            )
        ).strip()

        if (
            "youtube.com" not in url
            and "youtu.be" not in url
        ):
            continue

        try:

            stats = get_youtube_stats(url)

            if not stats:
                continue

            views = stats["views"]
            likes = stats["likes"]
            comments = stats["comments"]

            engagement = likes + comments

            er = round(
                (
                    engagement /
                    views
                ) * 100,
                2
            ) if views > 0 else 0

            avg_views = get_avg_views(
                stats["uploads_playlist"]
            )

            df.at[idx, FOLLOWERS_COL] = str(
                stats["followers"]
            )

            df.at[idx, AVG_VIEWS_COL] = str(
                avg_views
            )

            df.at[idx, VIEWS_COL] = str(
                views
            )

            df.at[idx, LIKES_COL] = str(
                likes
            )

            df.at[idx, COMMENTS_COL] = str(
                comments
            )

            df.at[idx, ENGAGEMENT_COL] = str(
                engagement
            )

            df.at[idx, ER_COL] = str(
                er
            )

            cost = pd.to_numeric(
                row.get(COST_COL),
                errors="coerce"
            )

            if (
                pd.notna(cost)
                and views > 0
            ):
                df.at[idx, CPV_COL] = str(
                    round(
                        cost / views,
                        4
                    )
                )

        except Exception as e:
            print(
                f"YouTube Row {idx}: {e}"
            )

    df.to_csv(
        output_csv,
        index=False,
        encoding="utf-8-sig"
    )

    return output_csv
