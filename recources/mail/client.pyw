# resources/mail/client.pyw
import socket, json, os, subprocess, re   # ⭐ You forgot these two!

PORT = 50505

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTBOX = os.path.join(BASE, "data", "outbox.json")

os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

def get_wifi_ip():
    try:
        output = subprocess.check_output("ipconfig", shell=True).decode(errors="ignore")
        sections = output.split("\r\n\r\n")
        for sec in sections:
            if ("Wireless LAN adapter" in sec) or ("Wi-Fi" in sec) or ("WLAN" in sec):
                match = re.search(r"IPv4 Address[^\:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", sec)
                if match:
                    return match.group(1)
        return "127.0.0.1"
    except:
        return "127.0.0.1"

def load_outbox():
    if not os.path.exists(OUTBOX):
        return []
    return json.load(open(OUTBOX, "r"))

def save_outbox(data):
    json.dump(data, open(OUTBOX, "w"), indent=4)

def send_mail(ip, subject, body):
    try:
        payload = f"{subject}|{body}"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, PORT))
            s.sendall(payload.encode("utf-8"))
            s.recv(1024)
        print(f"[SEND] Delivered to {ip}")
        return True
    except:
        print(f"[SEND] FAILED to {ip}, queued")
        return False

def queue_mail(ip, subject, body):
    out = load_outbox()
    out.append({"ip": ip, "subject": subject, "body": body})
    save_outbox(out)

def retry_outbox():
    out = load_outbox()
    still = []

    for item in out:
        if not send_mail(item["ip"], item["subject"], item["body"]):
            still.append(item)

    save_outbox(still)

if __name__ == "__main__":
    retry_outbox()
