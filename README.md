Peer-to-Peer Network Simulation
A simulation of a decentralized peer-to-peer network built entirely in Python using raw TCP sockets and threads — no third-party networking libraries. The project demonstrates core distributed systems concepts: seed-based peer discovery, preferential attachment for topology formation, gossip-based message propagation, and PING/PONG liveness detection with automatic dead peer eviction.

Built for learning purposes.

Table of Contents
Overview
Architecture
How It Works
Project Structure
Configuration
Prerequisites
How to Run
Protocol Reference
Constants and Tuning
Log Output
Known Limitations
Overview
The simulation models two types of nodes:

Seed nodes act as bootstrap registries. They do not participate in the P2P network directly. When a new peer joins, it connects to seeds to register itself and obtain a list of existing peers. Seeds maintain each peer's connection degree (how many other peers it is connected to) and remove peers that are reported dead.

Peer nodes are the actual participants in the network. Each peer connects to a subset of seeds, discovers other peers, forms connections using a preferential attachment algorithm, exchanges messages via gossip flooding, and continuously monitors its neighbours with heartbeat pings. A peer has a 30% chance of dying at a random time between 30 and 60 seconds after joining — simulating real-world node churn.


Seed nodes and peer nodes run as separate processes. Seed processes are started first via main.py. Peer processes are then started individually via new_peer.py, one per terminal.

How It Works
1. Seed node startup
main.py reads config.txt and starts a Seeds instance for each valid ip:port entry. Each seed opens a TCP server socket and spawns a thread to accept incoming connections. A second thread listens for the list or exit command in the terminal.

2. Peer joins the network
When new_peer.py is run with a port number, it creates a Peers instance and calls creation() to open its own TCP server socket bound to 0.0.0.0 (all interfaces). It then calls connect(), which performs the full join sequence:

Randomly selects (n/2) + 1 seeds from config.txt to connect to.
Sends PEER_SERVER:<port> to each selected seed to register itself.
Sends REQUEST_PEER_LIST to each seed and merges the returned peer lists, taking the maximum known degree for any peer that appears in multiple lists.
Runs the preferential attachment algorithm to decide which existing peers to connect to.
Sends CONNECTION_UPDATE to all connected seeds with its new degree and the list of peers it connected to.
Starts background threads for gossip sending and PING/PONG liveness checking.
Starts the death simulation thread.
3. Preferential attachment
For each peer in the merged peer list, a connection probability is computed as:

threshold = 1 / (degree + 1)
connect if random() > threshold
Peers with a higher degree have a lower threshold, making them more likely to be connected to. This mimics real-world scale-free network formation (similar to Barabási–Albert model). If only one peer exists in the list, the threshold is forced to 0, guaranteeing a connection.

4. Handshake
When a peer opens a connection to another peer, it immediately sends NEW_PEER_SERVER:<port>. The receiving peer's listener will not process any subsequent messages from that connection until this handshake line is received and the sender's identity (ip, port) is recorded.

5. Gossip propagation
Each peer generates up to NUM_MESSAGES (10) gossip messages, one every GOSSIP_SEND_INTERVAL (5) seconds. Each message is a string composed of the current epoch timestamp, the peer's IP and port. Its hash is computed and sent to all connected peers as GOSSIP:<hash>.

On receiving a gossip message, a peer checks whether it has already seen that hash. If not, it records the hash and forwards it to all other connected peers (flood with deduplication). This ensures each message is delivered exactly once to every reachable node, regardless of the network topology. Forwarding is handled by a shared thread pool (ThreadPoolExecutor, 8 workers) to bound the number of threads spawned under high gossip load.

6. Liveness detection (PING/PONG)
Every PING_INTERVAL (3) seconds, each peer sends a PING to all of its connected peers. On receiving a PING, a peer immediately responds with PONG. Each peer tracks the last time a PONG was received from each neighbour. If no PONG arrives within PING_MAX_WAIT (5) seconds, a missed ping counter is incremented. After 3 consecutive misses, the remote peer is declared dead:

It is removed from the local peer connection list.
It is removed from the local peer list.
A DEAD_NODE message is sent to all connected seeds so they can remove it from the global registry.
7. Death simulation
After joining, each peer rolls a random number. With 30% probability, the peer will die at a random time between 30 and 60 seconds. When a peer dies, isDead is set to True and close() is called immediately, which shuts down the server socket and the gossip thread pool. The gossip and ping sender threads check isDead and stop. Live neighbours detect the silence through missed PINGs and report the dead peer to seeds.
