from datetime import datetime

def is_expired(auth):
    try:
        expire_in = datetime.strptime(auth['expire_in'], "%Y-%m-%dT%H:%M:%S")
    except:
        expire_in = datetime.strptime(auth['expire_in'], "%Y-%m-%dT%H:%M:%S.%f")
    delta = expire_in - datetime.now()
    return delta.total_seconds() < 0

