# resources/mail/server.pyw
import socket, threading, os

PORT = 50505

# Go UP two folders: resources/mail → resources → LeModCraft
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAIL_FOLDER = os.path.join(BASE, "mail")

os.makedirs(MAIL_FOLDER, exist_ok=True)

def save_mail(sender_ip, subject, body):
    filename = f"{subject}.txt"
    path = os.path.join(MAIL_FOLDER, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"FROM: {sender_ip}\n\n{body}")

    print(f"[MAIL] Saved: {filename}")

def handle_client(conn, addr):
    try:
        data = conn.recv(4096).decode("utf-8", errors="ignore")
        if not data:
            return

        # Format: subject|body
        parts = data.split("|", 1)
        if len(parts) != 2:
            return

        subject, body = parts
        save_mail(addr[0], subject, body)

        conn.sendall(b"OK")
    except:
        pass

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", PORT))
        s.listen(5)
        print(f"[SERVER] Listening on port {PORT}")

        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
