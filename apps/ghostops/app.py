import json
import os
import platform
import subprocess
import time
from pathlib import Path

# v0.1.1 imports
import socket
import urllib.request


# flask
from flask import Flask, jsonify, request

APP_NAME = "GhostOpsv0.1.1"
DEFAULT_DEVICES_PATH = Path(__file__).with_name("devices.example.json")
SERVICES_PATH = Path(__file__).with_name("services.example.json")


app = Flask(__name__)

# in-memory cache (do not touch)
STATE = {
    "started_at":int(time.time()),
    "devices": [],
    "last_check":None,
    "status":{},
}
# gets the current devices (or default if none)
def load_devices() -> list[dict]:
    path=Path(os.environ.get("GHOSTOPS_DEVICES", str(DEFAULT_DEVICES_PATH)))
    # reading the  devices
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# pings only once each device, its either up or down, cant be between
def ping_once(ip:str, timeout_ms: int = 800) -> tuple[bool, float | None]:
    # should work cross platform, i dont have a mac to test this
    # returns (alive, rtt_ms or None)

    sys = platform.system().lower()

    if"windows" in sys:
        # -n 1 is one packet, -w timeout(ms)
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        # -c 1 for one packet. macOS doesnt have -w like linus so only -c 1 and pray on the default timeout for macos, for the sake of my sanity
        cmd = ["ping","-c","1", ip]

    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        alive = proc.returncode == 0
    except Exception:
        return False, None

    rtt = (time.time() - start) * 1000.0
    return (alive, round(rtt, 1)) if alive else (False, None)



STATE["services"] = []
STATE["services_status"] = {}


def load_services() -> list[dict]:
    path = Path(os.environ.get("GHOSTOPS_SERVICES", str(SERVICES_PATH))) # env var for services
    if not path.exists():
        return []
    with path.open("r", encoding = "utf-8") as f:
        return json.load(f)





# shit to  check tcp    and http    
def check_tcp(host:str, port:int, timeout=1.0) -> tuple[bool, float | None]:
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
                rtt = (time.time() - start) * 1000.0
                return True, round(rtt,1)
    except Exception:
        return False, None

# now the http checker
def check_http(host:str, port:int, timeout = 1.5) -> tuple[bool, float | None]:
    url = f"http://{host}:{port}/"
    start = time.time()
    try:
        with urllib.request.urlopen(url,timeout=timeout) as _:
            rtt = (time.time() - start) * 1000.0
            return True, round(rtt,1)
    except Exception:
        return False, None


# api endpoint to reload only the services file, basically rescannning for services
@app.post("/api/reload/services")
def reload_services():
    STATE["services"] = load_services()
    return jsonify({
        "ok" : True,
        "services_count": len(STATE["services"])
        })


@app.post("/api/check/services")
def check_services():
    results = {}
    for s in STATE.get("services", []):
        host = s.get("host")
        port = int(s.get("port"))
        stype = s.get("type", "tcp")

        if stype == "http":
            up, rtt = check_http(host, port)
        else:
            up, rtt = check_tcp(host, port)
        key = f"{host}:{port}"
        results[key] = {
        "name" : s.get("name"), 
        "type": stype,
        "up": up,
        "rtt_ms":rtt,
        "checked_at": int(time.time())
        }


    STATE["services_status"] = results
    return jsonify({
        "ok": True,
        "checked":len(results),
        "status":results
        })



@app.get("/api/status/services")
def services_status():
    return jsonify(STATE.get("services_status", {}))
# health check endpoint (really useful later)
@app.get("/api/health")
def health():
    return jsonify({    
        "app": APP_NAME,
        "started_at": STATE["started_at"],
        "devices_count": len(STATE["devices"]),
        "last_check": STATE["last_check"],
        })

# get status of the current devices
@app.get("/api/devices")
def devices():
    return jsonify(STATE["devices"])

# reconnects with the devices via a post rewuest and shows how many devices are connected
@app.post("/api/reload")
def reload_devices():
    STATE["devices"] = load_devices()
    return jsonify({"ok": True, "devices_count": len(STATE["devices"])
        })

@app.post("/api/check")
def check():
    timeout_ms = int(request.args.get("timeout_ms", "800"))
    results = {}

    for d in STATE["devices"]:
        ip = d.get("ip")
        if not ip:
            continue

        alive, rtt = ping_once(ip, timeout_ms=timeout_ms)
        results[ip] = {
            "alive": alive,
            "rtt_ms": rtt,
            "checked_at": int(time.time())
        }

    STATE["status"] = results
    STATE["last_check"] = int(time.time())

    return jsonify({
        "ok": True,
        "checked": len(results),
        "status": results
    })


