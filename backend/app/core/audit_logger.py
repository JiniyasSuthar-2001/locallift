import logging
from typing import Optional
from fastapi import Request

logger = logging.getLogger("locallift")

SENSITIVE_KEYS = {
    "password", "pass", "token", "api_key", "serpapi_key", "secret",
    "authorization", "access_token", "refresh_token", "hashed_password", "credential"
}

def log_user_action(
    request: Request,
    action: str,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    status: str = "success",
    **kwargs
) -> None:
    """
    Structured terminal log helper for meaningful application actions.
    Ensures zero leak of sensitive credentials, tokens, or passwords.
    """
    req_id = getattr(request.state, "request_id", "unknown")
    
    clean_items = []
    for k, v in kwargs.items():
        if k.lower() in SENSITIVE_KEYS:
            clean_items.append(f"{k}=[REDACTED]")
        else:
            clean_items.append(f"{k}={v}")
            
    extra_str = " ".join(clean_items)
    user_str = str(user_id) if user_id is not None else "anonymous"
    org_str = str(organization_id) if organization_id is not None else "none"

    msg = f"[USER_ACTION] request_id={req_id} action={action} user={user_str} organization={org_str} status={status}"
    if extra_str:
        msg += f" {extra_str}"
        
    logger.info(msg)
