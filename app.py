import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import httpx
import base64
import smtplib
from email.message import EmailMessage

# --- 1. SETUP & KONFIGURATION ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
    APP_URL = st.secrets["APP_URL"]
    
    # E-Mail Zugangsdaten (In Streamlit Secrets anlegen!)
    SMTP_SERVER = st.secrets["SMTP_SERVER"]
    SMTP_PORT = 465
    SMTP_USER = st.secrets["SMTP_USER"]
    SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]
except KeyError as e:
    st.error(f"Fehler: Secret {e} nicht gefunden! Bitte in Streamlit Cloud eintragen.")
    st.stop()

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. HILFSFUNKTIONEN ---

def sende_email(empfaenger, betreff, inhalt):
    """Verschickt eine normale E-Mail (kein Gmail-Spezial-Zwang)."""
    try:
        msg = EmailMessage()
        msg.set_content(inhalt)
        msg['Subject'] = betreff
        msg['From'] = SMTP_USER
        msg['To'] = empfaenger

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"E-Mail-Fehler: {e}")
        return False

def get_user_stats(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if len(res.data) == 0:
        new_user = {"id": user_id, "text_count": 0, "image_count": 0, "is_premium": False}
        supabase.table("profiles").insert(new_user).execute()
        return new_user
    return res.data[0]

def update_count(user_id, column):
    current_stats = get_user_stats(user_id)
    new_val = current_stats[column] + 1
    supabase.table("profiles").update({column: new_val}).eq("id", user_id).execute()

def set_premium(user_id):
    supabase.table("profiles").update({"is_premium": True}).eq("id", user_id).execute()

# --- 3. AUTHENTIFIZIERUNG & PAYPAL CHECK ---
if "user" not in st.session_state:
    st.session_state.user = None

query_params = st.query_params
if query_params.get("payment") == "success" and st.session_state.get("user_id"):
    set_premium(st.session_state.user_id)
    st.success("Zahlung erfolgreich! Du bist jetzt Premium-Nutzer! 🎉")
    st.balloons()

if not st.session_state.user:
    st.title("🛡️ Amtsschimmel-Zähmer")
    if st.button("Mit Google anmelden"):
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirect_to": APP_URL}
        })
        st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
        st.stop()
    
    try:
        session = supabase.auth.get_session()
        if session:
            st.session_state.user = session.user
            st.session_state.user_id = session.user.id
            st.rerun()
    except:
        st.stop()
else:
    # --- 4. HAUPT-LOGIK (EINGELOGGT) ---
    user_id = st.session_state.user_id
    stats = get_user_stats(user_id)
    is_premium = stats["is_premium"]
    total_usage = stats["text_count"] + stats["image_count"]

    with st.sidebar:
        st.write(f"Eingeloggt: **{st.session_state.user.email}**")
        st.write("Status: " + ("PREMIUM ✨" if is_premium else f"Versuche: {total_usage}/15"))
        if st.button("Abmelden"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

    if not is_premium and total_usage >= 15:
        st.warning("⚠️ Limit erreicht! Schalte unbegrenzte Nutzung für einmalig 2€ frei.")
        paypal_html = f"""
            <div id="paypal-button-container"></div>
            <script src="https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}&currency=EUR"></script>
            <script>
                paypal.Buttons({{
                    createOrder: function(data, actions) {{
                        return actions.order.create({{
                            purchase_units: [{{ amount: {{ value: '2.00' }} }}]
                        }});
                    }},
                    onApprove: function(data, actions) {{
                        return actions.order.capture().then(function(details) {{
                            window.location.href = "{APP_URL}?payment=success";
                        }});
                    }}
                }}).render('#paypal-button-container');
            </script>
        """
        st.components.v1.html(paypal_html, height=500)
    else:
        st.title("🛡️ Beamtendeutsch-Übersetzer")
        tab1, tab2 = st.tabs(["📝 Text prüfen", "🎙️ Sprachnachricht"])

        with tab1:
            input_text = st.text_area("Füge hier den Behördentext ein:")
            if st.button("Übersetzen & Bescheid senden"):
                if input_text:
                    # Platzhalter für KI-Logik
                    ergebnis = f"Dein Bescheid kurz gefasst: Das Amt möchte Dokumente von dir."
                    
                    st.write("### Ergebnis:")
                    st.info(ergebnis)
                    
                    # E-Mail automatisch senden
                    mail_inhalt = f"Hallo,\n\nhier ist die Übersetzung deines Dokuments:\n\n{ergebnis}\n\nDein Amtsschimmel-Zähmer"
                    if sende_email(st.session_state.user.email, "Deine Dokumenten-Übersetzung", mail_inhalt):
                        st.success("Bescheid wurde per E-Mail versendet! 📧")
                    
                    update_count(user_id, "text_count")

        with tab2:
            st.write("Hier kannst du Sprachnachrichten aufnehmen (Funktion einfügen).")
