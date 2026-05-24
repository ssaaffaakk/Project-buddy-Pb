import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import secrets

logger = logging.getLogger(__name__)

# Utility function to send email
def send_email(recipient_email, subject, body, is_html=False):
    """
    Send email using SMTP
    
    Args:
        recipient_email: Email address of recipient
        subject: Email subject
        body: Email body (HTML or plain text)
        is_html: If True, body is HTML; if False, plain text
    
    Returns:
        True if successful, False otherwise
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['MAIL_USERNAME']
        msg['To'] = recipient_email
        
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
            if current_app.config['MAIL_USE_TLS']:
                server.starttls()
            
            server.login(
                current_app.config['MAIL_USERNAME'],
                current_app.config['MAIL_PASSWORD']
            )
            server.send_message(msg)
        
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", recipient_email, e)
        return False

# Function to send password reset email
def send_password_reset_email(user_email, user_name, reset_token):
    """
    Send password reset email to user
    
    Args:
        user_email: User's email address
        user_name: User's first name
        reset_token: Generated reset token
    
    Returns:
        True if successful, False otherwise
    """
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
                    <div class="footer">© 2025 ProjectBuddy — International University of Sarajevo</div>
                </div>
            </div>
        </body>
    </html>
    """
    
    subject = "Password Reset Request - ProjectBuddy"
    return send_email(user_email, subject, html_body, is_html=True)

# Utility function to generate secure token for password reset
def generate_reset_token():
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(32)
