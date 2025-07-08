# authentication/views/message_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse, Http404
from django.conf import settings
from django.db.models import Q
from pymongo import MongoClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from base64 import b64decode, b64encode
import os, uuid, iso8601
from authentication.models import Match, Like, Profile, ProfileImage, User
from authentication.utils import log_action, get_safe_profile_image_url
from functools import lru_cache
from datetime import datetime

@lru_cache
def mongo():
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB]

COL = mongo().messages

def decrypt_aes_gcm(cipher_b64, nonce_b64):
    try:
        aesgcm = AESGCM(settings.AES_KEY)
        nonce = b64decode(nonce_b64)
        ciphertext = b64decode(cipher_b64)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()
    except Exception:
        return "[decryption failed]"

def fetch_messages(match, limit=None):
    q = {"match_id": str(match.match_id)}
    cursor = COL.find(q).sort("sent_at", 1)
    if limit:
        cursor = cursor.limit(limit)

    messages = []
    for doc in cursor:
        raw = doc.get("ciphertext", "")
        nonce = doc.get("nonce", "")
        try:
            doc["ciphertext"] = decrypt_aes_gcm(raw, nonce) if raw and nonce else "[missing ciphertext]"
        except:
            doc["ciphertext"] = "[error]"
        messages.append(doc)
    return messages

def append_message(match, sender_id, text):
    aesgcm = AESGCM(settings.AES_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, text.encode(), None)

    cipher_b64 = b64encode(ciphertext).decode()
    nonce_b64 = b64encode(nonce).decode()

    msg = {
        "match_id": str(match.match_id),
        "message_id": str(uuid.uuid4()),
        "sender_user_id": sender_id,
        "ciphertext": cipher_b64,
        "nonce": nonce_b64,
        "sent_at": datetime.now().isoformat(timespec="seconds"),
        "is_read": False,
        "encryption_meta": {"alg": "AES-GCM", "version": 1},
    }
    COL.insert_one(msg)
    return msg

def mark_read(match, reader_id):
    COL.update_many({
        "match_id": str(match.match_id),
        "sender_user_id": {"$ne": reader_id},
        "is_read": False
    }, {"$set": {"is_read": True}})

def get_conversations_for(user):
    sql_matches = Match.objects.filter(is_active=1).filter(Q(user1_id=user.user_id) | Q(user2_id=user.user_id)).values("match_id", "user1_id", "user2_id")
    match_ids = [str(m["match_id"]) for m in sql_matches]

    pipeline = [
        {"$match": {"match_id": {"$in": match_ids}, "sender_user_id": {"$ne": str(user.user_id)}, "is_read": False}},
        {"$group": {"_id": "$match_id", "unread": {"$sum": 1}}},
    ]
    unread_map = {d["_id"]: d["unread"] for d in COL.aggregate(pipeline)}

    conversations = []
    for m in sql_matches:
        other_uuid = m["user2_id"] if m["user1_id"] == user.user_id else m["user1_id"]
        try:
            profile = Profile.objects.only("name").get(user_id_fk__user_id=other_uuid)
            display = profile.name or "Unknown"
        except Profile.DoesNotExist:
            display = "Unknown"
        img = ProfileImage.objects.only("image_url").filter(profile_id_fk=profile, is_primary=1).first()
        img_url = get_safe_profile_image_url(img, True) if img else settings.STATIC_URL + "images/default-avatar.jpg"

        conversations.append({
            "user_id": other_uuid,
            "name": display,
            "avatar": img_url,
            "unread": unread_map.get(str(m["match_id"]), 0)
        })

    conversations.sort(key=lambda c: (-c["unread"], c["name"].lower()))
    return conversations

@never_cache
@login_required
def messages_home(request):
    convos = get_conversations_for(request.user)
    if convos:
        return redirect("messages_with", user_id=convos[0]["user_id"])
    return render(request, "pages/messages.html", {
        "conversations": [],
        "selected_user": None,
        "selected_name": None,
        "selected_avatar": None,
        "messages": []
    })

@never_cache
@login_required
def messages_with(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)
    try:
        profile = Profile.objects.get(user_id_fk=other_user)
        display_name = profile.name or other_user.email
    except Profile.DoesNotExist:
        display_name = other_user.email

    img = ProfileImage.objects.filter(profile_id_fk=profile, is_primary=1).first()
    avatar_url = get_safe_profile_image_url(img, True) if img else settings.STATIC_URL + "images/default-avatar.jpg"

    match = Match.objects.filter(is_active=1).filter((Q(user1_id=request.user.user_id) & Q(user2_id=other_user.user_id)) | (Q(user1_id=other_user.user_id) & Q(user2_id=request.user.user_id))).first()
    if not match:
        raise Http404("No active match between these users.")

    if request.method == "POST":
        body = request.POST.get("message", "").strip()
        if body:
            append_message(match, str(request.user.user_id), body)
            log_action(request.user, f"Sent message to user {user_id}", "INFO", request, metadata={"length": len(body)})
        return redirect("messages_with", user_id=other_user.user_id)

    messages = fetch_messages(match)
    mark_read(match, str(request.user.user_id))

    return render(request, "pages/messages.html", {
        "conversations": get_conversations_for(request.user),
        "selected_user": other_user,
        "selected_name": display_name,
        "selected_avatar": avatar_url,
        "messages": messages,
        "user": request.user
    })

@never_cache
@login_required
def messages_json(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)
    match = Match.objects.filter(is_active=True).filter((Q(user1_id=request.user.user_id) & Q(user2_id=other_user.user_id)) | (Q(user1_id=other_user.user_id) & Q(user2_id=request.user.user_id))).first()
    if not match:
        return JsonResponse({"messages": []})

    since = request.GET.get("after")
    msgs = fetch_messages(match)
    if since:
        try:
            after_dt = iso8601.parse_date(since)
            msgs = [m for m in msgs if iso8601.parse_date(m["sent_at"]) > after_dt]
        except iso8601.ParseError:
            pass

    mark_read(match, str(request.user.user_id))

    lite = [{
        "id": m["message_id"],
        "text": m.get("ciphertext", "[missing]"),
        "nonce": m.get("nonce", ""),
        "ts": m["sent_at"],
        "from": m["sender_user_id"]
    } for m in msgs]

    return JsonResponse({"messages": lite})
