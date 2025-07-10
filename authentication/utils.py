# authentication/utils.py

import hashlib
import uuid
import json
from .models import ActionLog
from django.utils.html import escape
from django.utils.text import Truncator


def sanitize_metadata(metadata):
    """
    Sanitize metadata dictionary to prevent XSS or script injection.
    Truncate long values to 500 chars to avoid excessive payloads.
    """
    if not isinstance(metadata, dict):
        return {}

    safe_metadata = {}
    for k, v in metadata.items():
        safe_key = escape(str(k))[:100]  # keys are escaped & max 100 chars
        safe_value = escape(str(v))      # escape all HTML/script content
        safe_value = Truncator(safe_value).chars(500)  # truncate long values
        safe_metadata[safe_key] = safe_value
    return safe_metadata

# Helper to mask IPv4 addresses (replace last octet with 0)
def mask_ip(ip_address):
    try:
        parts = ip_address.split('.')
        if len(parts) == 4:  # Only mask IPv4
            parts[-1] = '0'
            return '.'.join(parts)
        return ip_address  # Return unmodified if not IPv4
    except Exception:
        return None

def log_action(user, action_type, severity='INFO', request=None, target_id=None, target_type=None, metadata=None):
    # Get raw IP from request
    raw_ip = None
    if request:
        # Respect X-Forwarded-For if behind a proxy
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            raw_ip = x_forwarded_for.split(',')[0].strip()
        else:
            raw_ip = request.META.get('REMOTE_ADDR')

    # Pseudonymise the IP (mask the last octet)
    pseudonymised_ip = mask_ip(raw_ip) if raw_ip else None

    # Sanitize target_id and target_type (prevents script injection in DB)
    safe_target_id = escape(str(target_id)) if target_id else None
    safe_target_type = escape(str(target_type)) if target_type else None

    # Sanitize metadata
    if metadata and not isinstance(metadata, str):
        metadata = json.dumps(sanitize_metadata(metadata), default=str)

    # Generate log hash for integrity check
    log_string = f"{user.user_id if user else 'anon'}{action_type}{severity}{target_id}{target_type}".encode()
    log_hash = hashlib.sha256(log_string).hexdigest()

    ActionLog.objects.create(
        log_id=str(uuid.uuid4()),
        user=user if user and user.is_authenticated else None,
        action_type=escape(action_type),
        severity=severity,
        target_id=safe_target_id,
        target_type=safe_target_type,
        ip_address=pseudonymised_ip,
        metadata = metadata,
        log_hash=log_hash
    )


# utils.py
ROLE_PERMISSIONS = {
    "admin": {"delete_account", "edit_any_profile", "view_admin_dashboard","admin_dashboard_access",},
    "manager": {"edit_any_profile"},
    "user": {"edit_own_profile", "submit_report", "view_premium_content"}
}

def has_permission(user, action, obj=None):
    """
    Centralized access control check.
    """
    if not user.is_authenticated:
        return False

    # Get permissions for the user's role
    permissions = ROLE_PERMISSIONS.get(user.role, set())

    # Check if action is allowed for the role
    if action in permissions:
        if action == "edit_own_profile":
            return obj and obj.user_id_fk == user
        return True

    return False

