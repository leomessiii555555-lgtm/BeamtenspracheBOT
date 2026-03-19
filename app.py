import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import smtplib
from email.message import EmailMessage

# --- 1. KONFIGURATION ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
    APP_URL = st.secrets["APP_URL"]
    
    # E-Mail Konfiguration
    SMTP_SERVER = st.secrets["SMTP_SERVER"]
    SMTP_PORT = 587  # Empfohlen für STARTTLS
    SMTP_USER = st.secrets["SMTP_USER"]
    SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]
except Exception as e:
    st.error(f"Fehler: Secrets fehlen! ({e})")
    st.stop()

# Initialisierung
openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. KERN-FUNKTIONEN ---

def sende_ergebnis_email(ziel_email, inhalt):
    """Verschickt die Analyse sicher per STARTTLS (Port 587)."""
    try:
        msg = EmailMessage()
        msg.set_content(f"Amtsschimmel-Zähmer Analyse:\n\n{inhalt}")
        msg['Subject'] = "Dein Behörden-Bescheid (Ergebnis)"
        msg['From'] = SMTP_USER
        msg['To'] = ziel_email
        
        # Verbindung mit STARTTLS (Sicherer Standard)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls() 
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"E-Mail Fehler: {e}")
        return False

def hole_user_profil(user_id):
    """Sucht Profil oder legt es an (Wichtig: RLS in Supabase muss 'Insert' erlauben)."""
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        neu = {"id": user_id, "text_count": 0, "is_premium": False}
        supabase.table("profiles").insert(neu).execute()
        return neu
    return res.data[0]

# --- 3. LOGIN & REGISTRIERUNG ---
if "user" not in st.session_state:
    st.session_state.user = None

# PayPal-Logik: Falls Zahlung erfolgreich, Premium setzen und URL säubern
if st.query_params.get("payment") == "success" and "user_id" in st.session_state:
    supabase.table("profiles").update({"is_premium": True}).eq("id", st.session_state.user_id).execute()
    st.success("Premium aktiviert! ✨")
    st.query_params.clear() # Entfernt ?payment=success aus der Adressleiste

if not st.session_state.user:
    st.title("🛡️ Beamten-Roboter: Zugang")
    t1, t2 = st.tabs(["Login", "Konto erstellen"])
    
    with t2:
        r_email = st.text_input("E-Mail Adresse", key="reg_mail")
        r_pw = st.text_input("Passwort wählen", type="password", key="reg_pw")
        if st.button("Jetzt Registrieren"):
            try:
                supabase.auth.sign_up({"email": r_email, "password": r_pw})
                st.info("Bestätigungs-Mail verschickt! Bitte Link klicken, dann einloggen.")
            except Exception as e:
                st.error(f"Registrierung fehlgeschlagen: {e}")

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
                st.error("Login fehlgeschlagen. Mail bestätigt?")
    st.stop()

# --- 4. DASHBOARD ---
daten = hole_user_profil(st.session_state.user_id)
ist_premium = daten["is_premium"]
nutzung = daten["text_count"]

with st.sidebar:
    st.write(f"Nutzer: **{st.session_state.user.email}**")
    st.write("Status: " + ("⭐ PREMIUM" if ist_premium else f"Free: {nutzung}/15"))
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# Paywall-Check
if not ist_premium and nutzung >= 15:
    st.warning("Limit erreicht! Upgrade für unbegrenzte Analysen.")
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
    eingabe = st.text_area("Behördentext hier einfügen:", placeholder="Schreib hier den komplizierten Text rein...")
    
    if st.button("Analysieren & Bescheid senden"):
        if eingabe:
            with st.spinner("KI übersetzt Beamtendeutsch..."):
                ki_res = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Du bist ein hilfreicher Roboter. Erkläre Behördentexte so einfach, dass es ein Kind versteht. Nutze Bulletpoints."},
                        {"role": "user", "content": eingabe}
                    ]
                )
                ergebnis = ki_res.choices[0].message.content
                st.markdown("### Deine Analyse:")
                st.info(ergebnis)
                
                # Mail-Versand
                if sende_ergebnis_email(st.session_state.user.email, ergebnis):
                    st.success("Kopie per E-Mail verschickt!")
                
                # Zähler hochsetzen
                supabase.table("profiles").update({"text_count": nutzung + 1}).eq("id", st.session_state.user_id).execute()
