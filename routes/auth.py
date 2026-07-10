import re
import os
import hmac
import hashlib
import time
import secrets
import requests as http_requests
import eventlet.tpool
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, limiter
from models import User, UserInterest


# ── OAuth state helpers (HMAC-signed timestamp — no session dependency) ────────
def _make_oauth_state() -> str:
    """Return a self-contained signed state: '<timestamp>.<hmac_hex>'.
    Does NOT use the session, so it survives cross-site redirects reliably."""
    ts  = str(int(time.time()))
    key = current_app.config['SECRET_KEY'].encode()
    sig = hmac.new(key, ts.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{ts}.{sig}"


def _verify_oauth_state(state: str, max_age: int = 600) -> bool:
    """Return True if state was issued by us and is < max_age seconds old."""
    try:
        ts_str, sig = state.rsplit('.', 1)
        key = current_app.config['SECRET_KEY'].encode()
        expected = hmac.new(key, ts_str.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected):
            return False
        if abs(time.time() - int(ts_str)) > max_age:
            return False
        return True
    except Exception:
        return False

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ── LOGIN ──────────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute; 100 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))

        if user.is_banned:
            flash('Your account has been banned. Contact an administrator.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user)
        flash(f'Welcome back, {user.first_name}!', 'success')
        
        # Redirect admins to admin dashboard, others to student dashboard
        if user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))

    return render_template('auth/auth.html', action='login')


# ── REGISTER ───────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        first_name       = request.form.get('first_name', '').strip()
        last_name        = request.form.get('last_name', '').strip()
        email            = request.form.get('email', '').strip().lower()
        department       = request.form.get('department', '').strip()
        password         = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        tags             = request.form.getlist('interest_tags')

        # Basic field check
        if not all([first_name, last_name, email, password, password_confirm]):
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.register'))

        # Password match
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        # Password strength
        if (len(password) < 8
                or not re.search(r'\d', password)
                or not re.search(r'[!@#$%^&*]', password)):
            flash('Password must be at least 8 characters and contain a digit and a special character (!@#$%^&*).', 'error')
            return redirect(url_for('auth.register'))

        # Exactly 5 interest tags
        if len(tags) != 5:
            flash('Please select exactly 5 interest tags.', 'error')
            return redirect(url_for('auth.register'))

        # Duplicate email
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.register'))

        # Determine role — faculty domain addresses auto-receive instructor role.
        faculty_domain = current_app.config.get('FACULTY_DOMAIN', '@faculty.university.edu')
        role = 'instructor' if email.endswith(faculty_domain) else 'student'

        # Create user
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            department=department or None
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get user.id before commit

        # Save interest tags
        for tag in tags:
            db.session.add(UserInterest(user_id=user.id, tag=tag))

        db.session.commit()
        login_user(user)
        flash(f'Welcome, {user.first_name}! Your account has been created.', 'success')
        # First-run: let them pick an avatar + banner before landing on the dashboard
        return redirect(url_for('main.welcome'))

    return render_template('auth/auth.html', action='register')


