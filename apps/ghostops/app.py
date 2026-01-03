import json
import os
import platform
import subprocess
import time
from pathlib import Path

# flask
from flask import Flask, jsonify, request

APP_NAME = "GhostOpsv0.1"
DEFAULT_DEVICES_PATH = Path(__file__).with_name("devices.example.json")

app = Flask(__name__)

# in memoryt cache (do not touch, breaks the system somehow)
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
    timeout_ms = int(request.args.get("timeout_ms","800"))
    results = {}


    for d in STATE["devices"]:
        ip = d.get("ip")
        if not ip: continue
        alive, rtt = ping_once (ip, timeout_ms=timeout_ms)
        results[ip] = {"alive": alive, "rtt_ms":rtt, "checked_at":int(time.time())}

        STATE["status"] = results
        STATE["last_check"] = int(time.time())
        return jsonify({"ok":True, "checked":len(results), "status": results})


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
  </div>

  <div id="meta"></div>
  <table>
    <thead>
      <tr><th>Name</th><th>IP</th><th>Tags</th><th>Status</th><th>RTT</th></tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

<script>
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

async function refreshMeta() {{
  const h = await api("/api/health");
  document.getElementById("meta").innerHTML =
    `<p>Devices: <b>${{h.devices_count}}</b> · Last check: <b>${{h.last_check ?? "—"}}</b></p>`;
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


if __name__ == "__main__":
    bootstrap()
    # any device on the network can connect
    app.run(host="0.0.0.0", port=5055, debug=True)