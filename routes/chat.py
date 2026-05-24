from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db, admin_required
from models import Chat, ChatMessage
from datetime import datetime, timezone

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# Helper function to get last activity timestamp for a chat
def _last_activity(chat):
    """Return the most recent timestamp for a chat."""
    if chat.messages:
        latest_message = max(chat.messages, key=lambda item: item.created_at or chat.created_at)
        return latest_message.created_at or chat.created_at
    return chat.created_at


# ── RULES PAGE (Accept Terms) ──────────────────────────────────────────────
@chat_bp.route('/rules', methods=['GET', 'POST'])
@login_required
def chat_rules():
    if current_user.is_admin():
        return redirect(url_for('chat.admin_view_all'))

    if request.method == 'POST':
        # User accepted rules, redirect to start chat
        return redirect(url_for('chat.start_chat'))
    return render_template('chat/rules.html')


# ── START CHAT ─────────────────────────────────────────────────────────────
@chat_bp.route('/start', methods=['GET', 'POST'])
@login_required
def start_chat():
    if current_user.is_admin():
        flash('Admins can manage conversations from the support chat inbox.', 'error')
        return redirect(url_for('chat.admin_view_all'))

    existing_chat = (Chat.query
                     .filter_by(user_id=current_user.id, status='open')
                     .order_by(Chat.created_at.desc())
                     .first())
    if existing_chat:
        flash('You already have an open support chat. We opened it for you.', 'success')
        return redirect(url_for('chat.chat_room', chat_id=existing_chat.id))

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message_text = request.form.get('message', '').strip()
        
        if not subject:
            flash('Please provide a subject for your chat.', 'error')
            return redirect(url_for('chat.start_chat'))

        if not message_text:
            flash('Please include your first message so the admin can see the issue.', 'error')
            return redirect(url_for('chat.start_chat'))
        
        # Create new chat
        new_chat = Chat(
            user_id=current_user.id,
            subject=subject,
            status='open'
        )
        db.session.add(new_chat)
        db.session.flush()

        db.session.add(ChatMessage(
            chat_id=new_chat.id,
            sender_id=current_user.id,
            message=message_text
        ))
        db.session.commit()
        
        flash('Chat started! You can now message the admin.', 'success')
        return redirect(url_for('chat.chat_room', chat_id=new_chat.id))
    
    return render_template('chat/start.html')


# ── CHAT ROOM ──────────────────────────────────────────────────────────────
@chat_bp.route('/<int:chat_id>', methods=['GET'])
@login_required
def chat_room(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    
    # Check if user is authorized (either the user who started the chat or admin)
    if chat.user_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to access this chat.', 'error')
        return redirect(url_for('main.dashboard'))
    
    messages = (ChatMessage.query
                .filter_by(chat_id=chat_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .all())
    return render_template('chat/room.html', chat=chat, messages=messages)

#ajax ıs used for sending messages without refreshing the page, and for admin actions like assigning chat to self. Regular page loads are used for viewing chat history and finishing chat.
# ── SEND MESSAGE (AJAX) ────────────────────────────────────────────────────
@chat_bp.route('/<int:chat_id>/send', methods=['POST'])
@login_required
def send_message(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    
    # Check authorization
    if chat.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    if chat.status == 'closed':
        return jsonify({'error': 'Chat is closed'}), 400
    
    payload = request.get_json(silent=True) or {}
    message_text = payload.get('message', '').strip()
    
    if not message_text:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if current_user.is_admin() and chat.admin_id is None:
        chat.admin_id = current_user.id
    
    # Create message
    new_message = ChatMessage(
        chat_id=chat_id,
        sender_id=current_user.id,
        message=message_text
    )
    db.session.add(new_message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': {
            'id': new_message.id,
            'sender': current_user.first_name + ' ' + current_user.last_name,
            'text': new_message.message if new_message.message else '',
            'created_at': new_message.created_at.strftime('%H:%M'),
            'is_own': True
        }
    }), 201


# ── FINISH CHAT ────────────────────────────────────────────────────────────
@chat_bp.route('/<int:chat_id>/finish', methods=['POST'])
@login_required
def finish_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    
    # Only user who started chat can finish it
    if chat.user_id != current_user.id:
        flash('You do not have permission to close this chat.', 'error')
        return redirect(url_for('main.dashboard'))
    
    chat.status = 'closed'
    chat.closed_at = datetime.now(timezone.utc)
    db.session.commit()
    
    flash('Chat closed. Thank you for reaching out!', 'success')
    return redirect(url_for('main.dashboard'))


# ── ADMIN: VIEW ALL CHATS ──────────────────────────────────────────────────
@chat_bp.route('/admin/all', methods=['GET'])
@admin_required
def admin_view_all():
    all_chats = Chat.query.order_by(Chat.created_at.desc()).all()
    chat_items = []
    for chat in all_chats:
        ordered_messages = sorted(
            chat.messages,
            key=lambda item: (item.created_at or chat.created_at, item.id)
        )
        last_message = ordered_messages[-1] if ordered_messages else None
        chat_items.append({
            'chat': chat,
            'message_count': len(ordered_messages),
            'last_message': last_message,
            'last_activity': _last_activity(chat),
        })

    chat_items.sort(key=lambda item: item['last_activity'], reverse=True)
    open_chats = sum(1 for item in chat_items if item['chat'].status == 'open')
    unassigned_chats = sum(
        1 for item in chat_items
        if item['chat'].status == 'open' and item['chat'].admin_id is None
    )

    return render_template(
        'admin/chat_history.html',
        chat_items=chat_items,
        open_chats=open_chats,
        unassigned_chats=unassigned_chats,
    )


# ── ADMIN: VIEW SPECIFIC CHAT HISTORY ──────────────────────────────────────
@chat_bp.route('/admin/<int:chat_id>', methods=['GET'])
@admin_required
def admin_view_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    messages = (ChatMessage.query
                .filter_by(chat_id=chat_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .all())
    
    return render_template('admin/chat_detail.html', chat=chat, messages=messages)


# ── ADMIN: ASSIGN TO SELF ──────────────────────────────────────────────────
@chat_bp.route('/<int:chat_id>/assign', methods=['POST'])
@login_required
def assign_chat(chat_id):
    if not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    chat = Chat.query.get_or_404(chat_id)
    if chat.status == 'closed':
        return jsonify({'error': 'Closed chats cannot be assigned'}), 400
    if chat.admin_id and chat.admin_id != current_user.id:
        return jsonify({'error': 'This chat is already assigned to another admin'}), 409

    chat.admin_id = current_user.id
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Chat assigned to you'}), 200
