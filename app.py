import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP ---
st.set_page_config(page_title="Amtsschimmel-Zähmer PRO", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    pw = st.text_input("Passwort eingeben:", type="password")
    if pw == "Amt123":
        st.session_state.auth = True
        st.rerun()
    else:
        if pw: st.error("Falsches Passwort!")
        st.stop()

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("API-Key Fehler!")
    st.stop()

# --- 2. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    uploaded_file = st.file_uploader("📸 Brief hochladen", type=["jpg", "jpeg", "png"])
    # Mikrofon-Input
    audio_data = mic_recorder(start_prompt="🎤 Frage sprechen", stop_prompt="🛑 Stop", key='mic')
    if st.button("🗑️ Chat leeren"):
        st.session_state.messages = []
        st.session_state.last_audio = None # Audio-Reset
        st.rerun()

# --- 4. CHAT-LOGIK ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Den Chatverlauf anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- NEUER SYSTEM PROMPT FÜR DETAILS ---
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine Aufgabe: Analysiere Behördenbriefe extrem detailliert. "
    "Erkläre dem Nutzer genau, was das Beamtendeutsch bedeutet. "
    "Antworte immer in diesem Format:\n\n"
    "## 🎯 DER KERN DER SACHE\n(Was ist das für ein Brief? Wer schreibt hier genau?)\n\n"
    "## 🔍 DETAILLIERTE ANALYSE\n(Gehe Schritt für Schritt durch den Text. Erkläre schwierige Paragraphen.)\n\n"
    "## 💰 ZAHLEN & FRISTEN\n- **Betrag:** [X] €\n- **Deadline:** [Datum]\n- **Aktenzeichen:** [Nummer]\n\n"
    "## ⚡ SCHLACHTPLAN\n1. Was muss der Nutzer jetzt tun?\n2. Was passiert, wenn er nichts tut?"
)

# --- 5. INPUT-VERARBEITUNG ---
user_text = st.chat_input("Oder hier tippen...")
final_prompt = None

# 1. Check ob Sprache da ist
if audio_data and audio_data.get('bytes'):
    if "last_audio_ts" not in st.session_state or st.session_state.last_audio_ts != audio_data['bytes'][:100]:
        with st.spinner("Wandle Sprache in Text um..."):
            audio_bio = io.BytesIO(audio_data['bytes'])
            audio_bio.name = "input.wav"
            trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
            final_prompt = trans.text
            st.session_state.last_audio_ts = audio_data['bytes'][:100]

# 2. Wenn Text getippt wurde, überschreibt das alles
if user_text:
    final_prompt = user_text

# 3. Wenn was da ist, ab zu GPT
if final_prompt or uploaded_file:
    if not final_prompt: final_prompt = "Bitte analysiere diesen Brief so detailliert wie möglich."
    
    st.session_state.messages.append({"role": "user", "content": final_prompt})
    with st.chat_message("user"):
        st.markdown(final_prompt)

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

    with st.spinner("🤖 GPT analysiert tiefgründig..."):
        try:
            res = client.chat.completions.create(model="gpt-4o-mini", messages=messages_payload)
            ai_text = res.choices[0].message.content
            with st.chat_message("assistant"):
                st.markdown(ai_text)
            st.session_state.messages.append({"role": "assistant", "content": ai_text})
        except Exception as e:
            st.error(f"Fehler: {e}")
