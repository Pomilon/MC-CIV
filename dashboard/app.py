from flask import Flask, jsonify, render_template_string
import threading
import requests

app = Flask(__name__)

# Very simple shared state mechanism for this prototype
# In production, use Redis or a database
AGENT_REGISTRY = {
    "Bot1": {"url": "http://localhost:3000", "status": "Unknown"}
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Minecraft Dashboard</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body { font-family: monospace; background: #222; color: #0f0; padding: 20px; }
        .card { border: 1px solid #444; padding: 10px; margin: 10px 0; background: #111; }
    </style>
</head>
<body>
    <h1>System Status</h1>
    <div id="agents">
        {% for name, info in agents.items() %}
        <div class="card">
            <h3>{{ name }}</h3>
            <pre>{{ info.data | tojson(indent=2) }}</pre>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    # Fetch latest data from agents
    agents_data = {}
    for name, info in AGENT_REGISTRY.items():
        try:
            resp = requests.get(f"{info['url']}/observe", timeout=1)
            if resp.status_code == 200:
                agents_data[name] = {"data": resp.json()}
            else:
                agents_data[name] = {"data": "Offline (503)"}
        except:
            agents_data[name] = {"data": "Unreachable"}
            
    return render_template_string(HTML_TEMPLATE, agents=agents_data)

def run_dashboard():
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_dashboard()
