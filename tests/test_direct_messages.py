"""End-to-end tests for 1:1 direct messaging (inbox, thread, send, unread)."""
import pytest

from models import Conversation, DirectMessage, Notification


@pytest.fixture
def two_users(make_user):
    return make_user("alice@t.local", first="Alice"), make_user("bob@t.local", first="Bob")


def test_send_creates_conversation_message_and_notification(app, client, login, two_users):
    alice, bob = two_users
    login("alice@t.local")
    r = client.post(f"/messages/with/{bob}/send", json={"body": "hey bob"})
    assert r.status_code == 201
    with app.app_context():
        assert Conversation.query.count() == 1
        assert DirectMessage.query.count() == 1
        assert Notification.query.filter_by(user_id=bob, type="dm").count() == 1


def test_conversation_is_singleton_per_pair(app, client, login, two_users):
    alice, bob = two_users
    login("alice@t.local")
    client.post(f"/messages/with/{bob}/send", json={"body": "one"})
    client.post(f"/messages/with/{bob}/send", json={"body": "two"})
    with app.app_context():
        assert Conversation.query.count() == 1
        assert DirectMessage.query.count() == 2


def test_cannot_message_self(client, login, two_users):
    alice, _ = two_users
    login("alice@t.local")
    r = client.post(f"/messages/with/{alice}/send", json={"body": "hi me"})
    assert r.status_code == 400


def test_inbox_and_thread_render(client, login, two_users):
    alice, bob = two_users
    login("alice@t.local")
    client.post(f"/messages/with/{bob}/send", json={"body": "hello"})
    assert client.get("/messages/").status_code == 200
    r = client.get(f"/messages/with/{bob}")
    assert r.status_code == 200
    assert b"hello" in r.data


def test_unread_count_and_read_on_view(app, client, login, two_users):
    alice, bob = two_users
    login("alice@t.local")
    client.post(f"/messages/with/{bob}/send", json={"body": "ping"})
    client.get("/auth/logout")
    login("bob@t.local")
    assert client.get("/messages/unread-count").get_json()["count"] == 1
    client.get(f"/messages/with/{alice}")
    assert client.get("/messages/unread-count").get_json()["count"] == 0
