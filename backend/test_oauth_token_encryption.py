"""
Integration tests for Google OAuth security, State signing, Nonce Replay Prevention,
and Token Encryption at Rest.
"""
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import encrypt_token, decrypt_token
from app.services.google.oauth import GoogleOAuthService
from app.models.connections import GoogleConnection


def test_token_encryption_decryption():
    print("Testing token encryption / decryption roundtrip...")
    raw_token = "ya29.a0AfH6SMB_sample_super_secret_google_access_token_12345"
    encrypted = encrypt_token(raw_token)
    assert encrypted is not None
    assert encrypted != raw_token
    assert not encrypted.startswith("ya29.")

    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_token
    print("[PASS] Token encryption & decryption roundtrip passed.")


def test_oauth_state_generation_and_validation():
    print("Testing OAuth state cryptographic signing and validation...")
    state = GoogleOAuthService.encode_oauth_state(
        project_id=101,
        user_id=202,
        organization_id=303
    )
    assert state is not None
    assert isinstance(state, str)

    # Validate valid state
    payload = GoogleOAuthService.decode_and_validate_oauth_state(state)
    assert payload is not None
    assert payload["project_id"] == 101
    assert payload["user_id"] == 202
    assert payload["organization_id"] == 303
    print("[PASS] Valid OAuth state payload verified.")

    # Test replay protection: validating the same state again must fail because nonce is consumed
    try:
        GoogleOAuthService.decode_and_validate_oauth_state(state)
        assert False, "State replay should have been rejected!"
    except ValueError as e:
        assert "already been used" in str(e) or "invalid" in str(e).lower()
        print("[PASS] Nonce replay rejection verified.")


def test_oauth_state_tampering():
    print("Testing OAuth state tampering detection...")
    state = GoogleOAuthService.encode_oauth_state(
        project_id=101,
        user_id=202,
        organization_id=303
    )

    # Tampered state token
    tampered_state = state + "tampered_bits"
    try:
        GoogleOAuthService.decode_and_validate_oauth_state(tampered_state)
        assert False, "Expected tampered state to fail!"
    except ValueError:
        print("[PASS] Tampered OAuth state successfully rejected.")


if __name__ == "__main__":
    test_token_encryption_decryption()
    test_oauth_state_generation_and_validation()
    test_oauth_state_tampering()
    print("\n=======================================================")
    print("ALL OAUTH & TOKEN ENCRYPTION SECURITY TESTS PASSED!")
    print("=======================================================")
