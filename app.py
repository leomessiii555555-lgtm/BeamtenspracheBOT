import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. INITIALISIERUNG ---
st.set_page_config(page_title="Amtsschimmel-Zähmer PRO", layout="wide")

# Passwort-Schutz (Damit niemand dein Guthaben leer macht)
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    pw = st.text_input("Passwort eingeben:", type="password")
    if pw == "Amt123":  # <--- Das ist dein Passwort! Kannst du hier ändern.
        st.session_state.auth = True
        st.rerun()
    else:
        if pw: st.error("Falsches Passwort!")
        st.stop()

# API Keys aus den Streamlit Secrets laden
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Fehler: API-Keys fehlen in den Secrets! (OPENAI_API_KEY prüfen)")
    st.stop()

# --- 2. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.info("Status: GPT-4o-mini Aktiv ✅")
    uploaded_file = st.file_uploader("📸 Brief hochladen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Anweisung sprechen", stop_prompt="🛑 Fertig", key='mic')
    if st.button("🗑️ Chat leeren"):
        st.session_state.messages = []
        st.rerun()

# --- 4. CHAT-HISTORIE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Strengere Anweisung gegen Missbrauch
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine Aufgabe: Analysiere Behördenbriefe. "
    "Sei direkt, frech und effizient. Lehne Fragen ab, die nichts mit Briefen zu tun haben. "
    "Antworte immer so: \n"
    "### 🎯 KLARTEXT\n(Was wollen die? 1 Satz)\n\n"
    "### 💰 FAKTEN\n- Betrag: [X]\n- DEADLINE: **[Datum]**\n\n"
    "### ⚡ SCHLACHTPLAN\n1. [Schritt 1]\n2. [Schritt 2]"
)

# --- 5. INPUT VERARBEITUNG ---
user_text = st.chat_input("Frage zum Brief...")
final_prompt = user_text

# Audio zu Text (OpenAI Whisper)
if audio_data and "bytes" in audio_data:
    try:
        audio_bio = io.BytesIO(audio_data['bytes'])
        audio_bio.name = "input.wav"
        trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
        final_prompt = trans.text
    except: pass

if final_prompt or uploaded_file:
    if not final_prompt: final_prompt = "Analysiere diesen Brief."
    
    st.session_state.messages.append({"role": "user", "content": final_prompt})
    with st.chat_message("user"):
        st.markdown(final_prompt)

    # Payload für OpenAI vorbereiten
    messages_payload = [{"role": "system", "content": system_instruction}]
    for m in st.session_state.messages[:-1]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    
    if uploaded_file:
        img_b64 = encode_image(uploaded_file)
        messages_payload.append({
            "role": "user",
            "content": [
                {"type": "text", "text": final_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        })
    else:
        messages_payload.append({"role": "user", "content": final_prompt})

    with st.spinner("🤖 GPT liest den Brief..."):
        try:
            # Nutzung des günstigen gpt-4o-mini Modells
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload,
                max_tokens=1000
            )
            ai_text = res.choices[0].message.content
            
            with st.chat_message("assistant"):
                st.markdown(ai_text)
            st.session_state.messages.append({"role": "assistant", "content": ai_text})
            
            # Backup in Supabase
            try:
                supabase.table("brief_summaries").insert({"summary_text": ai_text[:300]}).execute()
            except: pass
            
        except Exception as e:
            st.error(f"Fehler: {e}")
