import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import smtplib
from email.message import EmailMessage
import base64
import re

# --- 1. KONFIGURATION (Laden aus st.secrets) ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
    
    # Resend SMTP Einstellungen
    SMTP_SERVER = "smtp.resend.com"
    SMTP_PORT = 465
    SMTP_USER = "resend"
    # WICHTIG: Der Absender MUSS bei Resend im Testmodus so heißen:
    SENDER_MAIL = "onboarding@resend.dev" 
    
except Exception as e:
    st.error(f"Fehler: Secrets konnten nicht geladen werden! ({e})")
    st.stop()

# Initialisierung
openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(bild_datei):
    """Wandelt das Foto für die KI um."""
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    """Verschickt die Analyse via Resend."""
    try:
        msg = EmailMessage()
        msg.set_content(f"Dein Beamten-Zähmer Ergebnis:\n\n{inhalt}")
        msg['Subject'] = "🛡️ Analyse deines Behörden-Briefs"
        msg['From'] = SENDER_MAIL
        msg['To'] = ziel_email
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SMTP_USER, RESEND_API_KEY)
            server.send_message(msg)
        return True
    except Exception as e:
        # Im Testmodus schlägt dies fehl, wenn ziel_email nicht deine eigene ist
        return False

# --- 3. LOGIN & AUTHENTIFIZIERUNG ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer: Zugang")
    t1, t2 = st.tabs(["Anmelden", "Konto erstellen"])
    
    with t2:
        r_email = st.text_input("E-Mail", key="reg_m")
        r_pw = st.text_input("Passwort", type="password", key="reg_p")
        if st.button("Konto erstellen"):
            try:
                supabase.auth.sign_up({"email": r_email, "password": r_pw})
                st.success("Erstellt! Schau in dein Postfach (auch Spam).")
            except Exception as e: st.error(e)

    with t1:
        l_email = st.text_input("E-Mail", key="log_m")
        l_pw = st.text_input("Passwort", type="password", key="log_p")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_email, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login fehlgeschlagen. Mail bestätigt?")
    st.stop()

# --- 4. DAS NEUE CHAT-LAYOUT ---

# Sidebar für Bild-Upload
with st.sidebar:
    st.title("📸 Brief-Scan")
    uploaded_file = st.file_uploader("Foto vom Brief hochladen", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.image(uploaded_file, caption="Dein Dokument", use_container_width=True)
    
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

# Haupt-Chat-Bereich
st.title("🛡️ Der Beamten-Zähmer")
st.markdown("*Ich übersetze Behörden-Deutsch in Menschen-Deutsch.*")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Verlauf anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Chat Eingabe unten (mit Mikrofon-Support vom System)
prompt = st.chat_input("Schreib mir oder nutze die Spracheingabe deiner Tastatur...")

if prompt or uploaded_file:
    # 1. Nutzer-Nachricht anzeigen
    with st.chat_message("user"):
        anzeige_text = prompt if prompt else "Ich habe ein Bild hochgeladen. Bitte analysiere es."
        st.markdown(anzeige_text)
    
    st.session_state.messages.append({"role": "user", "content": anzeige_text})

    # 2. KI-Antwort generieren
    with st.chat_message("assistant"):
        with st.spinner("Ich bändige den Amtsschimmel..."):
            try:
                # Die Regeln (System Prompt)
                system_rules = """Du bist der 'Beamten-Zähmer'. 
                REGELN:
                1. Antworte NUR auf Themen zu Behörden, Briefen, Ämtern, Verträgen oder Gesetzen.
                2. Wenn der Nutzer über Mathe, Fußball, Kochen oder andere Off-Topic Themen redet, antworte: 'Das ist kein Behördenthema. Damit verschwende ich keine Zeit, ich zähme lieber den Amtsschimmel für dich!'
                3. Bei Analysen: Erkläre es wie für ein Kind, nutze Bulletpoints und markiere Fristen FETT.
                4. Smalltalk über das 'schlimme Amt' ist erlaubt. Sei humorvoll und frech zum Amt, aber loyal zum Nutzer."""

                msgs = [{"role": "system", "content": system_rules}]
                
                # Falls Bild vorhanden
                if uploaded_file:
                    base64_image = bild_zu_base64(uploaded_file)
                    msgs.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt if prompt else "Analysiere dieses Bild."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    })
                else:
                    msgs.append({"role": "user", "content": prompt})

                # API Call
                completion = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=msgs
                )
                
                antwort = completion.choices[0].message.content
                st.markdown(antwort)
                
                # E-Mail im Hintergrund senden
                sende_ergebnis_email(st.session_state.user.email, antwort)
                
                # Im Verlauf speichern
                st.session_state.messages.append({"role": "assistant", "content": antwort})
                
            except Exception as e:
                st.error(f"Fehler: {e}")
