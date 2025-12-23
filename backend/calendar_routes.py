from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from services.memory_classifier import classify_memory
from services.supermemory_client import create_memory
from auth import get_user_from_token

calendar_bp = Blueprint('calendar_bp', __name__)


def _parse_ics_events(ics_text: str):
    events = []
    current = {}
    for raw in (ics_text or "").splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            current = {}
        elif upper.startswith("END:VEVENT"):
            if current.get("summary"):
                events.append(current)
            current = {}
        elif upper.startswith("SUMMARY:"):
            current["summary"] = line.split("SUMMARY:", 1)[1].strip()
        elif upper.startswith("DTSTART"):
            if ":" in line:
                dt_raw = line.split(":", 1)[1].strip()
                if "T" in dt_raw and len(dt_raw) >= 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
                elif len(dt_raw) == 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
    return events


@calendar_bp.route('/api/calendar/import', methods=['POST'])
def import_calendar():
    """Import calendar events from an ICS file or text and create event memories."""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        mode = request.form.get('mode') or request.args.get('mode') or 'default'
        ics_text = None

        if 'file' in request.files:
            f = request.files['file']
            ics_text = f.read().decode('utf-8', errors='ignore')
        else:
            ics_text = request.form.get('ics') or request.get_data(as_text=True)

        if not ics_text:
            return jsonify({'error': 'No ICS content provided'}), 400

        events = _parse_ics_events(ics_text)
        if not events:
            return jsonify({'error': 'No events found in ICS'}), 400

        created = []
        for ev in events:
            summary = ev.get("summary") or "Calendar event"
            event_date = ev.get("event_date")
            text = f"Event: {summary}"
            metadata = {
                'mode': mode,
                'source': 'calendar_import',
                'type': 'event',
                'title': summary,
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'userId': user.id
            }
            if event_date:
                metadata['event_date'] = event_date
                metadata['expires_at'] = event_date

            classification = classify_memory(mode, text)
            if classification.get('durability'):
                metadata['durability'] = classification['durability']
            if classification.get('expires_at') and not metadata.get('expires_at'):
                metadata['expires_at'] = classification['expires_at']

            result = create_memory(user.id, text, metadata, role=mode)
            if result and result.get('id'):
                created.append(result.get('id'))

        return jsonify({'imported': len(created), 'ids': created})
    except Exception as e:
        print(f"Error importing calendar: {e}")
        return jsonify({'error': str(e)}), 500


def register_calendar_routes(app):
    app.register_blueprint(calendar_bp)
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from services.memory_classifier import classify_memory
from services.supermemory_client import create_memory
from auth import get_user_from_token

calendar_bp = Blueprint('calendar_bp', __name__)


def _parse_ics_events(ics_text: str):
    events = []
    current = {}
    for raw in (ics_text or "").splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            current = {}
        elif upper.startswith("END:VEVENT"):
            if current.get("summary"):
                events.append(current)
            current = {}
        elif upper.startswith("SUMMARY:"):
            current["summary"] = line.split("SUMMARY:", 1)[1].strip()
        elif upper.startswith("DTSTART"):
            if ":" in line:
                dt_raw = line.split(":", 1)[1].strip()
                if "T" in dt_raw and len(dt_raw) >= 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
                elif len(dt_raw) == 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
    return events


@calendar_bp.route('/api/calendar/import', methods=['POST'])
def import_calendar():
    """Import calendar events from an ICS file or text and create event memories."""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        mode = request.form.get('mode') or request.args.get('mode') or 'default'
        ics_text = None

        if 'file' in request.files:
            f = request.files['file']
            ics_text = f.read().decode('utf-8', errors='ignore')
        else:
            ics_text = request.form.get('ics') or request.get_data(as_text=True)

        if not ics_text:
            return jsonify({'error': 'No ICS content provided'}), 400

        events = _parse_ics_events(ics_text)
        if not events:
            return jsonify({'error': 'No events found in ICS'}), 400

        created = []
        for ev in events:
            summary = ev.get("summary") or "Calendar event"
            event_date = ev.get("event_date")
            text = f"Event: {summary}"
            metadata = {
                'mode': mode,
                'source': 'calendar_import',
                'type': 'event',
                'title': summary,
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'userId': user.id
            }
            if event_date:
                metadata['event_date'] = event_date
                metadata['expires_at'] = event_date

            classification = classify_memory(mode, text)
            if classification.get('durability'):
                metadata['durability'] = classification['durability']
            if classification.get('expires_at') and not metadata.get('expires_at'):
                metadata['expires_at'] = classification['expires_at']

            result = create_memory(user.id, text, metadata, role=mode)
            if result and result.get('id'):
                created.append(result.get('id'))

        return jsonify({'imported': len(created), 'ids': created})
    except Exception as e:
        print(f"Error importing calendar: {e}")
        return jsonify({'error': str(e)}), 500


def register_calendar_routes(app):
    app.register_blueprint(calendar_bp)
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from services.memory_classifier import classify_memory
from services.supermemory_client import create_memory
from auth import get_user_from_token