# ── LOGOUT ─────────────────────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/admin-login', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 30 per hour", methods=["POST"])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('auth.admin_login'))

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.admin_login'))

        if user.role != 'admin':
            flash('Access denied. Admin credentials required.', 'error')
            return redirect(url_for('auth.admin_login'))

        if user.is_banned:
            flash('Your account has been banned.', 'error')
            return redirect(url_for('auth.admin_login'))

        login_user(user)
        flash(f'Welcome, {user.first_name}!', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('auth/admin_login.html')


# ── FORGOT PASSWORD ────────────────────────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset link"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('auth.forgot_password'))

        user = User.query.filter_by(email=email).first()

        if user:
            # Generate and save reset token
            from models import PasswordReset
            from routes.email import send_password_reset_email, generate_reset_token

            # Delete old tokens for this user
            PasswordReset.query.filter_by(user_id=user.id).delete()
            db.session.commit()

            # Generate new token
            token = generate_reset_token()
            reset_record = PasswordReset(user_id=user.id, token=token)
            db.session.add(reset_record)
            db.session.commit()

            # Send email
            if send_password_reset_email(user.email, user.first_name, token):
                flash('If an account exists with that email, you will receive a password reset link.', 'success')
            else:
                flash('Error sending email. Please try again later.', 'error')
        else:
            # Don't reveal if email exists (security best practice)
            flash('If an account exists with that email, you will receive a password reset link.', 'success')

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


# ── RESET PASSWORD ─────────────────────────────────────────────────────────────
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with valid token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    from models import PasswordReset
    from config import Config

    # Find reset token
    reset_record = PasswordReset.query.filter_by(token=token).first()

    if not reset_record:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.login'))

    # Check if token is expired
    if reset_record.is_expired(Config.PASSWORD_RESET_TOKEN_EXPIRY):
        db.session.delete(reset_record)
        db.session.commit()
        flash('Reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # Validation
        if not password or not password_confirm:
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        if (not re.search(r'\d', password) or not re.search(r'[!@#$%^&*]', password)):
            flash('Password must contain a digit and a special character (!@#$%^&*).', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        # Update password
        user = reset_record.user
        user.set_password(password)
        db.session.delete(reset_record)
        db.session.commit()

        flash('Your password has been reset successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ── GITHUB OAUTH — STEP 1: send user to GitHub ────────────────────────────────
@auth_bp.route('/github')
def github_login():
    client_id    = current_app.config.get('GITHUB_CLIENT_ID')
    redirect_uri = current_app.config.get('GITHUB_REDIRECT_URI')

    # Generate a self-verifying HMAC state token.
    # Signed with SECRET_KEY + timestamp — no session storage needed,
    # so it survives cross-site redirects regardless of cookie policy.
    state = _make_oauth_state()

    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read:user user:email"
        f"&state={state}"
    )
    return redirect(github_auth_url)


# ── GITHUB OAUTH — STEP 2: GitHub sends user back here ────────────────────────
@auth_bp.route('/github/callback')
def github_callback():

    # 1. Verify the HMAC-signed state — prevents OAuth CSRF.
    #    State is self-contained (timestamp + signature), no session lookup needed.
    returned_state = request.args.get('state', '')
    if not returned_state or not _verify_oauth_state(returned_state):
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    # 2. Get the one-time code GitHub sent back in the URL
    code = request.args.get('code')
    if not code:
        flash('GitHub login was cancelled.', 'error')
        return redirect(url_for('auth.login'))

    client_id     = current_app.config.get('GITHUB_CLIENT_ID')
    client_secret = current_app.config.get('GITHUB_CLIENT_SECRET')

    # 3. Exchange the code for an access token
    token_response = eventlet.tpool.execute(
        http_requests.post,
        'https://github.com/login/oauth/access_token',
        data={
            'client_id':     client_id,
            'client_secret': client_secret,
            'code':          code,
        },
        headers={'Accept': 'application/json'}
    )
    token_data   = token_response.json()
    access_token = token_data.get('access_token')

    if not access_token:
        flash('GitHub login failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    # 4. Use the token to GET the user's GitHub profile
    profile_response = eventlet.tpool.execute(
        http_requests.get,
        'https://api.github.com/user',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.github+json',
        }
    )
    profile = profile_response.json()

    github_id  = str(profile.get('id'))
    name       = profile.get('name') or ''
    email      = profile.get('email')
    avatar_url = profile.get('avatar_url')

    # 5. If GitHub didn't give us an email (some accounts hide it), fetch separately
    if not email:
        emails_response = eventlet.tpool.execute(
            http_requests.get,
            'https://api.github.com/user/emails',
            headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/vnd.github+json'}
        )
        emails = emails_response.json()
        # pick the primary verified email
        for e in emails:
            if e.get('primary') and e.get('verified'):
                email = e.get('email')
                break

    if not email:
        flash('Could not get your email from GitHub. Please make sure your GitHub email is public.', 'error')
        return redirect(url_for('auth.login'))

    # 6. Check if user already exists by email
    user = User.query.filter_by(email=email.lower()).first()

    if user:
        # Existing user — just log them in
        # Also update their avatar from GitHub if they don't have one yet
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
            db.session.commit()
        login_user(user)
        flash(f'Welcome back, {user.first_name}!', 'success')
        return redirect(url_for('main.dashboard'))

    else:
        # New user — create account from GitHub data
        # Split name into first + last (GitHub name is one string like "John Doe")
        name_parts = name.strip().split(' ', 1)
        first_name = name_parts[0] if name_parts else 'GitHub'
        last_name  = name_parts[1] if len(name_parts) > 1 else 'User'

        new_user = User(
            first_name = first_name,
            last_name  = last_name,
            email      = email.lower(),
            role       = 'student',
            avatar_url = avatar_url,
            # GitHub users have no password.
            # Store a random 64-char hex string that will never match any
            # real password because check_password() always verifies against
            # a bcrypt/pbkdf2 hash — a raw hex string will never verify.
            password_hash = secrets.token_hex(32),
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash(f'Welcome to ProjectBuddy, {first_name}! Complete your profile to get started.', 'success')
        # Send them to edit profile so they can pick interests + department
        return redirect(url_for('main.edit_profile'))