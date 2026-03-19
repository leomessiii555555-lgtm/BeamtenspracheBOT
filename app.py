import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import smtplib
from email.message import EmailMessage

# --- 1. KONFIGURATION (Lädt alles sicher aus den Streamlit Secrets) ---
try:
    # KI & Datenbank Schnittstellen
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    
    # PayPal & App Link
    PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
    APP_URL = st.secrets["APP_URL"]
    
    # E-Mail Account des Roboters (für den Versand)
    SMTP_SERVER = st.secrets["SMTP_SERVER"]
    SMTP_PORT = 465
    SMTP_USER = st.secrets["SMTP_USER"]
    SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]
except Exception:
    st.error("Fehler: Secrets nicht konfiguriert! Bitte Keys in Streamlit Cloud eintragen.")
    st.stop()

# Initialisierung der Dienste
openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. KERN-FUNKTIONEN ---

def sende_ergebnis_email(ziel_email, inhalt):
    """Verschickt die KI-Analyse als offizielle E-Mail."""
    try:
        msg = EmailMessage()
        msg.set_content(f"Amtsschimmel-Zähmer Analyse:\n\n{inhalt}")
        msg['Subject'] = "Dein Behörden-Bescheid (Ergebnis)"
        msg['From'] = SMTP_USER
        msg['To'] = ziel_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except:
        return False

def hole_user_profil(user_id):
    """Sucht den User in der Datenbank oder legt ihn neu an."""
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if len(res.data) == 0:
        neu = {"id": user_id, "text_count": 0, "is_premium": False}
        supabase.table("profiles").insert(neu).execute()
        return neu
    return res.data[0]

# --- 3. LOGIN & REGISTRIERUNG (Alle E-Mails) ---
if "user" not in st.session_state:
    st.session_state.user = None

# PayPal Rückleitung prüfen
if st.query_params.get("payment") == "success" and st.session_state.get("user_id"):
    supabase.table("profiles").update({"is_premium": True}).eq("id", st.session_state.user_id).execute()
    st.success("Premium aktiviert! 🎉")

if not st.session_state.user:
    st.title("🛡️ Beamten-Roboter: Zugang")
    t1, t2 = st.tabs(["Login", "Konto erstellen"])
    
    with t2:
        r_email = st.text_input("E-Mail Adresse")
        r_pw = st.text_input("Passwort", type="password", key="reg")
        if st.button("Jetzt Registrieren"):
            supabase.auth.sign_up({"email": r_email, "password": r_pw})
            st.info("Bestätigungs-Mail verschickt! Link klicken, dann einloggen.")

    with t1:
        l_email = st.text_input("E-Mail", key="log_e")
        l_pw = st.text_input("Passwort", type="password", key="log_p")
        if st.button("Anmelden"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_email, "password": l_pw})
                st.session_state.user = res.user
                st.session_state.user_id = res.user.id
                st.rerun()
            except:
                st.error("Fehler beim Login.")
    st.stop()

# --- 4. DASHBOARD & PAYWALL ---
user_id = st.session_state.user_id
daten = hole_user_profil(user_id)
ist_premium = daten["is_premium"]
nutzung = daten["text_count"]

with st.sidebar:
    st.write(f"Konto: {st.session_state.user.email}")
    st.write("Status: " + ("PREMIUM ✨" if ist_premium else f"Free: {nutzung}/15"))
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

if not ist_premium and nutzung >= 15:
    st.warning("Limit erreicht! Schalte unbegrenzte Nutzung für 2€ frei.")
    paypal_btn = f"""
        <div id="paypal-button-container"></div>
        <script src="https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}&currency=EUR"></script>
        <script>
            paypal.Buttons({{
                createOrder: function(data, actions) {{ return actions.order.create({{ purchase_units: [{{ amount: {{ value: '2.00' }} }}] }}); }},
                onApprove: function(data, actions) {{ return actions.order.capture().then(function() {{ window.location.href = "{APP_URL}?payment=success"; }}); }}
            }}).render('#paypal-button-container');
        </script> """
    st.components.v1.html(paypal_btn, height=500)
else:
    # --- 5. HAUPTFUNKTION ---
    st.title("🛡️ Der Beamten-Roboter")
    eingabe = st.text_area("Behördentext hier einfügen:")
    
    if st.button("Analysieren & Bescheid senden"):
        if eingabe:
            with st.spinner("Analysiere..."):
                # KI Antwort generieren
                ki_res = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": "Du bist ein Beamten-Roboter. Erkläre Behördentexte extrem einfach."},
                              {"role": "user", "content": eingabe}]
                )
                ergebnis = ki_res.choices[0].message.content
                st.info(ergebnis)
                
                # E-Mail senden
                if sende_ergebnis_email(st.session_state.user.email, ergebnis):
                    st.success("Ergebnis wurde auch per E-Mail gesendet!")
                
                # Zähler in Datenbank erhöhen
                supabase.table("profiles").update({"text_count": nutzung + 1}).eq("id", user_id).execute()
