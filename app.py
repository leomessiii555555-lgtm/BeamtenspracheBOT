import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import smtplib
from email.message import EmailMessage
import base64

# --- 1. KONFIGURATION ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    APP_URL = st.secrets["APP_URL"]
    
    SMTP_SERVER = "smtp.resend.com"
    SMTP_PORT = 465
    SMTP_USER = "resend"
    SMTP_PASSWORD = st.secrets["RESEND_API_KEY"] 
    SENDER_MAIL = "onboarding@resend.dev" 
except Exception as e:
    st.error("Konfigurationsfehler in den Secrets!")
    st.stop()

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. FUNKTIONEN ---
def bild_zu_base64(bild_datei):
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    try:
        msg = EmailMessage()
        msg.set_content(f"Dein Beamten-Zähmer Ergebnis:\n\n{inhalt}")
        msg['Subject'] = "Analyse deines Behörden-Schreibens"
        msg['From'] = SENDER_MAIL
        msg['To'] = ziel_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except: pass

def hole_profil(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None

# --- 3. AUTH-LOGIK ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer")
    tab1, tab2 = st.tabs(["Anmelden", "Konto erstellen"])
    with tab2:
        r_mail = st.text_input("E-Mail")
        r_pw = st.text_input("Passwort", type="password")
        if st.button("Registrieren"):
            try:
                supabase.auth.sign_up({"email": r_mail, "password": r_pw})
                st.success("Konto angelegt! Bitte E-Mail bestätigen.")
            except Exception as e: st.error(f"Fehler: {e}")
    with tab1:
        l_mail = st.text_input("E-Mail", key="l_m")
        l_pw = st.text_input("Passwort", type="password", key="l_p")
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_mail, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login fehlgeschlagen. Mail bestätigt?")
    st.stop()

# --- 4. NEUES CHAT-LAYOUT ---

# Sidebar: Nur für das Bild und Profil
with st.sidebar:
    st.title("📸 Brief-Scan")
    uploaded_file = st.file_uploader("Foto hochladen", type=["jpg", "png", "jpeg"])
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

# Hauptbereich: Chat-Fenster
st.title("🛡️ Der Beamten-Zähmer")
st.caption("Ich helfe dir bei Briefen von Ämtern. Mathe oder Fußball ignoriere ich.")

# Chat-Verlauf Initialisierung
if "messages" not in st.session_state:
    st.session_state.messages = []

# Verlauf anzeigen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Eingabe unten (Text & Mikrofon-Icon ist im Browser-Input integriert)
prompt = st.chat_input("Schreib mir oder nutze das Mikrofon deiner Tastatur...")

if prompt or uploaded_file:
    # Falls ein Bild hochgeladen wurde, wird es verarbeitet
    image_b64 = bild_zu_base64(uploaded_file) if uploaded_file else None
    
    # Nutzer-Nachricht anzeigen
    with st.chat_message("user"):
        st.markdown(prompt if prompt else "Brief-Analyse angefordert...")
    
    st.session_state.messages.append({"role": "user", "content": prompt if prompt else "Bild hochgeladen"})

    with st.chat_message("assistant"):
        with st.spinner("Ich lese das für dich..."):
            # SYSTEM PROMPT: Hier liegen die Regeln!
            system_rules = """Du bist der 'Beamten-Zähmer'. 
            REGELN:
            1. Antworte NUR auf Fragen zu Behörden, Briefen, Ämtern oder Gesetzen.
            2. Wenn der Nutzer über Mathe, Fußball oder andere Themen redet, sage höflich: 'Das ist kein Behördenthema. Damit verschwende ich keine Zeit, ich zähme lieber den Amtsschimmel für dich!'
            3. Smalltalk über Behörden ist erlaubt (z.B. 'Warum sind die so langsam?').
            4. Wenn du eine Analyse machst: Nutze Bulletpoints, markiere Fristen FETT und erkläre es wie für ein Kind.
            5. Sei humorvoll und frech gegenüber dem Amt, aber hilfsbereit zum Nutzer."""

            messages = [{"role": "system", "content": system_rules}]
            
            # Bild oder Text an OpenAI senden
            if image_b64:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt if prompt else "Analysiere diesen Brief."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]
                })
            else:
                messages.append({"role": "user", "content": prompt})

            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )
            
            full_response = response.choices[0].message.content
            st.markdown(full_response)
            
            # Ergebnis per Mail (optional im Hintergrund)
            sende_ergebnis_email(st.session_state.user.email, full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
