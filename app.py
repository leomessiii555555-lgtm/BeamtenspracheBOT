import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP ---
st.set_page_config(page_title="Amtsschimmel-Zähmer PRO", layout="wide", page_icon="🛡️")

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
    st.error("Fehler: API-Keys prüfen!")
    st.stop()

# --- 2. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.info("Modus: Intelligent 🧠")
    uploaded_file = st.file_uploader("📸 Brief-Foto hochladen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    if st.button("🗑️ Chat leeren"):
        st.session_state.messages = []
        st.session_state.last_audio_ts = None
        st.rerun()

# --- 4. CHAT-LOGIK & INTELLIGENTER SYSTEM PROMPT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Hier ist die Logik, die erkennt, ob es ein Brief-Text oder nur eine Frage ist
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine Aufgabe ist es, Behördenbriefe zu bändigen."
    "\n\nENTSCHEIDUNGSLOGIK FÜR DEINE ANTWORT:"
    "\n1. WENN der Nutzer ein BILD hochlädt ODER einen langen Text reinkopiert, der wie ein Brief aussieht (viele Fakten, Aktenzeichen, Behörden-Deutsch):"
    "\n   -> Nutze STRENG das Format: ## 🎯 KLARTEXT, ## 🔍 DETAILS, ## 💰 FRISTEN, ## ⚡ SCHLACHTPLAN."
    "\n\n2. WENN der Nutzer nur eine kurze Frage stellt (z.B. 'Wie soll ich zahlen?'), Smalltalk macht oder sich bedankt:"
    "\n   -> Antworte als lockerer Berater OHNE festes Format. Sei direkt und hilfreich."
    "\n\nZusammengefasst: Analyse-Format nur bei 'hartem Stoff' (Briefen/Kopien), sonst normaler Chat."
)

# --- 5. INPUT VERARBEITUNG ---
user_input = st.chat_input("Brief-Text hier reinkopieren oder Frage stellen...")
final_prompt = user_input

# Audio (Whisper)
if audio_data and audio_data.get('bytes'):
    current_audio_hash = audio_data['bytes'][:100]
    if "last_audio_ts" not in st.session_state or st.session_state.last_audio_ts != current_audio_hash:
        with st.spinner("Wandle Sprache um..."):
            audio_bio = io.BytesIO(audio_data['bytes'])
            audio_bio.name = "input.wav"
            trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
            final_prompt = trans.text
            st.session_state.last_audio_ts = current_audio_hash

if final_prompt or uploaded_file:
    current_query = final_prompt if final_prompt else "Analysiere diesen Brief."
    
    st.session_state.messages.append({"role": "user", "content": current_query})
    with st.chat_message("user"):
        st.markdown(current_query)

    messages_payload = [{"role": "system", "content": system_instruction}]
    for m in st.session_state.messages[:-1]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    
    if uploaded_file:
        img_b64 = encode_image(uploaded_file)
        messages_payload.append({
            "role": "user",
            "content": [
                {"type": "text", "text": current_query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        })
    else:
        messages_payload.append({"role": "user", "content": current_query})

    with st.spinner("🤖 Überlege..."):
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload,
                max_tokens=1200,
                temperature=0.7
            )
            answer = res.choices[0].message.content
            with st.chat_message("assistant"):
                st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error(f"Fehler: {e}")
