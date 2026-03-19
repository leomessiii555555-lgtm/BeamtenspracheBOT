import streamlit as st
from openai import OpenAI
import base64
import io
from streamlit_mic_recorder import mic_recorder # WICHTIG: Muss in requirements.txt

# --- 1. SETUP & PASSWORT ---
st.set_page_config(page_title="Beamten-Zähmer V3", layout="centered")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🛡️ Zugang zum Beamten-Zähmer")
        pwd_eingabe = st.text_input("Passwort eingeben", type="password")
        if st.button("Einloggen"):
            if pwd_eingabe == st.secrets["MASTER_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Falsches Passwort! 🚫")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. KI INITIALISIERUNG ---
try:
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"Fehler: {e}")
    st.stop()

# --- 3. FUNKTIONEN ---
def bild_zu_base64(datei):
    return base64.b64encode(datei.read()).decode('utf-8')

def transcribe_audio(audio_bytes):
    try:
        # Erstellt ein Datei-ähnliches Objekt aus den Bytes für die API
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "input.mp3"
        response = openai_client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, response_format="text"
        )
        return response
    except Exception as e:
        st.error(f"Fehler bei der Spracherkennung: {e}")
        return None

# --- 4. DIE APP ---
st.title("🛡️ Der Beamten-Zähmer")

with st.sidebar:
    st.header("Brief & Sprache")
    foto = st.file_uploader("Foto vom Brief", type=["jpg", "png", "jpeg"])
    
    st.write("### Sprache aufnehmen")
    # Das echte Mikrofon-Tool
    audio_record = mic_recorder(
        start_prompt="🎤 Aufnahme starten",
        stop_prompt="🛑 Stopp & Senden",
        key='recorder'
    )
    
    st.divider()
    if st.button("Neuer Brief / Chat löschen"):
        for key in list(st.session_state.keys()):
            if key != "authenticated":
                del st.session_state[key]
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mikrofon-Aufnahme verarbeiten
if audio_record and "last_audio_id" not in st.session_state or (audio_record and st.session_state.get("last_audio_id") != audio_record['id']):
    with st.spinner("Ich höre zu..."):
        text = transcribe_audio(audio_record['bytes'])
        if text:
            st.session_state.transcribed_input = text
            st.session_state.last_audio_id = audio_record['id']

# Verlauf anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Was willst du wissen?")

# Audio-Text als Prompt nutzen
if "transcribed_input" in st.session_state:
    prompt = st.session_state.transcribed_input
    del st.session_state.transcribed_input

if prompt or (foto and "foto_verarbeitet" not in st.session_state):
    
    system_prompt = """
    Du bist der 'Beamten-Zähmer'. Ein menschlicher Ratgeber für Behörden-Kram.
    
    DEINE GRENZEN:
    - Antworte NUR auf Fragen zu Behörden, Briefen, Gesetzen oder Anträgen.
    - Wenn der User etwas anderes fragt, sag höflich: 'Verzeiht, edler Fragesteller, doch meine Expertise liegt allein im Reiche der Paragraphen.'

    REGELN FÜR DIE ANALYSE:
    1. Wenn ein NEUES BILD kommt, antworte SOFORT mit dieser Struktur:
       - **Was ist los?**: (Kurze Erklärung)
       - **Forderung**: (Was genau muss getan werden?)
       - **Frist**: (Datum **FETT**)
    
    REGELN FÜR DEN CHAT:
    2. Sei kein Bot. Antworte direkt wie ein Mensch.
    3. Wenn der User eine Zusammenfassung will, nutze Bulletpoints.
    4. Wenn eine normale Frage kommt, antworte im Text ohne den Brief zu wiederholen.
    """

    with st.chat_message("user"):
        anzeige = prompt if prompt else "Hier ist mein Brief zur Analyse."
        st.markdown(anzeige)
    st.session_state.messages.append({"role": "user", "content": anzeige})

    with st.chat_message("assistant"):
        with st.spinner("Zähme Paragraphen..."):
            msgs = [{"role": "system", "content": system_prompt}] + st.session_state.messages
            
            if foto and "foto_verarbeitet" not in st.session_state:
                foto.seek(0)
                b64 = bild_zu_base64(foto)
                msgs[-1] = {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt if prompt else "Analysiere diesen Brief mit Bulletpoints."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
                st.session_state.foto_verarbeitet = True

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")

if not foto and "foto_verarbeitet" in st.session_state:
    del st.session_state.foto_verarbeitet
