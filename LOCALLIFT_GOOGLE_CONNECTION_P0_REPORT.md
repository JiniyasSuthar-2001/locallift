# LOCALLIFT — P0 GOOGLE CONNECTION & GBP ACCESS FORENSIC REMEDIATION REPORT

## 1. Executive Summary

This report documents the forensic root-cause analysis and remediation of the Google OAuth connection, token decryption errors, and Google Business Profile (GBP) access alert in **LocalLift26**.

All token decryption exceptions, legacy unencrypted token crashes, and misleading blanket alert banners have been resolved with resilient multi-key encryption, transparent plaintext handling, and accurate provider error classification.

---

## 2. Forensic Analysis & Root Causes

### Root Cause 1: Invalid / Corrupted Token Ciphertext
1. **Unencrypted Legacy Access Tokens**: In connection records (such as Conn ID 24 for `jiniyassuthar87@gmail.com`), the OAuth refresh token was Fernet encrypted while the access token was stored unencrypted as plaintext (`ya29.a0AdM...`).
2. **Brittle Decryption**: When `decrypt_token()` was called on the plaintext access token, Fernet threw an `InvalidToken` exception, logging `[locallift.security] Failed to decrypt token: invalid or corrupted ciphertext` and failing the entire connection resolution before checking the decryptable refresh token.
3. **Test / Mock Seeded Records**: Test fixtures in historical development databases inserted literal dummy strings (e.g. `'valid_access_token'` or `'encrypted_access_tok'`) without refresh tokens, which triggered decryption exceptions on service status discovery.

### Root Cause 2: Google Business Profile API Access (Quota = 0)
1. **Provider Evidence**: The Google Cloud project associated with OAuth Client ID (`741683454962-34oekguueauarjipgi5d1et80ne9hlsa...`) has not completed Google's mandatory approval process for the **Google Business Profile APIs** (`mybusinessaccountmanagement.googleapis.com` / `mybusinessbusinessinformation.googleapis.com`).
2. **Google Response Behavior**: Google Cloud returns `HTTP 429` with `QuotaFailure` (`quota_limit_value: 0`).
3. **Misleading Status Aggregation**: Previously, when location discovery encountered this quota limit, it swallowed the status and returned `NO_LOCATIONS`, while the frontend displayed a generic warning about both ciphertext corruption and quota issues simultaneously.

---

## 3. Architecture & Implementation Changes

### 1. Robust Multi-Key Encryption Suite & Transparent Plaintext Handling
- **File**: [`backend/app/core/security.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/core/security.py)
- **Changes**:
  - Implemented `_derive_fernet_key(settings.SECRET_KEY)` to ensure consistent Fernet key derivation.
  - Added `_get_all_fernet_suites()` containing the primary key derived from `settings.SECRET_KEY` and candidate fallback keys for legacy migrations.
  - Implemented `is_plaintext_token(token)` to detect raw OAuth tokens (`ya29...`, `1//...`) transparently. If a token is stored unencrypted, `decrypt_token()` safely returns it without crashing.

### 2. Resilient Token Resolution & Automatic Re-encryption
- **File**: [`backend/app/services/google/connections_service.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/google/connections_service.py)
- **Changes**:
  - Updated `get_valid_access_token()` to attempt access token decryption, and if the access token is corrupt/expired, use the valid decrypted refresh token to fetch and encrypt a fresh token.
  - Automatically re-encrypts plaintext tokens in the database with the primary Fernet key on first use.
  - Preserves refresh tokens when Google does not issue a new one on refresh.
  - Captured specific location error statuses (`API_ACCESS_NOT_GRANTED`, `PERMISSION_DENIED`, `RATE_LIMITED`) in `discover_gbp_locations_with_linkage()` instead of masking them as `NO_LOCATIONS`.

### 3. State-Specific Frontend Alert & Actionable Reconnect Workflow
- **File**: [`frontend/src/views/ConnectionsView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/ConnectionsView.tsx)
- **Changes**:
  - Replaced generic blanket error messages with distinct states:
    - **Authentication Expired**: Displays *"Your saved Google connection could not be securely read. Reconnect your Google account to restore access."* with a direct **Reconnect Google Business Profile** button.
    - **GBP API Quota Zero**: Displays *"Your Google account is connected, but this Google Cloud project does not currently have approved Business Profile API access (quota=0). Follow Google Cloud Console Business Profile API access approval procedures."*
    - **Permission Limitation**: Displays clear account permission notices.
  - Preserved independent functionality for Google Search Console, Google Ads, and Google Analytics 4 even when GBP API access is unapproved.

---

## 4. Recoverability of Existing Tokens

| Connection ID | Account Email | Service | Status Before | Recoverability | Status After |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Conn 6** | `jiniyassuthar87@gmail.com` | `business_profile` | Encrypted | **100% Recoverable** | Active |
| **Conn 24** | `jiniyassuthar87@gmail.com` | `business_profile` | Plaintext Access + Encrypted Refresh | **100% Recoverable** | Auto-re-encrypted & Active |
| **Conn 25** | `jiniyassuthar87@gmail.com` | `google_ads` | Encrypted | **100% Recoverable** | Active |
| **Conn 26** | `jiniyassuthar87@gmail.com` | `search_console` | Encrypted | **100% Recoverable** | Active |
| **Conn 27** | `jiniyassuthar87@gmail.com` | `analytics` | Encrypted | **100% Recoverable** | Active |
| **Conn 17, 28-31** | Various test emails | Various | Test dummy strings | Test data (unrecoverable) | Marked reconnect required without corrupting user accounts |

---

## 5. Automated Test Verification

Executed automated test suites:
- `pytest test_google_connections_p0_forensic.py -v`
- `pytest test_local_seo_part2_remediation.py -v`

### Test Results:
```text
test_google_connections_p0_forensic.py::test_token_encryption_and_decryption_lifecycle PASSED
test_google_connections_p0_forensic.py::test_legacy_and_plaintext_token_handling PASSED
test_google_connections_p0_forensic.py::test_token_refresh_preserves_refresh_token_and_reencrypts PASSED
test_google_connections_p0_forensic.py::test_gbp_api_access_not_granted_quota_zero_handling PASSED
test_local_seo_part2_remediation.py::test_schema_intelligence_matrix_and_prefill PASSED
test_local_seo_part2_remediation.py::test_citation_honest_discovery_and_distribution PASSED
test_local_seo_part2_remediation.py::test_nap_consistency_and_schema_integration PASSED
test_local_seo_part2_remediation.py::test_products_services_gbp_provenance PASSED

======================= 8 passed, 33 warnings in 6.10s ========================
```

---

## 6. Next Steps & Google Cloud Access Requirements

1. **Google Cloud Business Profile API Approval**:
   - To manage live GBP listings through the owner APIs, the Google Cloud Project owner must submit an access request at [Google Business Profile API Access Request](https://developers.google.com/my-business/content/prereqs#request-access).
   - Until Google approves production quota for the GCP project, LocalLift will continue to support manual product/service management, public Google Maps monitoring, and Search Console / Analytics data tracking without error.
2. **Reconnection Workflow**:
   - If an expired token is encountered, clicking the **Reconnect** button in Settings -> Connections initiates the standard Google OAuth 2.0 flow and safely persists newly encrypted access and refresh tokens.
