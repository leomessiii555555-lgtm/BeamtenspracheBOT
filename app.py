import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP ---
st.set_page_config(page_title="Amtsschimmel-Zähmer ECO", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    pw = st.text_input("Passwort:", type="password")
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
    st.title("🛡️ Amtsschimmel-Zähmer")
    st.info("Modus: Behörden-Spezialist ⚖️")
    uploaded_file = st.file_uploader("📸 Brief-Foto", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.session_state.last_audio_ts = None
        st.rerun()

# --- 4. CHAT-LOGIK & EISERNE REGELN ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# DIE STRENGE ANWEISUNG
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Du bist NUR für Behördenbriefe zuständig."
    "\n\nVERBOTE:"
    "\n- Beantworte KEINE Mathe-Aufgaben oder allgemeine Fragen (Kochen, Hausaufgaben, etc.). Sag höflich, dass du nur für Briefe da bist."
    "\n\nANTWORT-MODUS:"
    "\n1. NUR wenn ein BILD oder ein langer BRIEF-TEXT kommt: Nutze ## 🎯 KLARTEXT, ## 🔍 DETAILS, ## 💰 FRISTEN, ## ⚡ SCHLACHTPLAN."
    "\n2. Wenn der Nutzer Fragen zum Brief stellt (z.B. 'Soll ich zahlen?'): Antworte kurz, direkt und OHNE das Klartext-Format. Sei ein Berater."
    "\n3. Fasse dich extrem kurz, um Kosten zu sparen."
)

# --- 5. INPUT ---
user_input = st.chat_input("Nachricht oder Brief-Text...")
final_prompt = user_input

# Audio (Whisper)
if audio_data and audio_data.get('bytes'):
    current_audio_hash = audio_data['bytes'][:100]
    if "last_audio_ts" not in st.session_state or st.session_state.last_audio_ts != current_audio_hash:
        audio_bio = io.BytesIO(audio_data['bytes'])
        audio_bio.name = "input.wav"
        trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
        final_prompt = trans.text
        st.session_state.last_audio_ts = current_audio_hash

if final_prompt or uploaded_file:
    query = final_prompt if final_prompt else "Analysiere diesen Brief kurz."
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    payload = [{"role": "system", "content": system_instruction}]
    # Nur Text-Historie mitschicken (spart Geld)
    for m in st.session_state.messages[:-1]:
        payload.append({"role": m["role"], "content": m["content"]})
    
    if uploaded_file:
        img_b64 = encode_image(uploaded_file)
        payload.append({
            "role": "user",
            "content": [
                {"type": "text", "text": query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "low"}}
            ]
        })
    else:
        payload.append({"role": "user", "content": query})

    with st.spinner("🤖"):
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=payload,
                max_tokens=500,
                temperature=0.2 # Niedrige Temperatur = weniger 'kreatives' Gelaber
            )
            answer = res.choices[0].message.content
            with st.chat_message("assistant"):
                st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error(f"Fehler: {e}")
