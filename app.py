import streamlit as st
import resend
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. SETUP & GEHEIMNISSE ---
try:
    # Wir laden alles aus den Secrets
    R_KEY = st.secrets["RESEND_API_KEY"]
    O_KEY = st.secrets["OPENAI_API_KEY"]
    S_URL = st.secrets["SUPABASE_URL"]
    S_KEY = st.secrets["SUPABASE_KEY"]

    # Port 8501 für den Rücksprung nach der Mail-Bestätigung
    REDIRECT_URL = "http://localhost:8501"

    # Verbindung zu den Diensten aufbauen
    resend.api_key = R_KEY
    openai_client = OpenAI(api_key=O_KEY)
    supabase: Client = create_client(S_URL, S_KEY)
except Exception as e:
    st.error(f"Konfigurations-Fehler: {e}")
    st.stop()

# --- 2. WERKZEUGE (MAIL & BILD) ---

def bild_zu_base64(bild_datei):
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    """Versendet die KI-Analyse über Resend."""
    try:
        # ACHTUNG: onboarding@resend.dev schickt NUR an deine eigene E-Mail!
        r = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ziel_email,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"<h3>Deine Analyse:</h3><p>{inhalt.replace(chr(10), '<br>')}</p>"
        })
        st.toast(f"Resend hat die Mail akzeptiert! ID: {r.get('id')}", icon="📧")
        return True
    except Exception as e:
        st.sidebar.error(f"Resend-Fehler: {e}")
        return False

# --- 3. LOGIN & REGISTRIERUNG ---

if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer Login")
    tab1, tab2 = st.tabs(["Anmelden", "Konto erstellen"])
    
    with tab2:
        r_mail = st.text_input("Deine E-Mail", key="r_m")
        r_pw = st.text_input("Passwort (min. 6 Zeichen)", type="password", key="r_p")
        if st.button("Jetzt Registrieren"):
            try:
                # WICHTIG: Hier sagen wir Supabase, dass es auf 8501 zurück soll
                auth_res = supabase.auth.sign_up({
                    "email": r_mail, 
                    "password": r_pw,
                    "options": {"email_redirect_to": REDIRECT_URL}
                })
                if auth_res.user:
                    st.success(f"User-Konto angelegt! Schau jetzt in dein Postfach: {r_mail}")
                    st.info("Falls keine Mail kommt: Prüf den Spam oder warte 5 Min (Rate-Limit).")
                else:
                    st.warning("Konto konnte nicht erstellt werden. Vielleicht existiert es schon?")
            except Exception as e:
                st.error(f"Fehler bei Supabase: {e}")

    with tab1:
        l_mail = st.text_input("E-Mail", key="l_m")
        l_pw = st.text_input("Passwort", type="password", key="l_p")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_mail, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error("Login fehlgeschlagen. Mail bestätigt? Passwort korrekt?")
    st.stop()

# --- 4. HAUPT-INTERFACE ---

with st.sidebar:
    st.title("📸 Brief scannen")
    u_file = st.file_uploader("Bild hochladen", type=["jpg", "png", "jpeg"])
    if u_file:
        st.image(u_file)
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

st.title("🛡️ Der Beamten-Zähmer")
st.write(f"Eingeloggt als: {st.session_state.user.email}")

if "chat" not in st.session_state:
    st.session_state.chat = []

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# CHAT INPUT GANZ UNTEN
prompt = st.chat_input("Was hat das Amt geschrieben?")

if prompt or u_file:
    with st.chat_message("user"):
        txt = prompt if prompt else "Analysiere das Bild."
        st.markdown(txt)
    st.session_state.chat.append({"role": "user", "content": txt})

    with st.chat_message("assistant"):
        with st.spinner("Ich bändige das Deutsch..."):
            system_msg = "Du bist der Beamten-Zähmer. Antworte nur auf Behördenkram. Fristen FETT markieren."
            msgs = [{"role": "system", "content": system_msg}]
            
            if u_file:
                base64_img = bild_zu_base64(u_file)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": txt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]})
            else:
                msgs.append({"role": "user", "content": txt})

            try:
                # KI ANTWORT
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                
                # MAIL SENDEN
                sende_ergebnis_email(st.session_state.user.email, antwort)
                
                st.session_state.chat.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")
