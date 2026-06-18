import os

INSTAGRAM_BATCH_SIZE = 20


def _get_secret(key):
    value = os.environ.get(key)
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets[key]
    except Exception:
        return None


def get_youtube_api_key():
    return _get_secret("YOUTUBE_API_KEY")


def get_apify_token():
    return _get_secret("APIFY_TOKEN")


def keys_configured():
    return bool(get_youtube_api_key() and get_apify_token())
