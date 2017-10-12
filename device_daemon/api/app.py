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

@app.route('/connect')
def connect():
    port = request.args.get('port')
    success = app.tracker.connect(port)

    return jsonify({
        'success': success
    })

@app.route('/disconnect')
def disconnect():
    success = app.tracker.disconnect()

    return jsonify({
        'success': success
    })

@app.route('/status')
def status():
    json_status = {
        'connected': app.tracker.is_connected
    }

    if app.tracker.is_connected:
        json_status.update({
            'voltage': app.tracker.voltage,
            'temperature': app.tracker.temperature,
            'hz': app.tracker.hz
        })

    return jsonify(json_status)