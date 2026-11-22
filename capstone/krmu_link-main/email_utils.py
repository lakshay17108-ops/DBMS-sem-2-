import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import json
from datetime import datetime
from database import get_technicians

LOG_FILE = os.path.join(os.path.dirname(__file__), 'email_sends.log')

def _log_send_event(ticket_id, target, status, detail=None):
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'ticket_id': ticket_id,
        'target': target,
        'status': status,
        'detail': detail
    }
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass

def send_dispatch_email(ticket):
    # Load the routing matrix from MySQL (updated via the admin panel).
    category = ticket.get("category", "")
    routing_matrix = {}
    for entry in get_technicians():
        key = entry["category"]
        email = entry["email"]
        # Store original and lower-case keys for tolerant lookup.
        routing_matrix[key] = email
        routing_matrix[key.lower()] = email
        # Also map short variants when a category contains '/'.
        if '/' in key:
            short = key.split('/')[0].strip()
            routing_matrix[short] = email
            routing_matrix[short.lower()] = email

    # default hardcoded fallbacks
    defaults = {
        "Electrical": "electrician_team@university.edu",
        "Plumbing": "plumbing_team@university.edu",
        "Furniture": "carpenter_team@university.edu",
        "IoT / Network": "it_network_admin@university.edu",
        "IoT": "it_network_admin@university.edu",
        "HVAC": "hvac_maintenance@university.edu",
        "General": "general_maintenance@university.edu"
    }

    target_email = routing_matrix.get(category) or routing_matrix.get(category.lower()) or defaults.get(category) or defaults['General']

    # Debug/logging: show resolved routing target (helps when API key is missing)
    try:
        print(f"Dispatch routing: category='{category}' -> target_email='{target_email}'")
    except Exception:
        pass

    # Retrieve the API key from environment variables (only needed for sending)
    api_key = os.environ.get("BREVO_API_KEY", "")
    if not api_key:
        print("Warning: BREVO_API_KEY not set. Email dispatch aborted.")
        _log_send_event(ticket.get('ticket_id'), target_email, 'aborted', {'reason': 'BREVO_API_KEY not set'})
        return
    else:
        try:
            masked = api_key[:6] + '...' + api_key[-6:]
        except Exception:
            masked = '***'
        print(f"BREVO_API_KEY loaded (masked): {masked}")

    sender_email = os.environ.get('EMAIL_SENDER', 'lucky17108w@gmail.com')
    sender_name = os.environ.get('EMAIL_SENDER_NAME', 'CampusLink System')
    if sender_email == 'lucky17108w@gmail.com':
        print("Warning: EMAIL_SENDER is not set. Using fallback address. Make sure this sender is authorized in Brevo.")

    # Priority Tier Hex Colors
    priority = ticket.get("priority", "Low")
    color_matrix = {
        "Urgent": "#c0392b",
        "High": "#e74c3c",
        "Medium": "#f39c12",
        "Low": "#27ae60"
    }
    accent_color = color_matrix.get(priority, "#27ae60")

    # Configure Brevo API
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    # Construct HTML Template
    html_content = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #ddd; padding: 20px;">
        <h2 style="color: {accent_color}; border-bottom: 2px solid {accent_color}; padding-bottom: 10px;">
            CampusLink Dispatch: New Task Assigned
        </h2>
        <p><strong>Ticket ID:</strong> {ticket.get('ticket_id')}</p>
        <p><strong>Category:</strong> {category}</p>
        <p><strong>Priority:</strong> <span style="color: {accent_color}; font-weight: bold;">{priority}</span></p>
        <p><strong>Location:</strong> {ticket.get('location', 'N/A')}</p>
        <p><strong>Description:</strong></p>
        <blockquote style="background: #f9f9f9; padding: 10px; border-left: 4px solid #334155;">
            {ticket.get('description', '')}
        </blockquote>
        <p><strong>Status:</strong> {ticket.get('status')}</p>
        <br>
        <p style="font-size: 12px; color: #777; text-align: center;">
            Automated message from CampusLink Ticketing System.<br>
            by team heredity
        </p>
    </div>
    """

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": target_email}],
        sender={"email": os.environ.get('EMAIL_SENDER', 'lucky17108w@gmail.com'), "name": os.environ.get('EMAIL_SENDER_NAME', 'CampusLink System')},
        subject=f"[{priority}] Campus Maintenance Task: {ticket.get('ticket_id')}",
        html_content=html_content
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
        print(f"Dispatched email for {ticket.get('ticket_id')} to {target_email}")
        _log_send_event(ticket.get('ticket_id'), target_email, 'sent', {'message': 'OK'})
    except ApiException as e:
        # ApiException has a body attribute with details from Brevo
        body = getattr(e, 'body', None)
        print(f"Exception when calling TransactionalEmailsApi->send_transac_email: {e}")
        if body:
            print('Brevo response body:', body)
        _log_send_event(ticket.get('ticket_id'), target_email, 'error', {'exception': str(e), 'body': body})
    except Exception as e:
        # log unexpected errors too
        print(f"Unexpected error sending email: {e}")
        _log_send_event(ticket.get('ticket_id'), target_email, 'error', {'exception': str(e)})