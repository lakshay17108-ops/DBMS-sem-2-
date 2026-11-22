import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
import json
import time
import base64
import io
from datetime import timedelta
import qrcode
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from database import (
    add_technician,
    create_ticket,
    delete_technician,
    delete_ticket as remove_ticket,
    get_technician,
    get_technicians,
    get_tickets as fetch_tickets,
    initialize_database,
    update_technician,
    update_ticket_status,
)
from email_utils import send_dispatch_email

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_fallback_key")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
initialize_database()

@app.after_request
def no_cache_static(response):
    """Disable caching for static assets in development so changes apply immediately."""
    if app.debug and request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

def generate_qr(data_string):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# --- HTML Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# --- API Routes ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get("password") == ADMIN_PASSWORD:
        session.permanent = True          # use PERMANENT_SESSION_LIFETIME
        session["admin"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Unauthorized"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    if session.get("admin"):
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False}), 401

@app.route('/api/submit', methods=['POST'])
def submit_ticket():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON payload"}), 400

    try:
        ticket_id = f"CL{int(time.time() * 1000)}"
        qr_b64 = generate_qr(ticket_id)

        new_ticket = {
            "ticket_id": ticket_id,
            "full_name": data.get("fullName"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "block": data.get("block"),
            "floor": data.get("floor"),
            "room": data.get("room"),
            "date": data.get("date"),
            "category": data.get("category"),
            "priority": data.get("priority"),
            "location": data.get("location"),
            "description": data.get("description"),
            "image": data.get("image"),
            "status": "Awaiting Approval",
            "qr_code": qr_b64,
            "timestamp": int(time.time())
        }

        create_ticket(new_ticket)

        # Immediately dispatch email to technician (email_utils will handle missing API key)
        try:
            send_dispatch_email(new_ticket)
        except Exception:
            app.logger.exception("Dispatch email failed on submit")

        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "qr_code": f"data:image/png;base64,{qr_b64}"
        })
    except Exception as e:
        app.logger.exception("Failed to submit ticket")
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500

@app.route('/api/tickets', methods=['GET'])
def get_tickets():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(fetch_tickets())


# --- Technician management API ---
@app.route('/api/techs', methods=['GET'])
def get_techs():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(get_technicians())


@app.route('/api/techs', methods=['POST'])
def add_tech():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True)
    if not data or not data.get('category') or not data.get('email'):
        return jsonify({'error': 'Invalid payload'}), 400
    # generate simple id
    new_id = str(int(time.time() * 1000))
    entry = {'id': new_id, 'category': data['category'], 'email': data['email']}
    add_technician(entry)
    return jsonify(entry), 201


@app.route('/api/techs/<tech_id>', methods=['PUT'])
def update_tech(tech_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid payload'}), 400
    tech = get_technician(tech_id)
    if tech is None:
        return jsonify({'error': 'Not found'}), 404
    new_category = data.get('category', tech['category'])
    new_email = data.get('email', tech['email'])
    if not new_category or not new_email:
        return jsonify({'error': 'Invalid payload - category and email required'}), 400
    updated = update_technician(tech_id, new_category, new_email)
    return jsonify(updated)


@app.route('/api/email_logs', methods=['GET'])
def get_email_logs():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        n = int(request.args.get('n', 50))
    except Exception:
        n = 50
    log_path = os.path.join(os.path.dirname(__file__), 'email_sends.log')
    if not os.path.exists(log_path):
        return jsonify([])
    lines = []
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except Exception:
                    # skip malformed lines
                    continue
    except Exception:
        return jsonify({'error': 'Unable to read log file'}), 500
    # return most recent n entries
    return jsonify(lines[-n:][::-1])


@app.route('/api/techs/<tech_id>', methods=['DELETE'])
def delete_tech(tech_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if not delete_technician(tech_id):
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'success': True})

@app.route('/api/tickets/<ticket_id>/status', methods=['PUT'])
def update_status(ticket_id):
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    
    new_status = request.json.get("status")
    result = update_ticket_status(ticket_id, new_status)
    if result is None:
        return jsonify({"error": "Not found"}), 404
    old_status, ticket = result

    # Trigger dispatch email when approved or moved to in-progress from awaiting
    if old_status == "Awaiting Approval" and new_status in ["Approved", "In Progress"]:
        send_dispatch_email(ticket)

    return jsonify({"success": True})

@app.route('/api/tickets/<ticket_id>', methods=['DELETE'])
def delete_ticket(ticket_id):
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
        
    if not remove_ticket(ticket_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True, port=5500)