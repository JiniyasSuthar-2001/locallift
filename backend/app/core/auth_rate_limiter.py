"""
LocalLift — Authentication Rate Limiting & Brute-Force Throttling Service

Provides thread-safe in-memory tracking of authentication attempts by IP address and username/email.
Throttles repeated failed attempts, enforces temporary lockout windows, prevents password enumeration,
and logs suspicious security anomalies.
"""

import time
import logging
from typing import Dict, List, Tuple
from collections import defaultdict
import threading

from app.config import settings

logger = logging.getLogger("locallift.auth_security")

class AuthRateLimiter:
    """
    Sliding-window in-memory rate limiter and lockout manager for authentication endpoints.
    Tracks failed attempts by client IP and target account identifier.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Key -> List of timestamp floats
        self._failed_attempts: Dict[str, List[float]] = defaultdict(list)
        # Key -> lockout until timestamp float
        self._lockouts: Dict[str, float] = {}

    def _clean_old_entries(self, now: float, window_seconds: int):
        cutoff = now - window_seconds
        for key in list(self._failed_attempts.keys()):
            self._failed_attempts[key] = [t for t in self._failed_attempts[key] if t > cutoff]
            if not self._failed_attempts[key] and key not in self._lockouts:
                del self._failed_attempts[key]

        for key, lockout_until in list(self._lockouts.items()):
            if now > lockout_until:
                del self._lockouts[key]

    def check_rate_limit(self, identifier: str, client_ip: str) -> Tuple[bool, int]:
        """
        Checks if the identifier or client IP is currently rate-limited/locked out.
        Returns (is_allowed, retry_after_seconds).
        """
        now = time.time()
        max_attempts = getattr(settings, "AUTH_RATE_LIMIT_MAX_ATTEMPTS", 5)
        window = getattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)
        lockout_duration = getattr(settings, "AUTH_LOCKOUT_DURATION_SECONDS", 900)

        with self._lock:
            self._clean_old_entries(now, window)

            keys_to_check = [f"ip:{client_ip}", f"user:{identifier.lower().strip()}"]
            for k in keys_to_check:
                if k in self._lockouts:
                    remaining = int(self._lockouts[k] - now)
                    if remaining > 0:
                        return False, remaining

                # Check window failure count
                recent_failures = len(self._failed_attempts.get(k, []))
                if recent_failures >= max_attempts:
                    self._lockouts[k] = now + lockout_duration
                    logger.warning(
                        f"AUTH LOCKOUT TRIGGERED: Key '{k}' exceeded {max_attempts} failed attempts. "
                        f"Locked for {lockout_duration}s."
                    )
                    return False, lockout_duration

        return True, 0

    def record_failure(self, identifier: str, client_ip: str) -> int:
        """
        Records a failed authentication attempt and returns current failure count for this IP.
        """
        now = time.time()
        max_attempts = getattr(settings, "AUTH_RATE_LIMIT_MAX_ATTEMPTS", 5)
        window = getattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 300)
        lockout_duration = getattr(settings, "AUTH_LOCKOUT_DURATION_SECONDS", 900)

        with self._lock:
            self._clean_old_entries(now, window)
            ip_key = f"ip:{client_ip}"
            user_key = f"user:{identifier.lower().strip()}"

            self._failed_attempts[ip_key].append(now)
            self._failed_attempts[user_key].append(now)

            ip_fails = len(self._failed_attempts[ip_key])
            if ip_fails >= max_attempts:
                self._lockouts[ip_key] = now + lockout_duration
                logger.warning(
                    f"AUTH SUSPICIOUS ATTACK DETECTED: IP {client_ip} reached {ip_fails} failed attempts."
                )

            return ip_fails

    def record_success(self, identifier: str, client_ip: str):
        """
        Clears failure counts upon successful authentication.
        """
        with self._lock:
            ip_key = f"ip:{client_ip}"
            user_key = f"user:{identifier.lower().strip()}"
            self._failed_attempts.pop(ip_key, None)
            self._failed_attempts.pop(user_key, None)
            self._lockouts.pop(ip_key, None)
            self._lockouts.pop(user_key, None)

    def reset_all(self):
        """Resets all tracking states (used for test isolation)."""
        with self._lock:
            self._failed_attempts.clear()
            self._lockouts.clear()

# Global singleton rate limiter instance
auth_rate_limiter = AuthRateLimiter()
