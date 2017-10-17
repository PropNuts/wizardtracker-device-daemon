from flask import Flask, request, jsonify


app = Flask(__name__)


@app.route('/ports')
def get_ports():
    ports = app.tracker.get_ports()
    json_ports = [
        {
            'port': p.device,
            'description': p.description,
        } for p in ports]

    return jsonify({
        'ports': json_ports,
        'success': 'true'
    })

@app.route('/connect', methods=['POST'])
def connect():
    port = request.args.get('port')
    success = app.tracker.connect(port)

    return jsonify({
        'success': success
    })

@app.route('/disconnect', methods=['POST'])
def disconnect():
    success = app.tracker.disconnect()

    return jsonify({
        'success': success
    })

@app.route('/set_frequency', methods=['POST'])
def set_frequency():
    receiver_id = int(request.args.get('id'))
    frequency = int(request.args.get('frequency'))

    success = app.tracker.set_frequency(receiver_id, frequency)
    return jsonify({
        'success': success
    })

@app.route('/status')
def status():
    json_status = {
        'connected': app.tracker.is_connected,
        'ready': app.tracker.is_ready
    }

    if app.tracker.is_ready:
        json_status.update({
            'receiverCount': app.tracker.receiver_count,
            'frequencies': app.tracker.frequencies,
            'voltage': app.tracker.voltage,
            'temperature': app.tracker.temperature,
            'hz': app.tracker.hz,
            'rssi': app.tracker.rssi
        })

    return jsonify(json_status)
