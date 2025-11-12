import json
import socket
import threading
import time
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from daemon.weaprous import WeApRous

# ================================================================
# GLOBAL
# ================================================================
PEER_CONNECTIONS = {}
MESSAGES = []
MY_IP = None
MY_PORT = None
TRACKER_IP = None
TRACKER_PORT = None

# ================================================================
# 1️⃣ Register to tracker
# ================================================================
# def register_to_tracker(ip, port, tracker_ip, tracker_port):
#     body = json.dumps({"ip": ip, "port": port})
#     req = (
#         "POST /submit-info HTTP/1.1\r\n"
#         f"Host: {tracker_ip}:{tracker_port}\r\n"
#         "Content-Type: application/json\r\n"
#         f"Content-Length: {len(body)}\r\n\r\n"
#         f"{body}"
#     )

#     try:
#         s = socket.socket()
#         s.connect((tracker_ip, tracker_port))
#         s.send(req.encode())
#         resp = s.recv(4096).decode(errors="ignore")
#         s.close()
#         print("[Peer] Registered to tracker:", resp.splitlines()[0])
#     except Exception as e:
#         print("[Peer] Register failed:", e)


# ================================================================
# 2️⃣ Peer TCP server (listen HTTP + P2P)
# ================================================================
def handle_client(conn, addr):
    try:
        data = conn.recv(4096).decode(errors="ignore")
        if not data:
            conn.close()
            return

        if data.startswith("GET /") or data.startswith("POST /"):
            handle_http(conn, data)
        else:
            # raw P2P message
            print(f"[P2P] from {addr}: {data}")
            MESSAGES.append({"from": f"{addr}", "content": data})
            conn.send(b"OK")
        conn.close()
    except Exception as e:
        print(f"[Peer] Error from {addr}: {e}")
        conn.close()


def handle_http(conn, request):
    lines = request.split("\r\n")
    first_line = lines[0]
    method, path, *_ = first_line.split(" ")

    # Parse simple body if POST
    if "\r\n\r\n" in request:
        body = request.split("\r\n\r\n", 1)[1]
    else:
        body = ""

    # Serve index.html
    if method == "GET" and path == "/":
        with open("www/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        send_http(conn, 200, html, "text/html")
        return

    # API: /accept-connection (khi peer khác gọi đến)
    if method == "POST" and path == "/accept-connection":
        try:
            data = json.loads(body)
            from_peer = data["from"]
            key = f"{from_peer['ip']}:{from_peer['port']}"
            if key not in PEER_CONNECTIONS:
                PEER_CONNECTIONS[key] = True
                print(f"[Peer] Accepted connection from {key}")
            send_http(conn, 200, json.dumps({"status": "ok"}), "application/json")
        except Exception as e:
            send_http(conn, 400, json.dumps({"error": str(e)}), "application/json")
        return

    # API: /get-messages
    if method == "GET" and path == "/get-messages":
        body_json = json.dumps({"messages": MESSAGES[-50:]})
        send_http(conn, 200, body_json, "application/json")
        return

    # API: /send-message
    if method == "POST" and path == "/send-message":
        try:
            data = json.loads(body)
            msg = f"{data['sender']}: {data['content']}"
            MESSAGES.append(data)
            broadcast(msg)
            send_http(conn, 200, json.dumps({"status": "ok"}), "application/json")
        except Exception as e:
            send_http(conn, 400, json.dumps({"error": str(e)}), "application/json")
        return

    # Fallback
    send_http(conn, 404, "<h1>404 Not Found</h1>", "text/html")


def send_http(conn, code, body, content_type="text/plain"):
    conn.sendall(
        f"HTTP/1.1 {code} OK\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body.encode())}\r\n"
        "Connection: close\r\n\r\n"
        f"{body}".encode()
    )


def tcp_server():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((MY_IP, MY_PORT))
    srv.listen(10)
    print(f"[Peer] Listening (HTTP + P2P) on {MY_IP}:{MY_PORT}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


# ================================================================
# 3️⃣ Tracker sync
# ================================================================
def get_peer_list(tracker_ip, tracker_port):
    req = (
        "GET /get-list HTTP/1.1\r\n"
        f"Host: {tracker_ip}:{tracker_port}\r\n"
        "Connection: close\r\n\r\n"
    )
    try:
        s = socket.socket()
        s.connect((tracker_ip, tracker_port))
        s.send(req.encode())
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        body = resp.decode(errors="ignore").split("\r\n\r\n", 1)[1]
        return json.loads(body).get("peers", [])
    except Exception as e:
        print("[Peer] Tracker sync error:", e)
        return []

# ================================================================
# 4️⃣ Broadcast
# ================================================================
def broadcast(message):
    dead = []
    for key, s in PEER_CONNECTIONS.items():
        try:
            s.send(message.encode())
        except Exception:
            dead.append(key)
    for k in dead:
        del PEER_CONNECTIONS[k]


# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--tracker-ip", required=True)
    parser.add_argument("--tracker-port", type=int, required=True)
    args = parser.parse_args()

    MY_IP = args.ip
    MY_PORT = args.port
    TRACKER_IP = args.tracker_ip
    TRACKER_PORT = args.tracker_port

    print(f"[Peer] Starting peer {MY_IP}:{MY_PORT}")
    # register_to_tracker(MY_IP, MY_PORT, TRACKER_IP, TRACKER_PORT)

    threading.Thread(target=tcp_server, daemon=True).start()

    while True:
        time.sleep(1)
