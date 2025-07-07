# authentication/utils.py

import hashlib
import uuid
import json
from .models import ActionLog

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

    if metadata and not isinstance(metadata, str):
        metadata = json.dumps(metadata, default=str)  # Ensures safe storage

    # Generate log hash for integrity check
    log_string = f"{user.user_id if user else 'anon'}{action_type}{severity}{target_id}{target_type}".encode()
    log_hash = hashlib.sha256(log_string).hexdigest()

    ActionLog.objects.create(
        log_id=str(uuid.uuid4()),
        user=user if user and user.is_authenticated else None,
        action_type=action_type,
        severity=severity,
        target_id=target_id,
        target_type=target_type,
        ip_address=pseudonymised_ip,
        metadata = metadata,
        log_hash=log_hash
    )


# utils.py
ROLE_PERMISSIONS = {
    "admin": {"delete_account", "edit_any_profile", "view_admin_dashboard"},
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

