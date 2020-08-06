from datetime import datetime

def is_expired(auth):
    try:
        expire_in = datetime.strptime(auth['expire_in'], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, KeyError):
        try:
            expire_in = datetime.strptime(auth['expire_in'], "%Y-%m-%dT%H:%M:%S.%f")
        except (ValueError, KeyError):
            expire_in = None
    if expire_in:
        delta = expire_in - datetime.now()
        return delta.total_seconds() < 0
    else:
        return True

