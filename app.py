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
    PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
    APP_URL = st.secrets["APP_URL"]
    
    # Mail-Konfiguration
    SMTP_SERVER = "smtp.resend.com"
    SMTP_PORT = 465
    SMTP_USER = "resend"
    SMTP_PASSWORD = st.secrets["RESEND_API_KEY"] 
    SENDER_MAIL = "onboarding@resend.dev" 
    
except Exception as e:
    st.error(f"Konfigurationsfehler: {e}")
    st.stop()

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. FUNKTIONEN ---

def bild_zu_base64(bild_datei):
    """Konvertiert ein hochgeladenes Bild für die KI."""
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    try:
        msg = EmailMessage()
        msg.set_content(f"Dein Beamten-Roboter Ergebnis:\n\n{inhalt}")
        msg['Subject'] = "Analyse deines Behörden-Bescheids"
        msg['From'] = SENDER_MAIL
        msg['To'] = ziel_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"E-Mail Fehler: {e}")
        return False

def hole_user_profil(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        neu = {"id": user_id, "text_count": 0, "is_premium": False}
        supabase.table("profiles").insert(neu).execute()
        return neu
    return res.data[0]

# --- 3. LOGIN & AUTH ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer Login")
    t1, t2 = st.tabs(["Login", "Registrieren"])
    with t2:
        r_email = st.text_input("E-Mail")
        r_pw = st.text_input("Passwort", type="password")
        if st.button("Konto erstellen"):
            supabase.auth.sign_up({"email": r_email, "password": r_pw})
            st.info("Check dein Postfach!")
    with t1:
        l_email = st.text_input("E-Mail", key="l_e")
        l_pw = st.text_input("Passwort", type="password", key="l_p")
        if st.button("Anmelden"):
            res = supabase.auth.sign_in_with_password({"email": l_email, "password": l_pw})
            st.session_state.user = res.user
            st.rerun()
    st.stop()

# --- 4. HAUPTSEITE ---
profil = hole_user_profil(st.session_state.user.id)
nutzung = profil["text_count"]
ist_premium = profil["is_premium"]

st.title("🛡️ Der Beamten-Roboter")
st.markdown("### Ich zähme den Amtsschimmel für dich!")

# Eingabe-Optionen
tab_text, tab_bild, tab_audio = st.tabs(["📝 Text eingeben", "📸 Foto hochladen", "🎤 Sprache"])

user_input = ""
image_data = None

with tab_text:
    user_input = st.text_area("Kopiere den Text hier rein:", height=150)

with tab_bild:
    uploaded_file = st.file_uploader("Foto vom Brief hochladen", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        st.image(uploaded_file, caption="Dein Brief", width=300)
        image_data = bild_zu_base64(uploaded_file)

with tab_audio:
    st.write("Diese Funktion nutzt die Spracherkennung deines Geräts.")
    audio_input = st.text_input("Klicke auf das Mikrofon deiner Tastatur oder tippe hier kurz:")

# --- 5. ANALYSE LOGIK ---
if st.button("Analyse starten ✨"):
    if not user_input and not image_data:
        st.warning("Bitte gib einen Text ein oder lade ein Foto hoch!")
    elif not ist_premium and nutzung >= 15:
        st.error("Limit erreicht! Bitte auf Premium upgraden.")
    else:
        with st.spinner("Roboter liest und denkt nach..."):
            try:
                # System-Anweisung für den "Beamten-Zähmer"
                system_prompt = """Du bist der 'Beamten-Zähmer'. Deine Aufgabe:
                1. Erkläre den Inhalt des Textes so einfach, dass es ein 10-Jähriger versteht.
                2. Sage klar: Was will die Behörde von mir? (Aktion)
                3. Gibt es eine Frist? Wenn ja, nenne sie fett.
                4. Antworte humorvoll aber präzise. Nutze Bulletpoints."""

                messages = [{"role": "system", "content": system_prompt}]
                
                if image_data:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Was steht in diesem Brief? Analysiere ihn."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                        ]
                    })
                else:
                    messages.append({"role": "user", "content": user_input})

                response = openai_client.chat.completions.create(
                    model="gpt-4o", # gpt-4o kann Bilder sehen!
                    messages=messages
                )
                
                ergebnis = response.choices[0].message.content
                st.markdown("---")
                st.markdown(ergebnis)
                
                # Mail & Counter
                sende_ergebnis_email(st.session_state.user.email, ergebnis)
                supabase.table("profiles").update({"text_count": nutzung + 1}).eq("id", st.session_state.user.id).execute()
                st.success("Analyse fertig und per Mail gesendet!")
                
            except Exception as e:
                st.error(f"Fehler: {e}")

# Sidebar für Logout & Status
with st.sidebar:
    st.write(f"Nutzer: {st.session_state.user.email}")
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()
