import requests
from config import ID_INSTANCE, API_TOKEN_INSTANCE, WHATSAPP_CONTACTS


def send_whatsapp_alert(location_data):
    if not location_data:
        print("[WARN] Nu există locație GPS validă.")
        return False

    url = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"

    message_text = (
        "⚠️ ALERTĂ SISTEM DETECTARE OBOSEALĂ ȘOFER\n\n"
        "Sistemul a detectat semne de oboseală la volan.\n\n"
        f"Data/Ora: {location_data['timestamp']}\n"
        f"Latitudine: {location_data['lat']}\n"
        f"Longitudine: {location_data['lon']}\n\n"
        f"Locație Google Maps:\n{location_data['maps_link']}"
    )

    success = True

    for phone_number in WHATSAPP_CONTACTS:
        payload = {
            "chatId": f"{phone_number}@c.us",
            "message": message_text
        }

        try:
            response = requests.post(url, json=payload, timeout=8)

            if response.status_code == 200:
                print(f"[OK] Alertă WhatsApp trimisă către {phone_number}")
            else:
                print(f"[EROARE WA] {response.status_code} | {response.text}")
                success = False

        except Exception as e:
            print(f"[EROARE REȚEA WA] {e}")
            success = False

    return success