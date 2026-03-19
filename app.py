import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import smtplib
from email.message import EmailMessage

# --- 1. SETUP: TRAG HIER DEINE DATEN EIN ---
# Achtung: Diese Daten vor dem Hochladen auf GitHub löschen!
OPENAI_API_KEY = "DEIN_OPENAI_KEY"
SUPABASE_URL = "https://DEINE_ID.supabase.co"
SUPABASE_KEY = "DEIN_SUPABASE_KEY"
PAYPAL_CLIENT_ID = "DEINE_PAYPAL_ID"
APP_URL = "https://deine-app.streamlit.app"

# Deine E-Mail Daten (für den Versand der Ergebnisse)
SMTP_SERVER = "smtp.gmx.net" # oder smtp.web.de etc.
SMTP_PORT = 465
SMTP_USER = "deine-mail@gmx.de"
SMTP_PASSWORD = "dein-app-passwort"

# Clients starten
openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. FUNKTIONEN ---

def sende_bescheid_mail(user_email, inhalt):
    try:
        msg = EmailMessage()
        msg.set_content(f"Amtsschimmel-Zähmer Analyse:\n\n{inhalt}")
        msg['Subject'] = "Dein Behörden-Bescheid"
        msg['From'] = SMTP_USER
        msg['To'] = user_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Mail-Fehler: {e}")
        return False

def get_user_stats(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if len(res.data) == 0:
        new_user = {"id": user_id, "text_count": 0, "image_count": 0, "is_premium": False}
        supabase.table("profiles").insert(new_user).execute()
        return new_user
    return res.data[0]

# --- 3. LOGIN & REGISTRIERUNG ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Roboter Login")
    t1, t2 = st.tabs(["Login", "Registrieren"])
    
    with t2:
        reg_mail = st.text_input("E-Mail")
        reg_pw = st.text_input("Passwort", type="password", key="r_pw")
        if st.button("Konto erstellen"):
            supabase.auth.sign_up({"email": reg_mail, "password": reg_pw})
            st.info("Bestätigungs-Mail gesendet!")
            
    with t1:
        log_mail = st.text_input("E-Mail", key="l_m")
        log_pw = st.text_input("Passwort", type="password", key="l_p")
        if st.button("Einloggen"):
            res = supabase.auth.sign_in_with_password({"email": log_mail, "password": log_pw})
            st.session_state.user = res.user
            st.session_state.user_id = res.user.id
            st.rerun()
    st.stop()

# --- 4. HAUPTTEIL ---
user_id = st.session_state.user_id
stats = get_user_stats(user_id)
is_premium = stats["is_premium"]
nutzung = stats["text_count"] + stats["image_count"]

# Paywall (2€ via PayPal)
if not is_premium and nutzung >= 15:
    st.warning("Limit erreicht! Schalte Premium frei.")
    # Hier der PayPal Button (HTML/JS)
    st.write("PayPal Button hier...") 
else:
    st.title("🛡️ Der Beamten-Roboter")
    txt = st.text_area("Behördentext:")
    
    if st.button("Analysieren"):
        if txt:
            # KI Analyse
            resp = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": f"Erklär das einfach: {txt}"}]
            )
            antwort = resp.choices[0].message.content
            st.success(antwort)
            
            # Mail senden
            sende_bescheid_mail(st.session_state.user.email, antwort)
            
            # Counter hochsetzen
            new_count = stats["text_count"] + 1
            supabase.table("profiles").update({"text_count": new_count}).eq("id", user_id).execute()
