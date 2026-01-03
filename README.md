## GhostOps v0.1


GhostOps is a local-first homelab status panel designed to give fast visibility into devices on my LAN. The initial v0.1 release focuses on device inventory and reachability checks without requiring any external services

### Features
- Device inventory loaded from JSON
- Cross-platform ping checks for device status (UP/DOWN) and latency
- Simple LAN-accessible web UI
- Live status refresh and RTT measurement

### Demo
![GhostOps v0.1](demos/ghostops-v0.1.png)


## Installation

### Requirements
- Python 3.11.8
- Git
- Windows / Linux / MacOS

### Setup
``` bash
git clone https://github.com/TRXAlpha/ghostlab.git
cd ghostlab

# create python venv
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate for Windows

pip install -r apps/ghostops/requirements.txt
```
### Run GhostOps
```
python apps/ghostops/app.py
```
The web interface will be available at:
- http://127.0.0.1:5055
or
- http://<your-lan-ip>:5055 from other devices on the network

## Usage
#### Device configuration
Devices are defined in a JSON file:
```json
[
	{
		"name": "Dell Precision",
		"ip": "192.168.0.10",
		"tags": ["laptop", "main"]
	}
]
```
By default, GhostOps loads:
```
apps/ghostops/devices.example.json
```
You can override this path using an environment variable:
```
GHOSTOPS_DEVICES=/path/to/devices.json
```

### Web interface
- **Reload devices**  
  Reloads the device list from disk.

- **Ping check**  
  Performs a single ICMP reachability check per device and updates status.


Status values:

- **UP** — device responded to ping  
- **DOWN** — device unreachable  
- **—** — not checked yet  

## Project structure
```
ghostlab/
├─ README.md
├─ LICENSE
├─ apps/
│ └─ ghostops/
│ ├─ app.py
│ ├─ devices.example.json
│ └─ requirements.txt
├─ demos/
│ └─ ghostops-v0.1.png
└─ docs/
```

## Roadmap

### GhostOps
- Service and port checks (HTTP, HTTPS, custom ports)
- Per-device last-seen timestamps
- Service registry (Jellyfin, Pi-hole, NAS)
- Status export (JSON)
- Optional authentication
- Persistent configuration (YAML)

### GhostLab
- Backup orchestration (laptop → NAS)
- DNS intelligence dashboard
- Storage awareness (capacity, health)
- Jellyfin and *arr integration
- Tailscale-aware remote access
- Physical rack and lab documentation

## License
See [LICENSE](LICENSE).
