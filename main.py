import signal
import sys
import time
import threading
from seeds import Seeds
from log import log
from utils import load_seeds_from_config

seeds = []

def signal_handler(sig, frame):
    print("\nSignal received. Closing seeds gracefully...")
    log("Signal received. Closing seeds gracefully...")
    for seed in seeds:
        seed.close()
    sys.exit(0)


def command_listener():
    while True:
        try:
            cmd = input("Enter command (list/exit): ").strip().lower()
            if cmd == "list":
                print("----------- Peer Lists from All Seeds ----------------")
                for seed in seeds:
                    print(f"Seed {seed.ip}:{seed.port} peer list:")
                    for (ip, port), degree in seed.peer_list.items():
                        print(f"  {ip}:{port} degree: {degree}")
                print("------------------ End of Peer Lists ----------------")
            elif cmd == "exit":
                print("\nExiting...")
                break
            else:
                print("Unknown command. Try 'list' or 'exit'.")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    for ip, port in load_seeds_from_config():
        seed = Seeds(ip, port)
        if seed.creation():
            seeds.append(seed)

    if not seeds:
        print("No seeds created. Exiting...")
        log("No seeds created. Exiting...")
        sys.exit(1)

    command_thread = threading.Thread(target=command_listener, daemon=True)
    command_thread.start()

    while True:
        time.sleep(1)