import pytest
from app.core.security import encrypt_token, decrypt_token
from app.config import settings

def test_token_encryption_and_decryption_success():
    raw_secret = "ya29.a0AfH6SMD_live_oauth_access_token_12345"
    encrypted = encrypt_token(raw_secret)
    assert encrypted is not None
    assert encrypted != raw_secret
    assert len(encrypted) > 20

    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_secret

def test_token_encryption_none_handling():
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None

def test_token_decryption_invalid_ciphertext_fails_closed():
    # Corrupt or plaintext data must raise ValueError, never silently return plaintext/corrupted ciphertext
    with pytest.raises(ValueError, match="Invalid or corrupted token ciphertext"):
        decrypt_token("not_a_valid_fernet_token_string")

def test_token_decryption_tampered_ciphertext_fails_closed():
    raw = "super_secret_api_key_abc123"
    encrypted = encrypt_token(raw)
    assert encrypted is not None
    # Tamper with the middle of the ciphertext
    tampered = encrypted[:10] + "XYZ" + encrypted[13:]
    with pytest.raises(ValueError):
        decrypt_token(tampered)

def test_token_encryption_type_error_on_invalid_input():
    with pytest.raises(TypeError):
        encrypt_token(12345)  # type: ignore

    with pytest.raises(TypeError):
        decrypt_token(12345)  # type: ignore
