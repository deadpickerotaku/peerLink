import socket


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def load_seeds_from_config(path="config.txt"):
    seeds = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.count(':') != 1 or line.count('.') != 3:
                continue
            ip, port = line.split(':')
            seeds.append((ip, int(port)))
    return seeds
