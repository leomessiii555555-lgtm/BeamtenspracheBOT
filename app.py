import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import resend  # Die neue Library
import base64

# --- 1. KONFIGURATION ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
    
    # API Key für die Resend Library setzen
    resend.api_key = RESEND_API_KEY
    
except Exception as e:
    st.error(f"Fehler beim Laden der Secrets: {e}")
    st.stop()

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. FUNKTIONEN ---

def bild_zu_base64(bild_datei):
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    """Verschickt die Analyse mit der Resend API."""
    try:
        r = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ziel_email,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"""
            <h2>Hallo!</h2>
            <p>Hier ist die Analyse deines Behörden-Schreibens:</p>
            <div style="background: #f4f4f4; padding: 15px; border-radius: 10px;">
                {inhalt.replace('', '<br>')}
            </div>
            <p>Viel Erfolg beim Zähmen des Amts!</p>
            """
        })
        return True
    except Exception as e:
        st.sidebar.error(f"Mail-Fehler: {e}")
        return False

# --- 3. LOGIN-LOGIK ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer")
    t1, t2 = st.tabs(["Login", "Konto erstellen"])
    with t2:
        r_mail = st.text_input("E-Mail")
        r_pw = st.text_input("Passwort", type="password")
        if st.button("Registrieren"):
            supabase.auth.sign_up({"email": r_mail, "password": r_pw})
            st.success("Erstellt! Bitte E-Mail bestätigen.")
    with t1:
        l_mail = st.text_input("E-Mail", key="l_m")
        l_pw = st.text_input("Passwort", type="password", key="l_p")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_mail, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login fehlgeschlagen.")
    st.stop()

# --- 4. CHAT-LAYOUT ---

# Sidebar für Bilder
with st.sidebar:
    st.title("📸 Brief-Scan")
    uploaded_file = st.file_uploader("Foto hochladen", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        st.image(uploaded_file)
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

# Haupt-Chat
st.title("🛡️ Der Beamten-Zähmer")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Eingabe unten
prompt = st.chat_input("Was hat das Amt geschrieben?")

if prompt or uploaded_file:
    with st.chat_message("user"):
        st.markdown(prompt if prompt else "Brief-Analyse angefordert.")
    st.session_state.messages.append({"role": "user", "content": prompt if prompt else "Bild gesendet"})

    with st.chat_message("assistant"):
        with st.spinner("Ich bändige das Deutsch..."):
            # SYSTEM-REGELN
            system_rules = """Du bist der 'Beamten-Zähmer'.
            1. Antworte NUR auf Behörden-Themen.
            2. Mathe, Fußball, Kochen etc. lehnst du frech ab ('Dafür habe ich keine Zeit!').
            3. Analysen: Bulletpoints, Fristen FETT, Sprache für 10-Jährige.
            4. Sei humorvoll und nimm dem Nutzer die Angst vor dem Brief."""

            msgs = [{"role": "system", "content": system_rules}]
            
            if uploaded_file:
                b64 = bild_zu_base64(uploaded_file)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": prompt if prompt else "Analysiere diesen Brief."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
            else:
                msgs.append({"role": "user", "content": prompt})

            response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
            antwort = response.choices[0].message.content
            st.markdown(antwort)
            
            # Mail senden
            sende_ergebnis_email(st.session_state.user.email, antwort)
            st.session_state.messages.append({"role": "assistant", "content": antwort})
