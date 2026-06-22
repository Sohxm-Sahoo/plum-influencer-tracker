import time

import pandas as pd
from apify_client import ApifyClient

from config import INSTAGRAM_BATCH_SIZE, get_apify_token

URL_COL = "Post Link  (Main Asset)"
VIEWS_COL = "Video Views"
LIKES_COL = "Likes"
COMMENTS_COL = "Comments"
ENGAGEMENT_COL = "Engagement"

METRIC_COLS = [VIEWS_COL, LIKES_COL, COMMENTS_COL, ENGAGEMENT_COL]


def normalize_url(url):
    return str(url).split("?")[0].rstrip("/").lower()


def is_instagram_row(row):
    url = str(row.get(URL_COL, "")).strip().lower()
    platform = str(row.get("Platform", "")).strip().upper()

    if "instagram.com" in url:
        return True

    return platform in ("IG", "INSTAGRAM", "INSTA")


def prepare_instagram_columns(df):
    for col in METRIC_COLS:
        if col not in df.columns:
            df[col] = ""

        df[col] = df[col].astype(object)

    return df


def update_instagram_rows(df, progress_callback=None):
    df = prepare_instagram_columns(df)

    token = get_apify_token()
    if not token:
        raise Exception("APIFY_TOKEN not configured")

    client = ApifyClient(token)

    instagram_rows = []

    for idx, row in df.iterrows():
        url = str(row.get(URL_COL, "")).strip()

        if not url or url.lower() in ("nan", "none"):
            continue

        if not is_instagram_row(row):
            continue

        instagram_rows.append((idx, normalize_url(url)))

    if not instagram_rows:
        return df, 0

    total_batches = max(
        1,
        (len(instagram_rows) + INSTAGRAM_BATCH_SIZE - 1)
        // INSTAGRAM_BATCH_SIZE,
    )

    updated = 0

    for batch_num, start in enumerate(
        range(0, len(instagram_rows), INSTAGRAM_BATCH_SIZE),
        start=1,
    ):
        batch = instagram_rows[
            start : start + INSTAGRAM_BATCH_SIZE
        ]

        urls = [url for _, url in batch]

        if progress_callback:
            progress_callback(
                batch_num,
                total_batches,
                f"Instagram batch {batch_num}/{total_batches} ({len(urls)} posts)",
            )

        try:
            run = client.actor(
                "apify/instagram-scraper"
            ).call(
                run_input={
                    "directUrls": urls,
                    "resultsLimit": len(urls),
                }
            )

            items = list(
                client.dataset(
                    run["defaultDatasetId"]
                ).iterate_items()
            )

        except Exception as exc:
            print(f"Instagram batch failed: {exc}")
            continue

        results = {}

        for item in items:
            try:
                source_url = normalize_url(
                    item.get("inputUrl")
                    or item.get("url")
                    or item.get("postUrl")
                    or item.get("displayUrl")
                    or ""
                )

                likes = int(item.get("likesCount") or 0)
                comments = int(item.get("commentsCount") or 0)

                views = int(
                    item.get("videoViewCount")
                    or item.get("videoPlayCount")
                    or item.get("video_view_count")
                    or 0
                )

                if source_url:
                    results[source_url] = {
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "engagement": likes + comments,
                    }

            except Exception:
                continue

        for idx, url in batch:

            matched_url = None

            if url in results:
                matched_url = url
            else:
                for result_url in results.keys():
                    if url in result_url or result_url in url:
                        matched_url = result_url
                        break

            if not matched_url:
                continue

            r = results[matched_url]

            df.at[idx, VIEWS_COL] = r["views"]
            df.at[idx, LIKES_COL] = r["likes"]
            df.at[idx, COMMENTS_COL] = r["comments"]
            df.at[idx, ENGAGEMENT_COL] = r["engagement"]

            updated += 1

        if start + INSTAGRAM_BATCH_SIZE < len(instagram_rows):
            time.sleep(2)

    return df, updated
