# =========================
# CONFIGURAȚIE SISTEM
# =========================

# Praguri pentru detecția oboselii
EAR_THRESHOLD = 0.25
MAR_THRESHOLD = 0.70

# Număr de cadre consecutive pentru confirmarea alertei
EYE_CLOSED_FRAMES = 15
YAWN_FRAMES = 10

# Timp minim între două notificări WhatsApp, în secunde
WHATSAPP_COOLDOWN_SECONDS = 60

# Pini GPIO Raspberry Pi
LED_ALERT_GPIO = 17
BUZZER_GPIO = 18
LED_SYSTEM_GPIO = 27

# Date Green API / WhatsApp
ID_INSTANCE = "YOUR_GREEN_API_INSTANCE_ID"
API_TOKEN_INSTANCE = "YOUR_GREEN_API_TOKEN"

WHATSAPP_CONTACTS = [
    "407XXXXXXXX",
]