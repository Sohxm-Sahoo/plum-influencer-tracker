import io

import pandas as pd

from core.instagram import update_instagram_rows
from core.youtube import update_youtube_rows


def update_influencer_csv(
    file_bytes,
    update_instagram=True,
    update_youtube=True,
    progress_callback=None,
):
    df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    df.columns = df.columns.str.strip()

    for col in df.columns:
        df[col] = df[col].astype(object)

    stats = {
        "instagram_updated": 0,
        "youtube_updated": 0,
        "total_rows": len(df),
    }

    if update_youtube:
        if progress_callback:
            progress_callback("phase", "Updating YouTube rows…")

        def yt_progress(current, total, message):
            if progress_callback:
                progress_callback("youtube", current, total, message)

        df, yt_count = update_youtube_rows(df, progress_callback=yt_progress)
        stats["youtube_updated"] = yt_count

    if update_instagram:
        if progress_callback:
            progress_callback("phase", "Updating Instagram rows…")

        def ig_progress(current, total, message):
            if progress_callback:
                progress_callback("instagram", current, total, message)

        df, ig_count = update_instagram_rows(df, progress_callback=ig_progress)
        stats["instagram_updated"] = ig_count

    output = io.BytesIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    output.seek(0)

    return output.getvalue(), stats