@app.get("/api/status")
def status():
    return jsonify({"last_check":STATE["last_check"],
        "status": STATE["status"],
        })


# claude generated html ui
@app.get("/")
def index():
    # Tiny HTML UI without templates (fast MVP)
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>{APP_NAME}</title>
      <style>
        body {{ font-family: system-ui, sans-serif; margin: 24px; }}
        .row {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom: 12px; }}
        button {{ padding: 10px 12px; cursor: pointer; }}
        table {{ border-collapse: collapse; width: 100%; max-width: 900px; }}
        th, td {{ border: 1px solid #3333; padding: 8px; text-align:left; }}
        .ok {{ font-weight: 700; }}
        .bad {{ font-weight: 700; }}
        code {{ background:#00000010; padding:2px 4px; border-radius:4px; }}
      </style>
    </head>
    <body>
      <h1>{APP_NAME}</h1>
      <p>Local-first homelab status panel (MVP). No auth, LAN-only.</p>

      <div class="row">
        <button onclick="reloadDevices()">Reload devices</button>
        <button onclick="checkNow()">Ping check</button>
        <button onclick="reloadServices()">Reload services</button>
        <button onclick="checkServices()">Service check</button>

      </div>

      <div id="meta"></div>
      <table>
        <thead>
          <tr><th>Name</th><th>IP</th><th>Tags</th><th>Status</th><th>RTT</th></tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
      <h2>Services</h2>
        <table>
          <thead>
            <tr><th>Name</th><th>Endpoint</th><th>Type</th><th>Status</th><th>RTT</th></tr>
          </thead>
          <tbody id="services_tbody"></tbody>
        </table>



    <script>
    let SERVICES_STATUS = {{}};  // escaped object literal

    async function reloadServices() {{
      await api("/api/reload/services", {{ method: "POST" }});
    }}

    async function checkServices() {{
      const r = await api("/api/check/services", {{ method: "POST" }});
      SERVICES_STATUS = r.status || {{}};
      renderServices();
    }}


    function renderServices() {{
      const tbody = document.getElementById("services_tbody");
      tbody.innerHTML = "";
      for (const key in SERVICES_STATUS) {{
        const s = SERVICES_STATUS[key];
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${{s.name || ""}}</td>
          <td><code>${{key}}</code></td>
          <td>${{s.type}}</td>
          <td class="${{s.up ? "ok" : "bad"}}">
            ${{s.up ? "UP" : "DOWN"}}
          </td>
          <td>${{s.rtt_ms ? s.rtt_ms + " ms" : "—"}}</td>
        `;
        tbody.appendChild(tr);
      }}
    }}

    async function api(path, opts={{}}) {{
      const res = await fetch(path, opts);
      return await res.json();
    }}

    let DEVICES = [];
    let STATUS = {{}};

    function render() {{
      const tbody = document.getElementById("tbody");
      tbody.innerHTML = "";
      for (const d of DEVICES) {{
        const ip = d.ip;
        const s = STATUS[ip];
        const alive = s ? s.alive : null;
        const rtt = s ? s.rtt_ms : null;

        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${{d.name}}</td>
          <td><code>${{ip}}</code></td>
          <td>${{(d.tags||[]).join(", ")}}</td>
          <td class="${{alive === true ? "ok" : alive === false ? "bad" : ""}}">
            ${{alive === true ? "UP" : alive === false ? "DOWN" : "—"}}
          </td>
          <td>${{rtt ? (rtt + " ms") : "—"}}</td>
        `;
        tbody.appendChild(tr);
      }}
    }}

    function formatTs(ts) {{
      if (!ts) return "—";
      return new Date(ts * 1000).toLocaleString();
    }}

    async function refreshMeta() {{
      const h = await api("/api/health");
      document.getElementById("meta").innerHTML =
        `<p>Devices: <b>${{h.devices_count}}</b> · Last check: <b>${{formatTs(h.last_check)}}</b></p>`;
    }}


    async function reloadDevices() {{
      await api("/api/reload", {{ method: "POST" }});
      DEVICES = await api("/api/devices");
      render();
      await refreshMeta();
    }}

    async function checkNow() {{
      const r = await api("/api/check?timeout_ms=800", {{ method: "POST" }});
      STATUS = r.status || {{}};
      render();
      await refreshMeta();
    }}

    (async () => {{
      await reloadDevices();
    }})();
    </script>
    </body>
    </html>
"""

def bootstrap():
    #load devices ons tart
    STATE["devices"] = load_devices()
    STATE["services"] = load_services()


if __name__ == "__main__":
    bootstrap()
    # any device on the network can connect
    app.run(host="0.0.0.0", port=5055, debug=True)