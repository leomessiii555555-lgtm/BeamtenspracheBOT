import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP & SICHERHEIT ---
st.set_page_config(page_title="Amtsschimmel-Zähmer PRO", layout="wide", page_icon="🛡️")

# Passwort-Schutz (Damit niemand dein Guthaben verbraucht)
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    st.write("Bitte gib das Passwort ein, um die KI-Analyse zu starten.")
    pw = st.text_input("Passwort:", type="password")
    if pw == "Amt123":  # <--- Hier kannst du dein Passwort ändern!
        st.session_state.auth = True
        st.rerun()
    else:
        if pw: st.error("Falsches Passwort!")
        st.stop()

# Keys aus Streamlit Secrets laden
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Fehler: API-Keys fehlen in den Secrets!")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR (STEUERUNG) ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.success("Modus: Kosteneffizient ✅")
    st.write("---")
    uploaded_file = st.file_uploader("📸 Neuen Brief scannen", type=["jpg", "jpeg", "png"])
    
    # Mikrofon für Spracheingabe
    audio_data = mic_recorder(
        start_prompt="🎤 Frage sprechen", 
        stop_prompt="🛑 Aufnahme stoppen", 
        key='mic'
    )
    
    if st.button("🗑️ Chat-Verlauf löschen"):
        st.session_state.messages = []
        st.session_state.last_audio_ts = None
        st.rerun()

# --- 4. CHAT-LOGIK ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Den bisherigen Chat anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Die Arbeitsanweisung für die KI
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine Aufgabe: Analysiere Behördenbriefe. "
    "REGEL 1: Bei Smalltalk (Danke, Okay, Hallo) antworte kurz, nett und menschlich ohne festes Format. "
    "REGEL 2: Bei Brief-Analysen nutze STRENG dieses Format:\n"
    "## 🎯 KLARTEXT\n(Was ist das? Wer will was?)\n\n"
    "## 🔍 DETAILS\n(Genaue Analyse des Inhalts & Paragraphen)\n\n"
    "## 💰 FRISTEN & ZAHLEN\n- Betrag: [X]\n- Deadline: [Datum]\n\n"
    "## ⚡ SCHLACHTPLAN\n1. [Schritt 1]\n2. [Schritt 2]"
)

# --- 5. INPUT VERARBEITUNG ---
user_input = st.chat_input("Schreibe hier deine Frage...")
final_prompt = user_input

# Falls Sprache genutzt wurde (Whisper-Sperre gegen Doppelsenden)
if audio_data and audio_data.get('bytes'):
    current_audio_hash = audio_data['bytes'][:100]
    if "last_audio_ts" not in st.session_state or st.session_state.last_audio_ts != current_audio_hash:
        with st.spinner("Wandle Sprache in Text um..."):
            audio_bio = io.BytesIO(audio_data['bytes'])
            audio_bio.name = "input.wav"
            transcription = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
            final_prompt = transcription.text
            st.session_state.last_audio_ts = current_audio_hash

# Wenn eine Eingabe (Text/Bild/Sprache) vorliegt
if final_prompt or uploaded_file:
    current_query = final_prompt if final_prompt else "Bitte analysiere diesen Brief detailliert."
    
    # Nachricht im Chat zeigen
    st.session_state.messages.append({"role": "user", "content": current_query})
    with st.chat_message("user"):
        st.markdown(current_query)

    # --- SPAR-MODUS PAYLOAD ---
    messages_payload = [{"role": "system", "content": system_instruction}]
    
    # Text-Verlauf mitschicken (OHNE alte Bilder, um Geld zu sparen)
    for m in st.session_state.messages[:-1]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    
    # Aktuelle Nachricht: Mit Bild, falls gerade eines hochgeladen wurde
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
    with st.spinner("🤖 Analysiere..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload,
                max_tokens=1000,
                temperature=0.7
            )
            answer = response.choices[0].message.content
            
            with st.chat_message("assistant"):
                st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # Optional: Backup in Supabase (nur die ersten 300 Zeichen)
            try:
                supabase.table("brief_summaries").insert({"summary_text": answer[:300]}).execute()
            except:
                pass
                
        except Exception as e:
            st.error(f"KI-Fehler: {e}")
