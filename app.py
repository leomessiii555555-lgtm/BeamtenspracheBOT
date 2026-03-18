import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import httpx
import base64

# --- 1. SETUP & KONFIGURATION ---
# Diese Daten kommen aus deinen Streamlit Secrets
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
    # DEINE ECHTE APP-URL (WICHTIG!)
    APP_URL = "https://deine-app.streamlit.app" 
except KeyError as e:
    st.error(f"Fehler: Secret {e} nicht gefunden! Bitte in Streamlit Cloud eintragen.")
    st.stop()

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. HILFSFUNKTIONEN FÜR DIE DATENBANK ---
def get_user_stats(user_id):
    """Holt die Zählerstände des Users aus Supabase oder erstellt neuen User."""
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if len(res.data) == 0:
        # Neuer User: Zeile anlegen
        new_user = {"id": user_id, "text_count": 0, "image_count": 0, "is_premium": False}
        supabase.table("profiles").insert(new_user).execute()
        return new_user
    return res.data[0]

def update_count(user_id, column):
    """Erhöht den Text- oder Bildzähler."""
    current_stats = get_user_stats(user_id)
    new_val = current_stats[column] + 1
    supabase.table("profiles").update({column: new_val}).eq("id", user_id).execute()

def set_premium(user_id):
    """Schaltet Premium frei."""
    supabase.table("profiles").update({"is_premium": True}).eq("id", user_id).execute()

# --- 3. AUTHENTIFIZIERUNG (GOOGLE LOGIN) ---
if "user" not in st.session_state:
    st.session_state.user = None

# Prüfen, ob PayPal gerade erfolgreich war (URL Parameter)
query_params = st.query_params
if query_params.get("payment") == "success" and st.session_state.get("user_id"):
    set_premium(st.session_state.user_id)
    st.success("Zahlung erfolgreich! Du bist jetzt Premium-Nutzer! 🎉")
    st.balloons()

# Login-Check
if not st.session_state.user:
    st.title("🛡️ Amtsschimmel-Zähmer")
    st.info("Logge dich mit Google ein, um deine 15 Freiversuche zu nutzen.")
    
    if st.button("Mit Google anmelden"):
        # Login-URL von Supabase generieren
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirect_to": APP_URL}
        })
        st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
        st.stop()

    # Nach der Rückleitung Session abrufen
    try:
        session = supabase.auth.get_session()
        if session:
            st.session_state.user = session.user
            st.session_state.user_id = session.user.id
            st.rerun()
    except:
        st.stop()
else:
    # USER IST EINGELOGGT
    user_id = st.session_state.user_id
    stats = get_user_stats(user_id)
    is_premium = stats["is_premium"]
    total_usage = stats["text_count"] + stats["image_count"]

    # Sidebar mit Status
    with st.sidebar:
        st.write(f"Eingeloggt als: **{st.session_state.user.email}**")
        if is_premium:
            st.success("Status: PREMIUM ✨")
        else:
            st.write(f"Versuche: **{total_usage} / 15**")
        
        if st.button("Abmelden"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

    # --- 4. HAUPTPERFORMACE (PAYWALL CHECK) ---
    if not is_premium and total_usage >= 15:
        st.warning("⚠️ Limit erreicht! Schalte unbegrenzte Nutzung für einmalig 2€ frei.")
        
        # PayPal Button
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
        # HIER KOMMEN DEINE ALTEN FUNKTIONEN (TEXT, BILD, AUDIO) REIN
        st.title("🛡️ Beamtendeutsch-Übersetzer")
        
        tab1, tab2 = st.tabs(["📝 Text/Foto prüfen", "🎙️ Sprachnachricht"])

        with tab1:
            input_text = st.text_area("Füge hier den Behördentext ein:")
            if st.button("Übersetzen"):
                if input_text:
                    # Logik für Übersetzung...
                    update_count(user_id, "text_count")
                    st.write("Hier ist die einfache Erklärung...")

        with tab2:
            st.write("Nimm eine Nachricht auf...")
            # Deine Mic-Recorder Logik...
