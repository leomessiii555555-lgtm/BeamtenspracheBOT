import streamlit as st
from groq import Groq
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP ---
st.set_page_config(page_title="Amtsschimmel-Zähmer", layout="wide")

# API Keys aus den Secrets laden
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    S_URL = st.secrets["SUPABASE_URL"]
    S_KEY = st.secrets["SUPABASE_KEY"]
except Exception as e:
    st.error(f"API Keys fehlen in den Secrets: {e}")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(S_URL, S_KEY)

# --- 2. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.write("Scan den Brief, ich regel das.")
    uploaded_file = st.file_uploader("📸 Brief hochladen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Anweisung sprechen", stop_prompt="🛑 Fertig", key='sidebar_mic')
    if st.button("🗑️ Chat leeren"):
        st.session_state.messages = []
        st.rerun()

# --- 4. CHAT-HISTORIE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. DER "RECHTS-BULLE" PROMPT ---
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine Aufgabe: Analysiere den Brief auf dem Bild VOLLSTÄNDIG. "
    "Verweise NIEMALS darauf, dass der Nutzer den Brief selbst lesen soll. "
    "Antworte IMMER so:\n"
    "### 🎯 KLARTEXT\n(Was wollen die? 1 Satz)\n\n"
    "### 💰 FAKTEN\n- Betrag: [X]\n- DEADLINE: **[Datum]**\n\n"
    "### ⚡ SCHLACHTPLAN\n1. [Schritt 1]\n2. [Schritt 2]"
)

# --- 6. INPUT VERARBEITUNG ---
user_text = st.chat_input("Frage zum Brief...")

# Audio-Transkription
audio_prompt = None
if audio_data:
    try:
        audio_bio = io.BytesIO(audio_data['bytes'])
        audio_bio.name = "input.wav"
        trans = client.audio.transcriptions.create(file=(audio_bio.name, audio_bio.read()), model="whisper-large-v3")
        audio_prompt = trans.text
    except Exception as e:
        st.error(f"Audio-Fehler: {e}")

final_input = user_text if user_text else audio_prompt

if final_input or uploaded_file:
    if not final_input:
        final_input = "Analysiere diesen Brief und sag mir, was ich tun muss."

    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # AKTUALISIERTES MODELL (90b statt 11b)
    model_name = "llama-3.2-90b-vision-preview" if uploaded_file else "llama-3.3-70b-versatile"
    
    messages_payload = [{"role": "system", "content": system_instruction}]
    
    # Historie (nur Text)
    for m in st.session_state.messages[:-1]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    
    # Bild-Payload
    if uploaded_file:
        img_b64 = encode_image(uploaded_file)
        messages_payload.append({
            "role": "user",
            "content": [
                {"type": "text", "text": final_input},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        })
    else:
        messages_payload.append({"role": "user", "content": final_input})

    with st.spinner("🤖 Ich lese den Brief..."):
        try:
            res = client.chat.completions.create(model=model_name, messages=messages_payload)
            ai_text = res.choices[0].message.content
            
            with st.chat_message("assistant"):
                st.markdown(ai_text)
            st.session_state.messages.append({"role": "assistant", "content": ai_text})
            
            # DB Speicher
            try:
                supabase.table("brief_summaries").insert({"summary_text": ai_text[:300]}).execute()
            except: pass
            
        except Exception as e:
            st.error(f"Fehler: Das KI-Modell antwortet nicht richtig. Probier es gleich nochmal. ({e})")
