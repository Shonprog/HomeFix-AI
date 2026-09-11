"""
Communication layer between the Streamlit frontend and n8n Workflow 1
(HomeFix Main). This is the ONLY place in the frontend that talks to the
backend, and the ONLY place that knows the production webhook URL.

The payload contract below matches what Workflow 1 already expects and
must not change without verifying the n8n workflow first:

    multipart/form-data fields:
        description  -> str
        session_id   -> str
        user_email   -> str (may be empty)
        image        -> optional file field
        task_action  -> optional str, e.g. "close_case" (only sent when
                         an explicit backend action is requested, instead
                         of a normal free-text troubleshooting message)

    JSON response (either key is accepted):
        {"assistant_message": "..."} or {"message": "..."}
"""

from __future__ import annotations

import requests
import streamlit as st

REQUEST_TIMEOUT_SECONDS = 120


class HomeFixAPIError(Exception):
    """User-facing error raised when the HomeFix backend can't be reached
    or returns something the frontend can't use. Always carries a Hebrew,
    non-technical message safe to show directly in the UI."""


def get_webhook_url() -> str:
    """Read the Workflow 1 production webhook URL from Streamlit secrets.

    Never hardcode this URL in code and never display it in the UI.
    """
    try:
        url = st.secrets["N8N_WEBHOOK_URL"]
    except Exception as exc:  # missing secrets.toml or missing key
        raise HomeFixAPIError(
            "המערכת אינה מוגדרת כראוי כרגע (חסרה כתובת שרת). "
            "יש לפנות לתמיכה הטכנית."
        ) from exc

    url = str(url).strip()
    if not url:
        raise HomeFixAPIError(
            "המערכת אינה מוגדרת כראוי כרגע (חסרה כתובת שרת). "
            "יש לפנות לתמיכה הטכנית."
        )
    return url


def send_message(
    description: str,
    session_id: str,
    user_email: str = "",
    image_file=None,
    task_action: str = "",
) -> tuple[str, dict]:
    """Send one chat turn to Workflow 1 and return (assistant_message, raw_json).

    ``task_action`` is optional and, when set (e.g. "close_case"), tells the
    backend this is an explicit action rather than a free-text troubleshooting
    message -- it is only included in the request when non-empty, so normal
    chat turns keep the exact same payload shape as before.

    Raises HomeFixAPIError with a friendly Hebrew message on any failure.
    """
    webhook_url = get_webhook_url()

    form_data = {
        "description": (description or "").strip(),
        "session_id": session_id,
        "user_email": (user_email or "").strip(),
    }
    if task_action:
        form_data["task_action"] = task_action

    files = None
    if image_file is not None:
        files = {
            "image": (
                image_file.name,
                image_file.getvalue(),
                image_file.type or "application/octet-stream",
            )
        }

    try:
        response = requests.post(
            webhook_url,
            data=form_data,
            files=files,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise HomeFixAPIError(
            "השרת לא הגיב בזמן. נסו שוב בעוד רגע."
        ) from exc
    except requests.ConnectionError as exc:
        raise HomeFixAPIError(
            "לא ניתן להתחבר כרגע למערכת HomeFix AI. נסו שוב מאוחר יותר."
        ) from exc
    except requests.HTTPError as exc:
        raise HomeFixAPIError(
            "המערכת החזירה שגיאה בעת עיבוד הבקשה. נסו שוב או פנו לתמיכה."
        ) from exc
    except requests.RequestException as exc:
        raise HomeFixAPIError(
            "אירעה שגיאה בשליחת הבקשה. נסו שוב."
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise HomeFixAPIError(
            "התקבלה תשובה לא תקינה מהמערכת."
        ) from exc

    assistant_message = (
        result.get("assistant_message")
        or result.get("message")
        or "לא התקבלה תשובה מהמערכת."
    )
    return assistant_message, result
