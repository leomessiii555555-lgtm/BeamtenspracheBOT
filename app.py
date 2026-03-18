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
    st.error("API-Key Fehler in den Secrets!")
    st.stop()

# --- 2. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.write("Spar-Modus: AKTIV ✅")
    uploaded_file = st.file_uploader("📸 Neuen Brief scannen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.rerun()

# --- 4. CHAT-HISTORIE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Analysiere Behördenbriefe im Detail. "
    "Erkläre Beamtendeutsch einfach. Antworte mit: 🎯 KLARTEXT, 🔍 DETAILS, 💰 FRISTEN, ⚡ PLAN."
)

# --- 5. INPUT VERARBEITUNG ---
user_text = st.chat_input("Frage zum Brief...")
final_prompt = user_text

# Sprach-Eingabe (Whisper)
if audio_data and audio_data.get('bytes'):
    if "last_audio_ts" not in st.session_state or st.session_state.last_audio_ts != audio_data['bytes'][:100]:
        audio_bio = io.BytesIO(audio_data['bytes'])
        audio_bio.name = "input.wav"
        trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
        final_prompt = trans.text
        st.session_state.last_audio_ts = audio_data['bytes'][:100]

if final_prompt or uploaded_file:
    # Falls nur ein Bild ohne Text kommt
    current_query = final_prompt if final_prompt else "Analysiere diesen Brief."
    
    # Nutzer-Nachricht im Chat anzeigen
    st.session_state.messages.append({"role": "user", "content": current_query})
    with st.chat_message("user"):
        st.markdown(current_query)

    # --- DER SPAR-PAYLOAD ---
    # 1. System-Anweisung
    messages_payload = [{"role": "system", "content": system_instruction}]
    
    # 2. Alter Text-Verlauf (ohne alte Bilder!)
    for m in st.session_state.messages[:-1]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    
    # 3. Aktuelle Anfrage (mit Bild, falls gerade eins hochgeladen wurde)
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

    # --- ANFRAGE AN OPENAI ---
    with st.spinner("🤖 Analysiere..."):
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload,
                max_tokens=1000
            )
            ai_resp = res.choices[0].message.content
            with st.chat_message("assistant"):
                st.markdown(ai_resp)
            st.session_state.messages.append({"role": "assistant", "content": ai_resp})
            
            # Backup
            try:
                supabase.table("brief_summaries").insert({"summary_text": ai_resp[:300]}).execute()
            except: pass
        except Exception as e:
            st.error(f"Fehler: {e}")
