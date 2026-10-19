import re


def content_security_policy(callback_origin=None):
    """Permit only this validated OAuth client's callback origin for form redirects."""
    if callback_origin is not None and not re.fullmatch(r"https?://[A-Za-z0-9.\[\]:-]+", callback_origin):
        raise ValueError("Invalid callback origin")
    form_sources = "'self'" + (" " + callback_origin if callback_origin else "")
    return (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action " + form_sources
    )
