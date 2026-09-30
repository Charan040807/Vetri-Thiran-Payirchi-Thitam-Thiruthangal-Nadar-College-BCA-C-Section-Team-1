"""Shared helpers: Gemini client, JSON/chat/image calls, PDF export."""
import os, io, json, re, time
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fpdf import FPDF

load_dotenv()
TEXT_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"  # used if the main model is busy
IMAGE_MODEL = "gemini-3.1-flash-image"


def page_setup(title, icon, caption):
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.title(f"{icon} {title}")
    st.caption(caption)


@st.cache_resource
def client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        st.error("GEMINI_API_KEY not found. Add it to the .env file and restart the app.")
        st.stop()
    return genai.Client(api_key=key)


def ask(contents, system=None, json_mode=False, temperature=0.7):
    """Call Gemini. Returns text, or parsed JSON when json_mode=True. Returns None on failure."""
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=temperature,
        response_mime_type="application/json" if json_mode else None)
    text, last_err = None, None
    for model in (TEXT_MODEL, FALLBACK_MODEL):
        for _ in range(2):
            try:
                text = client().models.generate_content(model=model, contents=contents, config=cfg).text or ""
                break
            except Exception as e:
                last_err = e
                if not any(c in str(e) for c in ("429", "503", "UNAVAILABLE")):
                    st.error(f"Gemini error: {e}")
                    return None
                time.sleep(3)  # busy or rate limited: wait, retry, then try the backup model
        if text is not None:
            break
    if text is None:
        st.error(f"Gemini is very busy right now. Please try again in a minute. ({last_err})")
        return None
    if json_mode:
        try:
            return json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip())
        except json.JSONDecodeError:
            st.error("The AI returned an unreadable format. Please try again.")
            return None
    return text


def chat_reply(history, system):
    """history = [{'role': 'user'|'assistant', 'content': str}, ...]"""
    contents = [types.Content(role="user" if m["role"] == "user" else "model",
                              parts=[types.Part(text=m["content"])]) for m in history]
    return ask(contents, system)


def generate_image(prompt):
    """Returns image bytes or None."""
    try:
        r = client().models.generate_content(
            model=IMAGE_MODEL, contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
        for p in r.candidates[0].content.parts:
            if p.inline_data:
                return p.inline_data.data
    except Exception as e:
        st.warning(f"Image generation failed: {e}")
    return None


def clean_text(t):
    return re.sub(r"[*#`]", "", str(t)).encode("latin-1", "replace").decode("latin-1")


def make_pdf(title, text):
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, clean_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.ln(3)
    pdf.multi_cell(0, 6, clean_text(text), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())