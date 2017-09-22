from flask import Flask, request, jsonify


app = Flask(__name__)


@app.route('/start')
def start():
    round_id = int(request.args.get('id'))
    success = app.tracker.start_tracking(round_id)
    return jsonify({
        'success': success
    })

@app.route('/stop')
def stop():
    success = app.tracker.stop_tracking()
    return jsonify({
        'success': success
    })

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
