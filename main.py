import socket
import csv
from datetime import datetime
from flask import Flask, jsonify, render_template, Response
import threading
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import json
import plotly
import time

# --- Config ---
UDP_IP = "0.0.0.0"
UDP_PORT = 8000
CSV_FILE = "current_log.csv"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
PLOT_WINDOW_SECONDS = 60
UPDATE_INTERVAL_SEC = 1

app = Flask(__name__)
data = []  # (timestamp, current, power, energy_kwh)
total_energy_kwh = 0.0
data_lock = threading.Lock()  # Lock for thread-safe access to shared data

def udp_listener():
    global total_energy_kwh
    start_time = datetime.now()
    warmup_duration = 60  # seconds
    warmup_done = False
    last_time = start_time

    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "current", "power", "energy_kwh"])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    avg_buffer = []
    buffer_size = 5

    while True:
        message, _ = sock.recvfrom(1024)
        try:
            now = datetime.now()
            elapsed_since_start = (now - start_time).total_seconds()

            decoded = message.decode().strip()
            current_str, power_str = decoded.split(",")
            current = float(current_str)
            power = float(power_str)

            # Allow sensor to settle before processing
            if elapsed_since_start < warmup_duration:
                print(f"[WARMUP] {now} - Sensor settling... Skipping data.")
                continue  # Skip processing this sample

            if not warmup_done:
                print(f"[INFO] Warm-up completed. Starting data logging.")
                warmup_done = True

            # DEAD ZONE FILTER
            if abs(current) < 0.2:
                current = 0.0
                power = 0.0

            # Offset subtraction (clamped to 0)
            offset = 0.350
            current = max(0.0, current - offset)
            power = max(0.0, power - offset)

            avg_buffer.append((current, power))
            if len(avg_buffer) > buffer_size:
                avg_buffer.pop(0)
            current_avg = sum(c for c, _ in avg_buffer) / len(avg_buffer)
            power_avg = sum(p for _, p in avg_buffer) / len(avg_buffer)

            elapsed_seconds = (now - last_time).total_seconds()
            last_time = now

            energy_increment_kwh = (power_avg * elapsed_seconds) / 3600000.0
            total_energy_kwh += energy_increment_kwh

            timestamp = now
            print(f"[UDP] {timestamp} - {current_avg:.3f} A, {power_avg:.2f} W, {total_energy_kwh:.6f} kWh")

            with data_lock:
                data.append((timestamp, current_avg, power_avg, total_energy_kwh))

            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, current_avg, power_avg, total_energy_kwh])
        except Exception as e:
            print(f"UDP parse error: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def get_data():
    with data_lock:
        if not data:
            return Response(json.dumps(go.Figure(), cls=plotly.utils.PlotlyJSONEncoder), mimetype='application/json')
        
        df = pd.DataFrame(data, columns=["timestamp", "current", "power", "energy_kwh"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], format=TIMESTAMP_FORMAT)

    if df.empty:
        return Response(json.dumps(go.Figure(), cls=plotly.utils.PlotlyJSONEncoder), mimetype='application/json')

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=("Current (A)", "Power (W)", "Energy (kWh)")
    )

    # 🟦 Current Line Plot
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["current"],
        mode='lines+markers',
        name='Current (A)',
        line=dict(color='royalblue')
    ), row=1, col=1)

    # 🟥 Power Line Plot
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["power"],
        mode='lines+markers',
        name='Power (W)',
        line=dict(color='firebrick')
    ), row=2, col=1)

    # 🟩 Energy Line Plot + Labels
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["energy_kwh"],
        mode='lines+markers+text',
        name='Energy (kWh)',
        line=dict(color='seagreen')
    ), row=3, col=1)

    fig.update_layout(
        height=1000,
        title="Live Energy Monitoring Dashboard",
        showlegend=False,
        margin=dict(t=60, l=60, r=30, b=50),
        uirevision=True
    )

    fig.update_yaxes(title_text="Current (A)", row=1, col=1)
    fig.update_yaxes(title_text="Power (W)", row=2, col=1)
    fig.update_yaxes(title_text="Energy (kWh)", row=3, col=1)
    fig.update_xaxes(title_text="Time", row=3, col=1)

    return Response(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), mimetype='application/json')

# Start the UDP listener thread
threading.Thread(target=udp_listener, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
