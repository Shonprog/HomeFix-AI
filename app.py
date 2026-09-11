"""HomeFix AI — Hebrew customer chat frontend for n8n Workflow 1.

The app talks ONLY to the Workflow 1 production webhook (configured via
st.secrets["N8N_WEBHOOK_URL"]). All "smart buttons" below are convenience
shortcuts that build a natural-language Hebrew message and send it through
the exact same request function used by free-text chat -- they never talk
to Supabase / MCP / Workflow 2 directly.

Conversation history is a frontend-only, session-scoped cache
(st.session_state.conversations). There is currently no backend capability
to list past conversations or fetch messages by session_id, so nothing here
survives a browser reload -- see README for the minimal Workflow 1 extension
that would be needed to back this with real Supabase-backed persistence.
"""

from __future__ import annotations

import uuid

import streamlit as st

from homefix_api import HomeFixAPIError, send_message
from homefix_ui import (
    APP_CSS,
    derive_conversation_title,
    translate_status_words,
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def ensure_state() -> None:
    # Only created once per browser session; never regenerated on a normal
    # rerun. It is only replaced when the user explicitly starts a new issue
    # or explicitly opens a different past conversation.
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    st.session_state.setdefault("view", "home")  # "home" | "chat"
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("user_email", "")
    st.session_state.setdefault("pending_action", None)
    st.session_state.setdefault("show_followup", False)
    st.session_state.setdefault("case_closed", False)
    # session_id -> {"title": str | None, "messages": [...]}
    st.session_state.setdefault("conversations", {})


def sync_active_conversation() -> None:
    """Mirror the active chat into the local conversation cache (frontend
    cache layer only -- Supabase remains the real source of truth)."""
    sid = st.session_state.session_id
    entry = st.session_state.conversations.setdefault(
        sid, {"title": None, "messages": []}
    )
    entry["messages"] = st.session_state.messages
    if entry["title"] is None:
        first_user = next(
            (m["content"] for m in st.session_state.messages if m["role"] == "user"),
            None,
        )
        if first_user:
            entry["title"] = derive_conversation_title(first_user)


def start_new_issue() -> None:
    """The ONLY action that starts a brand-new technical conversation."""
    sync_active_conversation()  # keep the conversation we're leaving in the list
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    clear_pending_reminder_dialog()
    st.session_state.show_followup = False
    st.session_state.case_closed = False
    st.session_state.view = "chat"
    # user_email is intentionally left untouched


def open_conversation(session_id: str) -> None:
    """Switch the active backend session_id to a past local conversation and
    restore its messages. Future messages continue on this SAME session_id."""
    sync_active_conversation()
    entry = st.session_state.conversations.get(session_id, {"messages": []})
    st.session_state.session_id = session_id
    st.session_state.messages = list(entry["messages"])
    clear_pending_reminder_dialog()
    st.session_state.show_followup = False
    st.session_state.case_closed = False
    st.session_state.view = "chat"


# ---------------------------------------------------------------------------
# Core send flow — everything (chat input, quick buttons, nav) goes through
# this single function so the request/response handling stays in one place.
# ---------------------------------------------------------------------------

def perform(
    description: str,
    echo: str | None = None,
    requires_email: bool = False,
    image_file=None,
    next_followup: bool = False,
) -> None:
    if requires_email and not st.session_state.user_email:
        st.session_state.pending_action = {
            "description": description,
            "echo": echo,
            "next_followup": next_followup,
        }
        st.rerun()
        return

    display_text = echo if echo is not None else description
    st.session_state.messages.append({"role": "user", "content": display_text})
    st.session_state.case_closed = False

    try:
        with st.spinner("HomeFix AI בודק את הבקשה..."):
            assistant_message, _raw = send_message(
                description=description,
                session_id=st.session_state.session_id,
                user_email=st.session_state.user_email,
                image_file=image_file,
            )
    except HomeFixAPIError as exc:
        st.session_state.messages.append(
            {"role": "assistant", "content": f"⚠️ {exc}"}
        )
        st.session_state.show_followup = False
    else:
        clean_message = translate_status_words(assistant_message)
        st.session_state.messages.append(
            {"role": "assistant", "content": clean_message}
        )
        st.session_state.show_followup = next_followup

    sync_active_conversation()
    st.rerun()


def close_active_case() -> None:
    """Explicit "הסתדר ✅" action: closes the active case via task_action
    instead of sending it as a normal troubleshooting chat message."""
    clear_pending_reminder_dialog()
    st.session_state.messages.append(
        {"role": "user", "content": "✅ הבעיה הסתדרה"}
    )
    st.session_state.show_followup = False
    st.session_state.case_closed = False

    try:
        with st.spinner("HomeFix AI סוגר את התקלה..."):
            send_message(
                description="",
                session_id=st.session_state.session_id,
                user_email=st.session_state.user_email,
                task_action="close_case",
            )
    except HomeFixAPIError as exc:
        st.session_state.messages.append(
            {"role": "assistant", "content": f"⚠️ {exc}"}
        )
    else:
        st.session_state.messages.append(
            {"role": "assistant", "content": "התקלה נסגרה בהצלחה ✅"}
        )
        st.session_state.case_closed = True

    sync_active_conversation()
    st.rerun()


# ---------------------------------------------------------------------------
# Email dialog — shown only when an email-requiring action is queued and no
# email is known yet.
#
# Bug fix: st.dialog has no way to run our code on a plain rerun, so without
# on_dismiss, closing via the native "X" (or ESC / outside-click) left
# `pending_action` set and the dialog would silently reopen on the next
# unrelated rerun (e.g. clicking "הסתדר"). `on_dismiss` runs our cleanup
# callback for exactly that case; every other way to leave the dialog
# (Cancel, closing the active case, starting a new issue, opening another
# conversation) also routes through the same clear_pending_reminder_dialog()
# helper so no path can leave stale state behind.
# ---------------------------------------------------------------------------

def clear_pending_reminder_dialog() -> None:
    """Reset all session state that could cause the reminder/email dialog
    to (re)open on a later, unrelated rerun."""
    st.session_state.pending_action = None


@st.dialog("כתובת אימייל לתזכורות", on_dismiss=clear_pending_reminder_dialog)
def email_dialog() -> None:
    st.write(
        "כדי לנהל תזכורות ולשלוח עדכונים, נשמח לקבל את כתובת האימייל שלך."
    )
    email = st.text_input(
        "כתובת אימייל",
        key="email_dialog_input",
        placeholder="name@example.com",
    )
    col_save, col_cancel = st.columns(2)
    if col_save.button("שמירה והמשך", type="primary", use_container_width=True):
        if email and "@" in email and "." in email.split("@")[-1]:
            st.session_state.user_email = email.strip()
            st.rerun()
        else:
            st.warning("נא להזין כתובת אימייל תקינה.")
    if col_cancel.button("ביטול", use_container_width=True):
        clear_pending_reminder_dialog()
        st.rerun()


# ---------------------------------------------------------------------------
# Conversation list — shared between the sidebar and the Home screen.
# ---------------------------------------------------------------------------

def render_conversation_list() -> None:
    items = list(st.session_state.conversations.items())[::-1]  # most recent first
    if not items:
        st.caption("אין עדיין שיחות שמורות בסשן הזה.")
        return
    for sid, entry in items:
        title = entry.get("title") or "שיחה חדשה"
        is_active = sid == st.session_state.session_id
        if st.button(
            title,
            icon=":material/radio_button_checked:" if is_active else ":material/chat_bubble:",
            key=f"convo_{sid}",
            use_container_width=True,
            disabled=is_active,
        ):
            open_conversation(sid)
            st.rerun()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="hf-sidebar-brand">'
            '<div class="hf-appbar-mark hf-appbar-mark--sm">HF</div>'
            '<div>'
            '<div class="hf-sidebar-brand-title">HomeFix AI</div>'
            '<div class="hf-sidebar-brand-sub">תמיכה טכנית חכמה לבית</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )

        is_home = st.session_state.view == "home"
        if st.button(
            "בית",
            icon=":material/home:",
            use_container_width=True,
            type="primary" if is_home else "secondary",
        ):
            st.session_state.view = "home"
            st.rerun()

        if st.button("תקלה חדשה", icon=":material/add_circle:", use_container_width=True):
            start_new_issue()
            st.rerun()

        if st.button("הקייסים שלי", icon=":material/folder_open:", use_container_width=True):
            st.session_state.view = "chat"
            perform(
                "איזה קייסים פתוחים יש לי?",
                echo="📂 הקייסים שלי",
            )

        if st.button("התזכורות שלי", icon=":material/notifications:", use_container_width=True):
            st.session_state.view = "chat"
            perform(
                "מה התזכורות הפתוחות שלי?",
                echo="🔔 התזכורות שלי",
                requires_email=True,
            )

        st.divider()

        with st.expander("השיחות שלי", icon=":material/forum:"):
            render_conversation_list()

        st.divider()

        with st.popover("הגדרות", icon=":material/settings:", use_container_width=True):
            st.markdown("**כתובת אימייל לתזכורות**")
            current_email = st.session_state.user_email or ""
            new_email = st.text_input(
                "אימייל",
                value=current_email,
                key="settings_email_input",
                label_visibility="collapsed",
                placeholder="name@example.com",
            )
            if st.button("שמירה", icon=":material/save:", key="save_email_btn"):
                st.session_state.user_email = new_email.strip()
                st.success("נשמר!")


# ---------------------------------------------------------------------------
# Home view — a static launcher screen. Never touches session_id, never
# clears messages, never closes anything.
# ---------------------------------------------------------------------------

def render_home() -> None:
    st.markdown(
        '<div class="homefix-welcome">שלום! 👋 אני <b>HomeFix AI</b>, '
        "העוזר החכם לתקלות בבית. איך אפשר לעזור היום?</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### מה קורה?")
    s1, s2, s3 = st.columns(3, border=True)
    if s1.button("בעיה בטלוויזיה", icon=":material/tv:", use_container_width=True):
        st.session_state.view = "chat"
        perform(
            "יש לי בעיה בטלוויזיה",
            echo="📺 יש לי בעיה בטלוויזיה",
            next_followup=True,
        )
    if s2.button("בעיה במזגן", icon=":material/ac_unit:", use_container_width=True):
        st.session_state.view = "chat"
        perform(
            "יש לי בעיה במזגן",
            echo="❄️ יש לי בעיה במזגן",
            next_followup=True,
        )
    if s3.button("תקלה אחרת", icon=":material/handyman:", use_container_width=True):
        st.session_state.view = "chat"
        perform(
            "יש לי תקלה בבית",
            echo="🔧 יש לי תקלה בבית",
            next_followup=True,
        )

    st.divider()

    st.markdown("#### גישה מהירה")
    q1, q2 = st.columns(2, border=True)
    if q1.button(
        "הקייסים שלי",
        icon=":material/folder_open:",
        use_container_width=True,
        key="home_cases",
    ):
        st.session_state.view = "chat"
        perform("איזה קייסים פתוחים יש לי?", echo="📂 הקייסים שלי")
    if q2.button(
        "התזכורות שלי",
        icon=":material/notifications:",
        use_container_width=True,
        key="home_reminders",
    ):
        st.session_state.view = "chat"
        perform(
            "מה התזכורות הפתוחות שלי?",
            echo="🔔 התזכורות שלי",
            requires_email=True,
        )

    st.divider()

    st.markdown("#### השיחות שלי")
    render_conversation_list()


# ---------------------------------------------------------------------------
# Chat view
# ---------------------------------------------------------------------------

def render_chat_messages() -> None:
    if not st.session_state.messages:
        st.caption("כתבו כאן את התקלה שלכם כדי להתחיל.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if (
        st.session_state.show_followup
        and st.session_state.messages
        and st.session_state.messages[-1]["role"] == "assistant"
    ):
        key_suffix = len(st.session_state.messages)
        c1, c2, c3 = st.columns(3)
        if c1.button(
            "הסתדר",
            icon=":material/check_circle:",
            type="primary",
            use_container_width=True,
            key=f"resolved_{key_suffix}",
        ):
            close_active_case()
        if c2.button(
            "עדיין לא הסתדר",
            icon=":material/build:",
            use_container_width=True,
            key=f"unresolved_{key_suffix}",
        ):
            perform("לא, עדיין לא הסתדר", echo="🔧 עדיין לא הסתדר")
        if c3.button(
            "תזכיר לי לבדוק אחר כך",
            icon=":material/schedule:",
            type="tertiary",
            use_container_width=True,
            key=f"remindlater_{key_suffix}",
        ):
            perform(
                "תזכיר לי לבדוק שוב מחר אם הבעיה הסתדרה",
                echo="⏰ תזכיר לי לבדוק אחר כך",
                requires_email=True,
            )

    if st.session_state.case_closed:
        if st.button(
            "לפתוח תקלה חדשה",
            icon=":material/add_circle:",
            use_container_width=True,
            key="open_new_after_close",
        ):
            start_new_issue()
            st.rerun()


def render_chat_input() -> None:
    chat_value = st.chat_input(
        "כתבו כאן את התקלה... אפשר גם לצרף תמונה",
        accept_file=True,
        file_type=["jpg", "jpeg", "png"],
    )
    if not chat_value:
        return

    text = (chat_value.text or "").strip()
    image_file = chat_value.files[0] if chat_value.files else None

    if not text and image_file is None:
        st.warning("נא לכתוב תיאור של התקלה או לצרף תמונה.")
        return

    if image_file is not None and len(image_file.getvalue()) > MAX_IMAGE_BYTES:
        st.warning("קובץ התמונה גדול מדי (מקסימום 10MB). נסו תמונה קטנה יותר.")
        return

    if image_file is not None:
        echo = f"{text}\n\n📷 צורפה תמונה" if text else "📷 צורפה תמונה"
    else:
        echo = text

    perform(text, echo=echo, image_file=image_file, next_followup=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="HomeFix AI",
        page_icon="🛠️",
        layout="centered",
    )
    st.markdown(APP_CSS, unsafe_allow_html=True)

    ensure_state()

    # Resume a queued action once the email becomes available, or (re)open
    # the dialog asking for it.
    if st.session_state.pending_action and st.session_state.user_email:
        action = st.session_state.pending_action
        st.session_state.pending_action = None
        perform(
            action["description"],
            echo=action.get("echo"),
            requires_email=False,
            next_followup=action.get("next_followup", False),
        )
        return
    if st.session_state.pending_action and not st.session_state.user_email:
        email_dialog()

    st.markdown(
        '<div class="hf-appbar">'
        '<div class="hf-appbar-mark">HF</div>'
        "<div>"
        '<div class="hf-appbar-title">HomeFix AI</div>'
        '<div class="hf-appbar-sub">העוזר החכם לתקלות בבית</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    render_sidebar()

    if st.session_state.view == "home":
        render_home()
    else:
        render_chat_messages()
        render_chat_input()


if __name__ == "__main__":
    main()
