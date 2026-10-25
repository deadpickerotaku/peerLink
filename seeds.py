import socket
import threading
from typing import Dict, List, Tuple
from log import log
from utils import get_local_ip


class Seeds:
    def __init__(self, ip=None, port=0):
        if ip is None:
            self.ip = get_local_ip()
        else:
            self.ip = ip
        self.port = int(port)
        self.server_socket = None
        self.seed_sockets: List[socket.socket] = []
        self.peer_list: Dict[Tuple[str, int], int] = {}  # (ip, port) -> degree
        self.running_status = True

    def creation(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.ip, self.port))
            if self.port == 0:
                self.port = self.server_socket.getsockname()[1]
            self.server_socket.listen(100)
            msg = f"Seed activated: Listening on {self.ip}:{self.port}"
            print(msg)
            log(msg)
            thread = threading.Thread(target=self.accept_connections, daemon=True)
            thread.start()
            return 1
        except socket.error as e:
            err_msg = f"Failed to activate seed on {self.ip}:{self.port}. Error: {e}"
            print(err_msg)
            return 0

    def accept_connections(self):
        while self.running_status:
            try:
                connection, address = self.server_socket.accept()
                msg = f"Seed({self.ip}:{self.port}) -> New connection from {address[0]}:{address[1]}"
                print(msg)
                log(msg)
                thread = threading.Thread(
                    target=self.handle_peer_connection,
                    args=(connection, address),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running_status:
                    print(f"Seed({self.ip}:{self.port}) -> Error accepting connection: {e}")
                break

    def handle_peer_connection(self, connection: socket.socket, address):
        buffer = ""
        while self.running_status:
            try:
                data = connection.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line:
                        continue
                    if line.startswith("PEER_SERVER:"):
                        try:
                            server_port = int(line.split(":")[1])
                        except ValueError:
                            continue
                        key = (address[0], server_port)
                        if key not in self.peer_list:
                            self.peer_list[key] = 1
                        msg = f"Seed({self.ip}:{self.port}) -> Peer {address[0]}:{server_port} registered with degree 1"
                        print(msg)
                        log(msg)
                        if connection not in self.seed_sockets:
                            self.seed_sockets.append(connection)
                    if line.startswith("REQUEST_PEER_LIST:"):
                        peer_list_str = '\n'.join(
                            f"{ip}:{port}:{degree}"
                            for (ip, port), degree in self.peer_list.items()
                        ) + "\n"
                        connection.sendall(peer_list_str.encode('utf-8'))
                    if line.startswith("DEAD_NODE:"):
                        parts = line.split(":")
                        if len(parts) >= 3:
                            dead_ip = parts[1]
                            try:
                                dead_port = int(parts[2])
                            except ValueError:
                                continue
                            removed = self.peer_list.pop((dead_ip, dead_port), None)
                            if removed is not None:
                                msg = f"Seed({self.ip}:{self.port}) -> Removed dead peer {dead_ip}:{dead_port}"
                            else:
                                msg = f"Seed({self.ip}:{self.port}) -> Dead peer {dead_ip}:{dead_port} not found"
                            print(msg)
                            log(msg)
                    if line.startswith("CONNECTION_UPDATE:"):
                        parts = line.split(":", 4)
                        if len(parts) < 4:
                            continue
                        new_ip = parts[1]
                        try:
                            new_port = int(parts[2])
                            new_degree = int(parts[3])
                        except ValueError:
                            continue
                        connected_peers_str = parts[4] if len(parts) == 5 else ""
                        key = (new_ip, new_port)
                        self.peer_list[key] = max(self.peer_list.get(key, 0), new_degree)
                        if connected_peers_str:
                            for cp in connected_peers_str.split(","):
                                if not cp.strip():
                                    continue
                                try:
                                    cp_ip, cp_port_str = cp.split(":")
                                    cp_port = int(cp_port_str)
                                except ValueError:
                                    continue
                                cp_key = (cp_ip, cp_port)
                                self.peer_list[cp_key] = self.peer_list.get(cp_key, 0) + 1
                        msg = f"Seed({self.ip}:{self.port}) -> CONNECTION_UPDATE from {new_ip}:{new_port}. List: {self.peer_list}"
                        print(msg)
                        log(msg)
            except Exception as e:
                if self.running_status:
                    err_msg = f"Seed({self.ip}:{self.port}) -> Error handling peer: {e}"
                    print(err_msg)
                    log(err_msg)
                break
        if connection:
            connection.close()

    def close(self):
        self.running_status = False
        if self.server_socket:
            try:
                self.server_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.server_socket.close()
            msg = f"Seed server on {self.ip}:{self.port} closed."
            print(msg)
            log(msg)
        for conn in self.seed_sockets:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
