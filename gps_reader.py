import serial
import threading
import time


class GPSReader:
    def __init__(self, port="/dev/serial0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.last_location = None
        self.running = False
        self.thread = None

    def _convert_to_decimal(self, raw_value, direction):
        if not raw_value:
            return None

        try:
            value = float(raw_value)
            degrees = int(value / 100)
            minutes = value - (degrees * 100)
            decimal = degrees + (minutes / 60.0)

            if direction in ["S", "W"]:
                decimal = -decimal

            return decimal

        except ValueError:
            return None

    def _parse_gprmc(self, line):
        parts = line.split(",")

        if len(parts) < 7:
            return

        status = parts[2]

        if status != "A":
            return

        lat = self._convert_to_decimal(parts[3], parts[4])
        lon = self._convert_to_decimal(parts[5], parts[6])

        if lat is not None and lon is not None:
            self.last_location = {
                "lat": lat,
                "lon": lon,
                "maps_link": f"https://www.google.com/maps?q={lat},{lon}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def _read_loop(self):
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                while self.running:
                    line = ser.readline().decode("ascii", errors="ignore").strip()

                    if line.startswith("$GPRMC"):
                        self._parse_gprmc(line)

        except Exception as e:
            print(f"Eroare GPS: {e}")

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        print("[INFO] GPS background pornit.")

    def stop(self):
        self.running = False
        print("[INFO] GPS oprit.")

    def get_last_location(self):
        return self.last_location


if __name__ == "__main__":
    gps = GPSReader()
    gps.start()

    print("Aștept GPS fix... CTRL+C pentru ieșire")

    try:
        while True:
            location = gps.get_last_location()

            if location:
                print(location)

            time.sleep(2)

    except KeyboardInterrupt:
        gps.stop()
        print("Ieșire.")
