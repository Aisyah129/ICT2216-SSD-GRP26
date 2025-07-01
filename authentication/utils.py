# authentication/utils.py

import hashlib
import uuid
import json
from .models import ActionLog

def log_action(user, action_type, severity='INFO', request=None, target_id=None, target_type=None, metadata=None):
    ip = request.META.get('REMOTE_ADDR') if request else None

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
        ip_address=ip,
        metadata = metadata,
        log_hash=log_hash
    )
