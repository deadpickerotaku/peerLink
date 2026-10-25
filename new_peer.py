import sys
import time
import signal
from peers import Peers
from log import log
from utils import load_seeds_from_config

seeds_connection = []

def signal_handler(sig, frame):
    global peer_instance
    msg = "Termination signal received, peer is dead."
    print(msg)
    log(msg)
    peer_instance.close()
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        msg = "Usage: python new_peer.py <port>"
        print(msg)
        log(msg)
        sys.exit(1)
    try:
        assigned_port = int(sys.argv[1])
    except ValueError:
        msg = "Invalid port number."
        print(msg)
        log(msg)
        sys.exit(1)

    seeds_connection = load_seeds_from_config()

    peer_instance = Peers(None, assigned_port)
    peer_instance.creation()
    time.sleep(1)
    peer_instance.connect(seeds_connection)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    msg = f"Peer running on {peer_instance.ip}:{peer_instance.port}."
    print(msg)
    log(msg)

    while True:
        time.sleep(1)