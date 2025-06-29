import base64
import os

key = os.urandom(32)  # 256-bit AES key
encoded = base64.b64encode(key).decode()
print(encoded)

from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat())