calendar_bp = Blueprint('calendar_bp', __name__)


def _parse_ics_events(ics_text: str):
    events = []
    current = {}
    for raw in (ics_text or "").splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            current = {}
        elif upper.startswith("END:VEVENT"):
            if current.get("summary"):
                events.append(current)
            current = {}
        elif upper.startswith("SUMMARY:"):
            current["summary"] = line.split("SUMMARY:", 1)[1].strip()
        elif upper.startswith("DTSTART"):
            if ":" in line:
                dt_raw = line.split(":", 1)[1].strip()
                if "T" in dt_raw and len(dt_raw) >= 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
                elif len(dt_raw) == 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
    return events


@calendar_bp.route('/api/calendar/import', methods=['POST'])
def import_calendar():
    """Import calendar events from an ICS file or text and create event memories."""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        mode = request.form.get('mode') or request.args.get('mode') or 'default'
        ics_text = None

        if 'file' in request.files:
            f = request.files['file']
            ics_text = f.read().decode('utf-8', errors='ignore')
        else:
            ics_text = request.form.get('ics') or request.get_data(as_text=True)

        if not ics_text:
            return jsonify({'error': 'No ICS content provided'}), 400

        events = _parse_ics_events(ics_text)
        if not events:
            return jsonify({'error': 'No events found in ICS'}), 400

        created = []
        for ev in events:
            summary = ev.get("summary") or "Calendar event"
            event_date = ev.get("event_date")
            text = f"Event: {summary}"
            metadata = {
                'mode': mode,
                'source': 'calendar_import',
                'type': 'event',
                'title': summary,
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'userId': user.id
            }
            if event_date:
                metadata['event_date'] = event_date
                metadata['expires_at'] = event_date

            classification = classify_memory(mode, text)
            if classification.get('durability'):
                metadata['durability'] = classification['durability']
            if classification.get('expires_at') and not metadata.get('expires_at'):
                metadata['expires_at'] = classification['expires_at']

            result = create_memory(user.id, text, metadata, role=mode)
            if result and result.get('id'):
                created.append(result.get('id'))

        return jsonify({'imported': len(created), 'ids': created})
    except Exception as e:
        print(f"Error importing calendar: {e}")
        return jsonify({'error': str(e)}), 500


def register_calendar_routes(app):
    app.register_blueprint(calendar_bp)
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from services.memory_classifier import classify_memory
from services.supermemory_client import create_memory
from auth import get_user_from_token

calendar_bp = Blueprint('calendar_bp', __name__)


def _parse_ics_events(ics_text: str):
    events = []
    current = {}
    for raw in (ics_text or "").splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            current = {}
        elif upper.startswith("END:VEVENT"):
            if current.get("summary"):
                events.append(current)
            current = {}
        elif upper.startswith("SUMMARY:"):
            current["summary"] = line.split("SUMMARY:", 1)[1].strip()
        elif upper.startswith("DTSTART"):
            if ":" in line:
                dt_raw = line.split(":", 1)[1].strip()
                if "T" in dt_raw and len(dt_raw) >= 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
                elif len(dt_raw) == 8:
                    yyyy = dt_raw[0:4]; mm = dt_raw[4:6]; dd = dt_raw[6:8]
                    current["event_date"] = f"{yyyy}-{mm}-{dd}"
    return events


@calendar_bp.route('/api/calendar/import', methods=['POST'])
def import_calendar():
    """Import calendar events from an ICS file or text and create event memories."""
    try:
        user = get_user_from_token(request)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        mode = request.form.get('mode') or request.args.get('mode') or 'default'
        ics_text = None

        if 'file' in request.files:
            f = request.files['file']
            ics_text = f.read().decode('utf-8', errors='ignore')
        else:
            ics_text = request.form.get('ics') or request.get_data(as_text=True)

        if not ics_text:
            return jsonify({'error': 'No ICS content provided'}), 400

        events = _parse_ics_events(ics_text)
        if not events:
            return jsonify({'error': 'No events found in ICS'}), 400

        created = []
        for ev in events:
            summary = ev.get("summary") or "Calendar event"
            event_date = ev.get("event_date")
            text = f"Event: {summary}"
            metadata = {
                'mode': mode,
                'source': 'calendar_import',
                'type': 'event',
                'title': summary,
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'userId': user.id
            }
            if event_date:
                metadata['event_date'] = event_date
                metadata['expires_at'] = event_date

            classification = classify_memory(mode, text)
            if classification.get('durability'):
                metadata['durability'] = classification['durability']
            if classification.get('expires_at') and not metadata.get('expires_at'):
                metadata['expires_at'] = classification['expires_at']

            result = create_memory(user.id, text, metadata, role=mode)
            if result and result.get('id'):
                created.append(result.get('id'))

        return jsonify({'imported': len(created), 'ids': created})
    except Exception as e:
        print(f"Error importing calendar: {e}")
        return jsonify({'error': str(e)}), 500


def register_calendar_routes(app):
    app.register_blueprint(calendar_bp)

