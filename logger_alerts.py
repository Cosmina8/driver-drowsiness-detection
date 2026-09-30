from datetime import datetime


LOG_FILE = "alerts_log.txt"


def log_alert(alert_type, location_data, whatsapp_sent):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if location_data:
        lat = location_data.get("lat", "N/A")
        lon = location_data.get("lon", "N/A")
        maps_link = location_data.get("maps_link", "N/A")
    else:
        lat = "N/A"
        lon = "N/A"
        maps_link = "N/A"

    status_whatsapp = "TRIMIS" if whatsapp_sent else "NETRIMIS"

    log_line = (
        f"[{timestamp}] "
        f"Tip alerta: {alert_type} | "
        f"WhatsApp: {status_whatsapp} | "
        f"Lat: {lat} | "
        f"Lon: {lon} | "
        f"Maps: {maps_link}\n"
    )

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(log_line)

    print("[INFO] Alertă salvată în alerts_log.txt")