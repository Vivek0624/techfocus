from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet

from app.models import OAuthState
from app.security import TokenCipher, consume_oauth_state, new_oauth_state, redact


def test_token_encryption_roundtrip_and_rotation():
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    c_old = TokenCipher(old)
    ct = c_old.encrypt("IGQ-secret-token")
    assert "IGQ-secret-token" not in ct
    c_both = TokenCipher(f"{new},{old}")
    assert c_both.decrypt(ct) == "IGQ-secret-token"
    rotated = c_both.rotate(ct)
    assert TokenCipher(new).decrypt(rotated) == "IGQ-secret-token"
    try:
        TokenCipher(Fernet.generate_key().decode()).decrypt(ct)
        raise AssertionError("should fail")
    except ValueError:
        pass


def test_oauth_state_single_use(db):
    s = new_oauth_state(db)
    assert consume_oauth_state(db, s) is True
    assert consume_oauth_state(db, s) is False
    assert consume_oauth_state(db, "forged") is False
    assert consume_oauth_state(db, None) is False


def test_oauth_state_expires(db):
    db.add(OAuthState(state="old", created_at=datetime.now(UTC) - timedelta(minutes=30)))
    db.flush()
    assert consume_oauth_state(db, "old") is False


def test_redaction():
    s = redact('GET /x?access_token=IGQabc&client_secret=zz Bearer abc.def {"token": "t1"}')
    assert "IGQabc" not in s and "zz" not in s and "abc.def" not in s and "t1" not in s
