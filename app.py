import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP & SICHERHEIT ---
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
    st.error("Fehler: API-Keys in den Secrets prüfen!")
    st.stop()

# --- 2. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.write("Spar-Modus: **AKTIV** 💰")
    st.write("---")
    uploaded_file = st.file_uploader("📸 Brief scannen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.session_state.last_audio_ts = None
        st.rerun()

# --- 4. CHAT-LOGIK & SYSTEM PROMPT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Die "Gehirn-Anweisung" für die KI
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine wichtigste Regel: Unterscheide den Modus!"
    "\n\n1. ANALYSE-MODUS: Wenn ein BILD hochgeladen wurde oder der Nutzer 'Analysiere' sagt, nutze STRENG dieses Format:"
    "\n## 🎯 KLARTEXT\n(Was ist das?)\n## 🔍 DETAILS\n(Genaue Analyse)\n## 💰 FRISTEN\n(Daten & Beträge)\n## ⚡ SCHLACHTPLAN\n(Schritte)"
    "\n\n2. CHAT-MODUS: Wenn der Nutzer Fragen zum Brief stellt (z.B. 'Wie soll ich zahlen?', 'Was bedeutet das?') "
    "oder einfach nur 'Danke/Okay' sagt, antworte wie ein normaler, hilfreicher Berater. Nutze KEIN festes Format. "
    "Beantworte die Frage direkt und effizient."
)

# --- 5. INPUT VERARBEITUNG ---
user_input = st.chat_input("Frage zum Brief...")
final_prompt = user_input

# Sprache zu Text (Whisper)
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
    current_query = final_prompt if final_prompt else "Bitte analysiere diesen Brief."
    
    st.session_state.messages.append({"role": "user", "content": current_query})
    with st.chat_message("user"):
        st.markdown(current_query)

    # --- SPAR-PAYLOAD (Nur aktuelles Bild + Textverlauf) ---
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

    # --- KI ANFRAGE ---
    with st.spinner("🤖 Denkt nach..."):
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload,
                max_tokens=1000,
                temperature=0.7
            )
            answer = res.choices[0].message.content
            with st.chat_message("assistant"):
                st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # Backup
            try:
                supabase.table("brief_summaries").insert({"summary_text": answer[:200]}).execute()
            except: pass
        except Exception as e:
            st.error(f"Fehler: {e}")
