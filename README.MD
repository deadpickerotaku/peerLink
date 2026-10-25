# Peer-to-Peer Network Simulation

A simulation of a decentralized peer-to-peer network built entirely in Python using raw TCP sockets and threads — no third-party networking libraries. The project demonstrates core distributed systems concepts: seed-based peer discovery, preferential attachment for topology formation, gossip-based message propagation, and PING/PONG liveness detection with automatic dead peer eviction.

Built for learning purposes.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Prerequisites](#prerequisites)
- [How to Run](#how-to-run)
- [Protocol Reference](#protocol-reference)
- [Constants and Tuning](#constants-and-tuning)
- [Log Output](#log-output)
- [Known Limitations](#known-limitations)

---

## Overview

The simulation models two types of nodes:

**Seed nodes** act as bootstrap registries. They do not participate in the P2P network directly. When a new peer joins, it connects to seeds to register itself and obtain a list of existing peers. Seeds maintain each peer's connection degree (how many other peers it is connected to) and remove peers that are reported dead.

**Peer nodes** are the actual participants in the network. Each peer connects to a subset of seeds, discovers other peers, forms connections using a preferential attachment algorithm, exchanges messages via gossip flooding, and continuously monitors its neighbours with heartbeat pings. A peer has a 30% chance of dying at a random time between 30 and 60 seconds after joining — simulating real-world node churn.

---

## Architecture

```
                        ┌─────────────────────┐
                        │      config.txt      │
                        │  (seed ip:port list) │
                        └────────┬─────────────┘
                                 │ read by
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
           ┌─────────┐    ┌─────────┐    ┌─────────┐
           │  Seed 1  │    │  Seed 2  │    │  Seed 3  │
           │:5000     │    │:5001     │    │:5002     │
           └────┬─────┘    └────┬─────┘    └────┬─────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
                  peers connect to (n/2)+1 seeds
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │  Peer A  │◄───────►│  Peer B  │◄───────►│  Peer C  │
    │  :6001   │         │  :6002   │         │  :6003   │
    └──────────┘         └──────────┘         └──────────┘
          ▲                                         │
          └─────────────────────────────────────────┘
                    (preferential attachment graph)
```

Seed nodes and peer nodes run as separate processes. Seed processes are started first via `main.py`. Peer processes are then started individually via `new_peer.py`, one per terminal.

---

## How It Works

### 1. Seed node startup

`main.py` reads `config.txt` and starts a `Seeds` instance for each valid `ip:port` entry. Each seed opens a TCP server socket and spawns a thread to accept incoming connections. A second thread listens for the `list` or `exit` command in the terminal.

### 2. Peer joins the network

When `new_peer.py` is run with a port number, it creates a `Peers` instance and calls `creation()` to open its own TCP server socket bound to `0.0.0.0` (all interfaces). It then calls `connect()`, which performs the full join sequence:

1. Randomly selects `(n/2) + 1` seeds from `config.txt` to connect to.
2. Sends `PEER_SERVER:<port>` to each selected seed to register itself.
3. Sends `REQUEST_PEER_LIST` to each seed and merges the returned peer lists, taking the maximum known degree for any peer that appears in multiple lists.
4. Runs the preferential attachment algorithm to decide which existing peers to connect to.
5. Sends `CONNECTION_UPDATE` to all connected seeds with its new degree and the list of peers it connected to.
6. Starts background threads for gossip sending and PING/PONG liveness checking.
7. Starts the death simulation thread.

### 3. Preferential attachment

For each peer in the merged peer list, a connection probability is computed as:

```
threshold = 1 / (degree + 1)
connect if random() > threshold
```

Peers with a higher degree have a lower threshold, making them more likely to be connected to. This mimics real-world scale-free network formation (similar to Barabási–Albert model). If only one peer exists in the list, the threshold is forced to 0, guaranteeing a connection.

### 4. Handshake

When a peer opens a connection to another peer, it immediately sends `NEW_PEER_SERVER:<port>`. The receiving peer's listener will not process any subsequent messages from that connection until this handshake line is received and the sender's identity `(ip, port)` is recorded.

### 5. Gossip propagation

Each peer generates up to `NUM_MESSAGES` (10) gossip messages, one every `GOSSIP_SEND_INTERVAL` (5) seconds. Each message is a string composed of the current epoch timestamp, the peer's IP and port. Its hash is computed and sent to all connected peers as `GOSSIP:<hash>`.

On receiving a gossip message, a peer checks whether it has already seen that hash. If not, it records the hash and forwards it to all other connected peers (flood with deduplication). This ensures each message is delivered exactly once to every reachable node, regardless of the network topology. Forwarding is handled by a shared thread pool (`ThreadPoolExecutor`, 8 workers) to bound the number of threads spawned under high gossip load.

### 6. Liveness detection (PING/PONG)

Every `PING_INTERVAL` (3) seconds, each peer sends a `PING` to all of its connected peers. On receiving a `PING`, a peer immediately responds with `PONG`. Each peer tracks the last time a `PONG` was received from each neighbour. If no `PONG` arrives within `PING_MAX_WAIT` (5) seconds, a missed ping counter is incremented. After 3 consecutive misses, the remote peer is declared dead:

- It is removed from the local peer connection list.
- It is removed from the local peer list.
- A `DEAD_NODE` message is sent to all connected seeds so they can remove it from the global registry.

### 7. Death simulation

After joining, each peer rolls a random number. With 30% probability, the peer will die at a random time between 30 and 60 seconds. When a peer dies, `isDead` is set to `True` and `close()` is called immediately, which shuts down the server socket and the gossip thread pool. The gossip and ping sender threads check `isDead` and stop. Live neighbours detect the silence through missed PINGs and report the dead peer to seeds.

---

## Project Structure

```
p2p-network-simulation/
│
├── main.py          # Entry point for seed nodes
├── new_peer.py      # Entry point for a single peer node
├── seeds.py         # Seeds class — registry and peer list management
├── peers.py         # Peers class — all peer-side logic
├── log.py           # Logging utility (wraps Python's logging module)
├── utils.py         # Shared helpers: get_local_ip, load_seeds_from_config
│
├── config.txt       # Seed node addresses (one ip:port per line)
├── OUTPUT.txt       # Generated at runtime — all timestamped log entries
│
├── requirements.txt # No third-party dependencies (stdlib only)
└── README.md
```

| File | Responsibility |
|---|---|
| `log.py` | Thin wrapper around Python's `logging` module — writes timestamped entries to `OUTPUT.txt` with thread-safe file handling |
| `utils.py` | Shared utilities used by multiple modules: `get_local_ip()` and `load_seeds_from_config()` |
| `seeds.py` | TCP server that registers peers, serves peer lists, tracks degrees, and evicts dead nodes |
| `main.py` | Reads `config.txt`, creates `Seeds` instances, and provides a CLI to inspect peer lists |
| `peers.py` | Full peer lifecycle: creation, seed connection, peer discovery, gossip, liveness, death |
| `new_peer.py` | Thin launcher that reads `config.txt`, starts a `Peers` instance, and handles OS signals |

---

## Configuration

**`config.txt`** lists the seed nodes that both `main.py` and `new_peer.py` read. Each line must be a valid IPv4 address followed by a port, separated by a colon.

```
127.0.0.1:5000
127.0.0.1:5001
127.0.0.1:5002
```

Lines with incorrect formatting (wrong number of colons, not an IPv4 address) are silently skipped by both entry points.

To run across multiple machines, replace `127.0.0.1` with the actual LAN IP of the machine running the seeds. All peer machines must be able to reach that IP on the listed ports.

---

## Prerequisites

- Python 3.8 or higher
- No third-party packages required — uses only the Python standard library (`socket`, `threading`, `signal`, `random`, `time`)

Verify your Python version:

```bash
python --version
```

---

## How to Run

### Step 1 — Clone the repository

```bash
git clone https://github.com/RounakChoudhary/Peer-Link.git
cd Peer-Link
```

### Step 2 — Verify config.txt

Open `config.txt` and confirm the seed addresses match the machine and ports you intend to use. The default is three seeds on localhost.

### Step 3 — Start the seed nodes

Open a terminal and run:

```bash
python main.py
```

You will see a confirmation line for each seed that starts successfully, for example:

```
Seed activated: Listening on 127.0.0.1:5000
Seed activated: Listening on 127.0.0.1:5001
Seed activated: Listening on 127.0.0.1:5002
Enter command (list/exit):
```

The seed process stays running. You can type `list` at any time to inspect the current peer registry across all seeds, or `exit` to stop the command listener (seeds keep running until you press `Ctrl+C`).

### Step 4 — Start peer nodes

Open a separate terminal for each peer and run:

```bash
python new_peer.py 6001
```

```bash
python new_peer.py 6002
```

```bash
python new_peer.py 6003
```

Each peer will print its connection activity, gossip sends, and pings as it runs. Start at least three peers to observe the network forming and gossip propagating.

### Step 5 — Observe the network

In the seed terminal, type `list` to see which peers are registered and their current degrees:

```
----------- Peer Lists from All Seeds ----------------
Seed 127.0.0.1:5000 peer list:
  127.0.0.1:6001 degree: 2
  127.0.0.1:6002 degree: 1
  127.0.0.1:6003 degree: 2
------------------ End of Peer Lists ----------------
```

In each peer terminal, you will see gossip messages being sent and received, pings going out, and pongs coming back. If a peer dies (simulated), its neighbours will log the detection and notify the seeds.

### Step 6 — Shut down

Press `Ctrl+C` in any peer terminal to cleanly shut down that peer. Press `Ctrl+C` in the seed terminal to shut down all seeds.

---

## Protocol Reference

All messages are plain UTF-8 text terminated with a newline (`\n`). Both seeds and peers use a line-buffered reader that accumulates bytes until a `\n` is found before processing.

### Peer → Seed messages

| Message | Format | Description |
|---|---|---|
| Register | `PEER_SERVER:<port>` | Sent immediately after a peer connects to a seed. Registers the peer's server port. The seed uses the connection's source IP combined with this port to identify the peer. |
| Request list | `REQUEST_PEER_LIST:<port>` | Asks the seed to send back its full peer list. The seed responds synchronously with one `ip:port:degree` entry per line. |
| Connection update | `CONNECTION_UPDATE:<ip>:<port>:<degree>:<peer1_ip>:<peer1_port>,...` | Sent after a peer finishes connecting to other peers. Updates the seed with the peer's new degree and the list of peers it connected to. The seed increments each connected peer's degree by 1. |
| Dead node report | `DEAD_NODE:<ip>:<port>:<timestamp>:<reporter_ip>:<reporter_port>` | Sent when a peer determines a neighbour is dead (3 consecutive missed PINGs). The seed removes the dead peer from its registry. |

### Seed → Peer messages

| Message | Format | Description |
|---|---|---|
| Peer list response | `<ip>:<port>:<degree>\n` (one per line) | Sent synchronously in response to `REQUEST_PEER_LIST`. The peer accumulates chunks until the trailing newline is received. |

### Peer → Peer messages

| Message | Format | Description |
|---|---|---|
| Handshake | `NEW_PEER_SERVER:<port>` | Sent immediately upon connecting to another peer. Required before any other message is processed. |
| Ping | `PING` | Liveness probe sent every `PING_INTERVAL` seconds. |
| Pong | `PONG` | Reply to a `PING`. Resets the missed-ping counter for that connection. |
| Gossip | `GOSSIP:<hash>` | Carries the integer hash of a gossip message. Forwarded to all peers except the sender if the hash has not been seen before. |

---

## Constants and Tuning

These are defined at the top of `peers.py` and can be adjusted to observe different network behaviours.

| Constant | Default | Effect |
|---|---|---|
| `PING_INTERVAL` | `3` seconds | How often each peer sends a PING to all neighbours |
| `PING_MAX_WAIT` | `5` seconds | How long without a PONG before a miss is counted |
| `GOSSIP_SEND_INTERVAL` | `5` seconds | Delay between each gossip message a peer originates |
| `NUM_MESSAGES` | `10` | Total gossip messages each peer generates over its lifetime |

Death simulation parameters are hardcoded in `simulate_death()`:

| Parameter | Value | Effect |
|---|---|---|
| `chance_to_die` | `0.30` | Probability that a given peer will die during the simulation |
| Death window | `30–60` seconds | Random interval after which a dying peer stops responding |

Seed selection uses `(n/2) + 1` seeds from the config, ensuring a majority connection even if some seeds are unavailable.

---

## Log Output

All significant events are written to `OUTPUT.txt` in the working directory. The file is appended to (not overwritten) on each run, so delete or clear it between runs if you want a clean log.

Each entry is formatted as:

```
YYYY-MM-DD HH:MM:SS - <message>
```

Example entries:

```
2024-11-10 14:23:01 - Seed activated: Listening on 127.0.0.1:5000
2024-11-10 14:23:04 - Peer listening on 127.0.0.1:6001
2024-11-10 14:23:04 - Peer(client)(127.0.0.1:6001) -> Connected to seed 127.0.0.1:5000
2024-11-10 14:23:05 - Peer(client)(127.0.0.1:6001) -> Merged peer list: [('127.0.0.1', 6002, 1)]
2024-11-10 14:23:05 - Peer(client)(127.0.0.1:6001) -> Connected to peer 127.0.0.1:6002
2024-11-10 14:23:10 - Peer(client)(127.0.0.1:6001) -> Sent: PING to ('127.0.0.1', 6002)
2024-11-10 14:23:45 - Peer 127.0.0.1:6002 has died (simulated).
2024-11-10 14:23:50 - Peer(client)(127.0.0.1:6001) -> Peer ('127.0.0.1', 6002) is dead
```

`OUTPUT.txt` is listed in `.gitignore` and will not be committed.

---

## Known Limitations

- **No reconnection logic** — if a peer loses its connection to a seed or a neighbour, it does not attempt to reconnect. The peer continues operating with its remaining connections until it or they die.

- **Death detection delay** — when a peer dies, its socket and gossip pool are shut down immediately, but neighbours are not notified directly. Detection relies on the PING/PONG timeout mechanism, which means there is a detection delay of up to `PING_INTERVAL × 3 + PING_MAX_WAIT` seconds (approximately 14 seconds with default settings).

- **Local network only** — IP discovery uses a UDP trick (`connect` to `8.8.8.8:80`) to find the outbound interface IP for identification and logging. The peer server socket binds to `0.0.0.0` so it accepts connections on all interfaces, which means both localhost simulations and LAN deployments work correctly. It will not work across NAT or the public internet without additional configuration.

- **Thread-per-connection model** — every peer connection spawns a dedicated listener thread. Gossip forwarding uses a bounded thread pool (8 workers), but for large-scale simulations with hundreds of peers, an event-loop model (`asyncio` or `selectors`) would be more appropriate.
