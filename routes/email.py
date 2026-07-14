import logging
from flask import current_app
import secrets

logger = logging.getLogger(__name__)


def deliver_email(recipient_email, subject, body, is_html=False):
    """Synchronously deliver one email via the Brevo HTTP API.

    Called by the Celery task (worker) or on a background thread (no broker).
    Returns True on 2xx. Uses eventlet's tpool only when the process is
    monkey-patched (production web), plain requests otherwise (dev, worker).
    """
    api_key = current_app.config.get('BREVO_API_KEY', '')
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', '')
    if not api_key:
        logger.warning("Email not sent: BREVO_API_KEY not configured.")
        return False

    payload = {
        "sender": {"email": sender, "name": "ProjectBuddy"},
        "to": [{"email": recipient_email}],
        "subject": subject,
    }
    if is_html:
        payload["htmlContent"] = body
    else:
        payload["textContent"] = body

    import requests as _req
    post = _req.post
    try:
        import eventlet.patcher
        if eventlet.patcher.is_monkey_patched('socket'):
            import eventlet.tpool
            def post(*args, **kwargs):  # noqa: F811 — tpool wrapper
                return eventlet.tpool.execute(_req.post, *args, **kwargs)
    except ImportError:
        pass

    try:
        resp = post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as e:
        logger.exception("Brevo send failed: %s", e)
        return False
    if resp.status_code not in (200, 201):
        logger.error("Brevo API error %s: %s", resp.status_code, resp.text)
        return False
    return True


def send_email(recipient_email, subject, body, is_html=False):
    """Send an email in the background (Celery queue, or a thread without a
    broker). Returns True when the send was accepted for delivery."""
    try:
        if not current_app.config.get('BREVO_API_KEY', ''):
            logger.warning("Email not sent: BREVO_API_KEY not configured.")
            return False
        from services.tasks import dispatch_email
        dispatch_email(recipient_email, subject, body, is_html=is_html)
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", recipient_email, e)
        return False


def send_password_reset_email(user_email, user_name, reset_token):
    """Send password reset email to user."""
    from flask import url_for

    reset_url = url_for('auth.reset_password', token=reset_token, _external=True)

    html_body = f"""
    <html>
        <head>
            <style>
                body {{ margin:0;padding:0;background-color:#0d0c0b;font-family:'Segoe UI',sans-serif; }}
                .wrapper {{ padding:40px 20px; }}
                .container {{ background:#141210;border:1px solid rgba(255,255,255,0.06);border-radius:8px;max-width:480px;margin:0 auto;padding:40px; }}
                .logo {{ font-size:1.1rem;color:#ede8df;margin-bottom:32px;letter-spacing:0.01em; }}
                .logo span {{ color:#FFD700;font-style:italic; }}
                h2 {{ color:#ede8df;font-size:1.4rem;font-weight:400;margin:0 0 12px 0;letter-spacing:-0.01em; }}
                p {{ color:#8a8078;line-height:1.7;font-size:0.88rem;margin:0 0 16px 0; }}
                .btn {{ display:inline-block;background:#FFD700;color:#0d0c0b;padding:13px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;margin:8px 0 24px 0; }}
                .divider {{ border:none;border-top:1px solid rgba(255,255,255,0.06);margin:24px 0; }}
                .footer {{ color:#4a4540;font-size:0.75rem;text-align:center; }}
                .link-box {{ background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:10px 14px;font-size:0.75rem;color:#4a4540;word-break:break-all;margin-top:12px; }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="container">
                    <div class="logo">Project<span>Buddy</span></div>
                    <h2>Reset your password</h2>
                    <p>Hi {user_name},</p>
                    <p>We received a request to reset your ProjectBuddy password. Click the button below to choose a new one:</p>
                    <a href="{reset_url}" class="btn">Reset Password →</a>
                    <p>This link expires in 24 hours. If you didn't request a password reset, you can safely ignore this email.</p>
                    <hr class="divider">
                    <p style="font-size:0.75rem;">Or copy this link into your browser:</p>
                    <div class="link-box">{reset_url}</div>
                    <hr class="divider">
                    <div class="footer">© 2025 ProjectBuddy</div>
                </div>
            </div>
        </body>
    </html>
    """

    subject = "Password Reset Request - ProjectBuddy"
    return send_email(user_email, subject, html_body, is_html=True)


def send_welcome_email(user_email, user_name):
    """Greet a brand-new account.

    Strictly best-effort. The account is already committed by the time this
    runs, so *nothing* in here may raise: a signup that 500s after the user
    row exists is worse than a signup with no welcome mail. Everything —
    url_for, template building, dispatch — is inside the guard.
    """
    try:
        return _welcome_email_body(user_email, user_name)
    except Exception as e:
        logger.exception("Welcome email failed for %s: %s", user_email, e)
        return False


def _welcome_email_body(user_email, user_name):
    from flask import url_for

    dashboard_url = url_for('main.dashboard', _external=True)

    html_body = f"""
    <html>
        <head>
            <style>
                body {{ margin:0;padding:0;background-color:#0d0c0b;font-family:'Segoe UI',sans-serif; }}
                .wrapper {{ padding:40px 20px; }}
                .container {{ background:#141210;border:1px solid rgba(255,255,255,0.06);border-radius:8px;max-width:480px;margin:0 auto;padding:40px; }}
                .logo {{ font-size:1.1rem;color:#ede8df;margin-bottom:32px;letter-spacing:0.01em; }}
                .logo span {{ color:#FFD700;font-style:italic; }}
                h2 {{ color:#ede8df;font-size:1.4rem;font-weight:400;margin:0 0 12px 0;letter-spacing:-0.01em; }}
                p {{ color:#8a8078;line-height:1.7;font-size:0.88rem;margin:0 0 16px 0; }}
                ul {{ color:#8a8078;line-height:1.9;font-size:0.88rem;margin:0 0 20px 0;padding-left:20px; }}
                li strong {{ color:#ede8df;font-weight:600; }}
                .btn {{ display:inline-block;background:#FFD700;color:#0d0c0b;padding:13px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;margin:8px 0 24px 0; }}
                .divider {{ border:none;border-top:1px solid rgba(255,255,255,0.06);margin:24px 0; }}
                .footer {{ color:#4a4540;font-size:0.75rem;text-align:center; }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="container">
                    <div class="logo">Project<span>Buddy</span></div>
                    <h2>Welcome to ProjectBuddy, {user_name}!</h2>
                    <p>Your account is ready. ProjectBuddy is where students find the right teammates — and build a track record that follows them into the next project.</p>
                    <p>A good first move:</p>
                    <ul>
                        <li><strong>Pick your interests</strong> — they drive what we recommend to you.</li>
                        <li><strong>Browse open projects</strong> — apply to the ones that fit.</li>
                        <li><strong>Find teammates</strong> — ranked by how well they complement you.</li>
                    </ul>
                    <a href="{dashboard_url}" class="btn">Open ProjectBuddy →</a>
                    <hr class="divider">
                    <div class="footer">© 2025 ProjectBuddy</div>
                </div>
            </div>
        </body>
    </html>
    """

    subject = "Welcome to ProjectBuddy"
    return send_email(user_email, subject, html_body, is_html=True)


def generate_reset_token():
    """Generate a secure random token for password reset."""
    return secrets.token_urlsafe(32)
