from datetime import datetime

def is_expired(auth):
    try:
        expires_at = datetime.strptime(auth['expires_at'], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, KeyError):
        try:
            expires_at = datetime.strptime(auth['expires_at'], "%Y-%m-%dT%H:%M:%S.%f")
        except (ValueError, KeyError):
            expires_at = None
    if expires_at:
        delta = expires_at - datetime.now()
        return delta.total_seconds() < 0
    else:
        return True

