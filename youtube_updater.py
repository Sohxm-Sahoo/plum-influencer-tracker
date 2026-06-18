import pandas as pd
import requests
from urllib.parse import urlparse, parse_qs

from config import get_youtube_api_key

POST_LINK_COL = "Post Link  (Main Asset)"
PROFILE_LINK_COL = "Profile Link"
PLATFORM_COL = "Platform"
TOTAL_COST_COL = "Total Cost (Incl commission)"

AVG_VIEWS_COL = "Average Views"
TARGET_CPV_COL = "Target CPV"
VIDEO_VIEWS_COL = "Video Views"
TOTAL_VIEWS_COL = "Total Views"
LIKES_COL = "Likes"
COMMENTS_COL = "Comments"
ENGAGEMENT_COL = "Engagement"
ACTUAL_ER_COL = "Actual ER%"
ACTUAL_CPV_COL = "Actual CPV"
STATUS_COL = "Status"


def get_video_id(url):
    try:
        parsed = urlparse(url)
        if "watch" in url:
            return parse_qs(parsed.query).get("v", [None])[0]
        if "youtu.be" in url:
            return parsed.path.strip("/")
        if "/shorts/" in url:
            return parsed.path.split("/shorts/")[1].split("?")[0]
    except Exception:
        pass
    return None


def get_video_details(video_id):
    url = (
        "https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet,statistics,contentDetails"
        f"&id={video_id}"
        f"&key={get_youtube_api_key()}"
    )
    data = requests.get(url, timeout=30).json()
    if not data.get("items"):
        return None
    return data["items"][0]


def get_channel_data(channel_id):
    url = (
        "https://www.googleapis.com/youtube/v3/channels"
        f"?part=contentDetails"
        f"&id={channel_id}"
        f"&key={get_youtube_api_key()}"
    )
    data = requests.get(url, timeout=30).json()
    if not data.get("items"):
        return None
    return (
        data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )


def is_short(duration):
    duration = duration.upper()
    if "H" in duration or "M" in duration:
        return False
    return True


def get_average_views(playlist_id, want_shorts):
    next_page = None
    selected_views = []

    while len(selected_views) < 10:
        url = (
            "https://www.googleapis.com/youtube/v3/playlistItems"
            f"?part=contentDetails"
            f"&playlistId={playlist_id}"
            f"&maxResults=50"
            f"&key={get_youtube_api_key()}"
        )
        if next_page:
            url += f"&pageToken={next_page}"

        data = requests.get(url, timeout=30).json()
        ids = [
            item["contentDetails"]["videoId"]
            for item in data.get("items", [])
        ]
        if not ids:
            break

        stats_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=statistics,contentDetails"
            f"&id={','.join(ids)}"
            f"&key={get_youtube_api_key()}"
        )
        videos = requests.get(stats_url, timeout=30).json()

        for video in videos.get("items", []):
            duration = video["contentDetails"]["duration"]
            short_flag = is_short(duration)
            if short_flag != want_shorts:
                continue
            views = int(video["statistics"].get("viewCount", 0))
            selected_views.append(views)
            if len(selected_views) >= 10:
                break

        next_page = data.get("nextPageToken")
        if not next_page:
            break

    if not selected_views:
        return 0
    return round(sum(selected_views) / len(selected_views))


def get_channel_id_from_profile(profile_url):
    try:
        if "/@" in profile_url:
            handle = (
                profile_url.split("/@")[1].split("/")[0].split("?")[0]
            )
            url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet"
                f"&q={handle}"
                f"&type=channel"
                f"&maxResults=1"
                f"&key={get_youtube_api_key()}"
            )
            data = requests.get(url, timeout=30).json()
            if data.get("items"):
                return data["items"][0]["snippet"]["channelId"]
    except Exception:
        pass
    return None


def is_youtube_row(row):
    platform = str(row.get(PLATFORM_COL, "")).upper()
    post_link = str(row.get(POST_LINK_COL, "")).strip().lower()
    profile_link = str(row.get(PROFILE_LINK_COL, "")).strip().lower()

    if "YT" in platform or "YOUTUBE" in platform:
        return True
    for link in (post_link, profile_link):
        if any(
            token in link
            for token in ("youtube.com", "youtu.be")
        ):
            return True
    return False


def update_youtube_rows(df, progress_callback=None):
    updated = 0
    youtube_rows = [idx for idx, row in df.iterrows() if is_youtube_row(row)]
    total = len(youtube_rows)

    for count, idx in enumerate(youtube_rows, start=1):
        row = df.loc[idx]
        if progress_callback:
            progress_callback(
                count,
                total,
                f"YouTube: row {idx + 1} — {row.get('Name', 'Unknown')}",
            )

        try:
            post_link = str(row.get(POST_LINK_COL, "")).strip()
            profile_link = str(row.get(PROFILE_LINK_COL, "")).strip()
            total_cost = pd.to_numeric(
                row.get(TOTAL_COST_COL, 0),
                errors="coerce",
            )
            if pd.isna(total_cost):
                total_cost = 0

            if post_link in ("", "nan", "None"):
                channel_id = get_channel_id_from_profile(profile_link)
                if not channel_id:
                    continue
                playlist_id = get_channel_data(channel_id)
                avg_views = get_average_views(playlist_id, False)
                target_cpv = (
                    round(total_cost / avg_views, 4) if avg_views else 0
                )
                df.at[idx, AVG_VIEWS_COL] = avg_views
                df.at[idx, TARGET_CPV_COL] = target_cpv
                updated += 1
                continue

            video_id = get_video_id(post_link)
            if not video_id:
                continue

            video = get_video_details(video_id)
            if not video:
                continue

            stats = video["statistics"]
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            engagement = likes + comments
            actual_er = round(engagement / views * 100, 2) if views else 0

            channel_id = video["snippet"]["channelId"]
            playlist_id = get_channel_data(channel_id)
            current_is_short = "/shorts/" in post_link.lower()
            avg_views = get_average_views(playlist_id, current_is_short)
            target_cpv = round(total_cost / avg_views, 4) if avg_views else 0
            actual_cpv = round(total_cost / views, 4) if views else 0

            df.at[idx, AVG_VIEWS_COL] = avg_views
            df.at[idx, TARGET_CPV_COL] = target_cpv
            df.at[idx, VIDEO_VIEWS_COL] = views
            df.at[idx, TOTAL_VIEWS_COL] = views
            df.at[idx, LIKES_COL] = likes
            df.at[idx, COMMENTS_COL] = comments
            df.at[idx, ENGAGEMENT_COL] = engagement
            df.at[idx, ACTUAL_ER_COL] = actual_er
            df.at[idx, ACTUAL_CPV_COL] = actual_cpv
            df.at[idx, STATUS_COL] = "Live"
            updated += 1

        except Exception:
            continue

    return df, updated
