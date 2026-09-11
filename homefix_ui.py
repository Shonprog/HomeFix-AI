"""
Presentation helpers for the HomeFix AI Streamlit frontend:
RTL/bidi styling and Hebrew status labels.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Status labels — internal backend values must never leak to the customer.
# ---------------------------------------------------------------------------

STATUS_HE = {
    "open": "פתוח",
    "in_progress": "בטיפול",
    "closed": "סגור",
}

_STATUS_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in STATUS_HE) + r")\b",
    re.IGNORECASE,
)


def translate_status_words(text: str) -> str:
    """Defensively replace raw internal status words with Hebrew labels,
    in case the backend ever echoes one verbatim."""
    if not text:
        return text

    def _replace(match: re.Match) -> str:
        return STATUS_HE.get(match.group(1).lower(), match.group(0))

    return _STATUS_WORD_RE.sub(_replace, text)


# ---------------------------------------------------------------------------
# Conversation titles — derived locally from the first user message, never
# via an extra AI call. Simple, deterministic prefix-trim + length cap.
# ---------------------------------------------------------------------------

_TITLE_LEADING_FILLER = "יש לי "
_TITLE_MAX_LEN = 40


def derive_conversation_title(first_user_message: str) -> str:
    cleaned = (first_user_message or "").strip()
    if not cleaned:
        return "שיחה חדשה"
    if cleaned.startswith(_TITLE_LEADING_FILLER):
        cleaned = cleaned[len(_TITLE_LEADING_FILLER):].strip() or cleaned
    if len(cleaned) > _TITLE_MAX_LEN:
        cleaned = cleaned[:_TITLE_MAX_LEN].rstrip() + "…"
    return cleaned


# ---------------------------------------------------------------------------
# Global CSS: RTL layout that keeps embedded English/numbers (HDMI, Wi-Fi,
# model names) in correct visual order instead of being mirrored.
# ---------------------------------------------------------------------------

APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&display=swap');

    :root {
        --hf-accent: #0d9488;
        --hf-accent-dark: #0f766e;
        --hf-accent-soft: #f0fdfa;
        --hf-border: rgba(15, 23, 42, 0.08);
        --hf-text: #1f2937;
        --hf-text-muted: #64748b;
    }

    html, body, [class*="css"] {
        direction: rtl;
        font-family: "Heebo", "Assistant", "Rubik", -apple-system, sans-serif;
    }

    h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stButton button, .stTextInput input, .stTextArea textarea,
    [data-testid="stSidebar"], [data-testid="stChatMessageContent"] {
        font-family: "Heebo", "Assistant", "Rubik", -apple-system, sans-serif;
    }

    [data-testid="stAppViewContainer"] {
        background: #fafafa;
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    /* ---------------- Brand header ---------------- */
    .hf-appbar {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.25rem 0 1.1rem 0;
        margin-bottom: 0.4rem;
        border-bottom: 1px solid var(--hf-border);
    }

    .hf-appbar-mark {
        flex-shrink: 0;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: linear-gradient(135deg, #0d9488, #14b8a6);
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.05rem;
        letter-spacing: 0.02em;
        box-shadow: 0 4px 10px rgba(13, 148, 136, 0.28);
    }

    .hf-appbar-mark--sm {
        width: 34px;
        height: 34px;
        font-size: 0.85rem;
        border-radius: 9px;
    }

    .hf-appbar-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: var(--hf-text);
        line-height: 1.2;
    }

    .hf-appbar-sub {
        font-size: 0.85rem;
        color: var(--hf-text-muted);
        margin-top: 0.1rem;
    }

    /* Sidebar brand */
    .hf-sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.4rem 0 1rem 0;
    }

    .hf-sidebar-brand-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--hf-text);
        line-height: 1.2;
    }

    .hf-sidebar-brand-sub {
        font-size: 0.75rem;
        color: var(--hf-text-muted);
    }

    /* ---------------- Welcome card ---------------- */
    .homefix-welcome {
        background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 100%);
        border: 1px solid rgba(13, 148, 136, 0.18);
        border-radius: 16px;
        padding: 1.35rem 1.5rem;
        margin-bottom: 1.1rem;
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
        font-size: 1.02rem;
        line-height: 1.65;
        color: var(--hf-text);
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }

    /* ---------------- Section titles ---------------- */
    [data-testid="stMarkdownContainer"] h4 {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--hf-text-muted);
        letter-spacing: 0.01em;
        margin: 1.4rem 0 0.6rem 0;
    }

    /* ---------------- Buttons ---------------- */
    .stButton button {
        direction: rtl;
        border-radius: 10px;
        font-weight: 500;
        border: 1px solid var(--hf-border);
        transition: all 0.15s ease;
    }

    .stButton button:hover {
        border-color: var(--hf-accent);
        color: var(--hf-accent-dark);
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(13, 148, 136, 0.12);
    }

    .stButton button[kind="primary"] {
        background: var(--hf-accent);
        border-color: var(--hf-accent);
    }

    .stButton button[kind="primary"]:hover {
        background: var(--hf-accent-dark);
        border-color: var(--hf-accent-dark);
        color: #ffffff;
    }

    /* Bordered card-style columns (quick-action tiles) */
    [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px;
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }

    [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
        transform: translateY(-2px);
    }

    /* ---------------- Sidebar ---------------- */
    [data-testid="stSidebar"] {
        direction: rtl;
        text-align: right;
        background: #ffffff;
        border-left: 1px solid var(--hf-border);
    }

    [data-testid="stSidebar"] .stButton button {
        text-align: right;
        justify-content: flex-start;
        background: transparent;
        border: 1px solid transparent;
    }

    [data-testid="stSidebar"] .stButton button:hover {
        background: var(--hf-accent-soft);
        border-color: rgba(13, 148, 136, 0.2);
    }

    [data-testid="stSidebar"] .stButton button[kind="primary"] {
        background: var(--hf-accent-soft);
        color: var(--hf-accent-dark);
        border-color: rgba(13, 148, 136, 0.3);
        font-weight: 600;
    }

    /* ---------------- Chat ---------------- */
    [data-testid="stChatMessageContent"] {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
    }

    [data-testid="stChatMessageContent"] ol,
    [data-testid="stChatMessageContent"] ul {
        direction: rtl;
        text-align: right;
        padding-right: 1.4rem;
        padding-left: 0;
    }

    [data-testid="stChatMessageContent"] li {
        padding-right: 0.2rem;
    }

    [data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.15rem 0.3rem;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: #ffffff;
        border: 1px solid var(--hf-border);
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: var(--hf-accent-soft);
        border: 1px solid rgba(13, 148, 136, 0.15);
    }

    /* ---------------- Inputs ---------------- */
    .stTextArea textarea,
    .stTextInput input,
    [data-testid="stChatInputTextArea"] {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
        border-radius: 10px;
    }

    /* ---------------- Popover / expander ---------------- */
    [data-testid="stPopoverBody"] {
        direction: rtl;
        text-align: right;
        border-radius: 12px;
    }

    [data-testid="stExpander"] {
        border-radius: 12px;
        border: 1px solid var(--hf-border);
    }
</style>
"""
