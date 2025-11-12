import json
import argparse
import sys, os, requests
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from daemon.weaprous import WeApRous
app = WeApRous()

PEERS = {}
MESSAGES = []
CONNECTED_PEERS = {}

@app.route('/', methods=['GET'])
def index(headers, body):
    with open("www/index.html", "r", encoding="utf-8") as f:
        return f.read(), "text/html"

# ----------------------------------------------------------
# 1. /submit-info → Peer registration
# ----------------------------------------------------------
@app.route('/submit-info', methods=['POST'])
def submit_info(headers, body):
    """
    body: {"ip": "...", "port": 8001}
    """
    print("DEBUG submit-info headers=", headers)
    print("DEBUG submit-info body=", body)
    data = json.loads(body)
    ip = data["ip"]
    port = data["port"]

    key = f"{ip}:{port}"
    PEERS[key] = {"ip": ip, "port": port}

    return json.dumps({"status": "ok"}), "application/json"


# ----------------------------------------------------------
# 2. /get-list → Peer discovery
# ----------------------------------------------------------
@app.route('/get-list', methods=['GET'])
def get_list(headers, body):
    lst = list(PEERS.values())
    return json.dumps({"status": "ok", "peers": lst}), "application/json"


# ----------------------------------------------------------
# 3. /connect-peer → Setup direct P2P connections
# ----------------------------------------------------------
@app.route('/connect-peer', methods=['POST'])
def connect_peer(headers, body):
    """
    body: {"from": {"ip": "127.0.0.1", "port": 8000},
           "to": {"ip": "127.0.0.1", "port": 8001}}
    """
    data = json.loads(body)
    print(f"[Peer] connect-peer: {data}")

    from_peer = data["from"]
    to_peer = data["to"]
    from_key = f"{from_peer['ip']}:{from_peer['port']}"
    to_key = f"{to_peer['ip']}:{to_peer['port']}"

    CONNECTED_PEERS.setdefault(from_key, [])
    CONNECTED_PEERS.setdefault(to_key, [])

    if to_peer not in CONNECTED_PEERS[from_key]:
        CONNECTED_PEERS[from_key].append(to_peer)
    if from_peer not in CONNECTED_PEERS[to_key]:
        CONNECTED_PEERS[to_key].append(from_peer)
    try:
        requests.post(f"http://{to_peer['ip']}:{to_peer['port']}/accept-connection",
                      json={"from": from_peer}, timeout=2)
    except Exception as e:
        print("[Tracker] Connect failed:", e)
    print(f"[Tracker] Updated connections: {CONNECTED_PEERS}")

    return json.dumps({"status": "ok"}), "application/json"

@app.route('/accept-connection', methods=['POST'])
def accept_connection(headers, body):
    data = json.loads(body)
    from_peer = data["from"]
    to_peer = None

    print(f"[Peer] Accepted connection from {from_peer['ip']}:{from_peer['port']}")

    for key in CONNECTED_PEERS.keys():
        if key.endswith(str(from_peer["port"])):
            continue 
    target_key = f"{from_peer['ip']}:{from_peer['port']}"
    CONNECTED_PEERS.setdefault(target_key, [])

    print(f"[Tracker] Current CONNECTED_PEERS: {json.dumps(CONNECTED_PEERS, indent=2)}")

    return json.dumps({"status": "ok"}), "application/json"

@app.route('/get-messages', methods=['GET'])
def get_messages(headers, body):
    data = json.loads()
    print(f"[Peer] Received Message from {data.get('from')}: {data.get('message')}")
    return json.dumps({"status": "received"}), "application/json"

@app.route('/get-connections', methods=['GET'])
def get_connections(headers, body):
    lst = list(CONNECTED_PEERS.values())
    if not lst:
        return json.dumps({"status": "ok", "connected_peers": CONNECTED_PEERS  }), "application/json"
    return json.dumps({"status": "ok", "connected_peers": lst}), "application/json"

# ----------------------------------------------------------
# 4. /broadcast-peer
# ----------------------------------------------------------
@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers, body):
    data = json.loads(body)
    print("[Tracker] Broadcast request:", data)
    return json.dumps({"status": "ok"}), "application/json"


# ----------------------------------------------------------
# 5. /send-peer → Optional direct messaging request
# ----------------------------------------------------------
@app.route('/send-peer', methods=['POST'])
def send_peer(headers, body):
    data = json.loads(body)
    MESSAGES.append(data)
    print("[Tracker] Peer-to-peer send:", data)
    return json.dumps({"status": "ok"}), "application/json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Tracker', description='', epilog='Tracker daemon')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=7000)
    args = parser.parse_args()

    app.prepare_address(args.server_ip, args.server_port)
    app.run()
