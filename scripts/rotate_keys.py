"""Re-encrypt every stored token with the first key in TOKEN_ENCRYPTION_KEY.
Before: TOKEN_ENCRYPTION_KEY=<new>,<old>. After this runs you may drop <old>."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "api"))

from app.db import SessionLocal  # noqa: E402
from app.models import InstagramToken  # noqa: E402
from app.security import get_cipher  # noqa: E402

with SessionLocal() as db:
    c = get_cipher()
    n = 0
    for t in db.query(InstagramToken):
        t.ciphertext = c.rotate(t.ciphertext)
        t.key_version += 1
        n += 1
    db.commit()
print(f"rotated {n} token(s)")
