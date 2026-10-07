"""
Phone push notifications for calendar reminders (standard Web Push, works on iPhone for the Home Screen app).

- Keys: a VAPID key pair is made once and kept in the store (nothing to set up on Vercel).
- Encryption: RFC 8291 (aes128gcm) + VAPID (RFC 8292), done here with `cryptography`, no push library needed.
- Subscriptions: each device that allowed notifications is saved under push:subs; dead ones (404/410) are removed.
"""
from __future__ import annotations

import base64
import re
import json
import os
import time
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from store import db

KEYS = "push:vapid"
SUBS = "push:subs"
LAST = "push:last"


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(text: str) -> bytes:
    text = str(text or "")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _raw_public(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def _vapid() -> tuple[ec.EllipticCurvePrivateKey, str]:
    saved = db.get(KEYS)
    if saved and saved.get("private"):
        private = serialization.load_pem_private_key(saved["private"].encode(), password=None)
        return private, saved["public"]
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    public = b64u(_raw_public(private.public_key()))
    db.set(KEYS, {"private": pem, "public": public})
    return private, public


def public_key() -> str:
    """The key the browser needs to subscribe (applicationServerKey)."""
    return _vapid()[1]


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    """RFC 8291 aes128gcm body for one subscription."""
    ua_public_raw = unb64u(p256dh)
    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public_raw)
    as_private = ec.generate_private_key(ec.SECP256R1())
    as_public_raw = _raw_public(as_private.public_key())
    shared = as_private.exchange(ec.ECDH(), ua_public)
    ikm = _hkdf(unb64u(auth), shared, b"WebPush: info\x00" + ua_public_raw + as_public_raw, 32)
    salt = os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    cipher = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + (4096).to_bytes(4, "big") + bytes([len(as_public_raw)]) + as_public_raw
    return header + cipher


def _jwt(endpoint: str, private: ec.EllipticCurvePrivateKey, subject: str) -> str:
    target = urlparse(endpoint)
    header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = b64u(json.dumps({"aud": f"{target.scheme}://{target.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject},
                             separators=(",", ":")).encode())
    signing = f"{header}.{claims}".encode()
    r, s = decode_dss_signature(private.sign(signing, ec.ECDSA(hashes.SHA256())))
    return f"{header}.{claims}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


# ---------- subscriptions ----------

def save_subscription(sub: dict, origin: str) -> None:
    endpoint = str(sub.get("endpoint") or "")
    keys = sub.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("That isn't a push subscription.")
    device = str(sub.get("device") or "")[:64]
    if device:   # one subscription per device: an old one from the same phone / Mac would double every push
        old = [e for e, s in (db.hgetall(SUBS) or {}).items() if s.get("device") == device and e != endpoint]
        if old:
            db.hdel(SUBS, *old)
    db.hset(SUBS, {endpoint: {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]},
                              "origin": origin, "at": int(time.time()), "device": device}})


def has_subscriptions() -> bool:
    return bool(db.hgetall(SUBS))


def device_count() -> int:
    return len(db.hgetall(SUBS) or {})


def _service(endpoint: str) -> str:
    host = urlparse(endpoint).netloc
    return "Apple" if "push.apple.com" in host else "Google" if "googleapis.com" in host else "Mozilla" if "mozilla" in host else host


def send_all(title: str, body: str, tag: str, url: str = "/?calendar=today") -> int:
    """Push one notification to every saved device. Returns how many accepted it."""
    return send_report(title, body, tag, url)["sent"]


def send_report(title: str, body: str, tag: str, url: str = "/?calendar=today") -> dict:
    """Same as send_all, but says what each push service answered (kept as push:last for the calendar's status line)."""
    subs = db.hgetall(SUBS) or {}
    report = {"at": int(time.time()), "title": title, "sent": 0, "devices": len(subs), "results": []}
    if not subs:
        return report
    private, public = _vapid()
    payload = json.dumps({"title": title, "body": body, "tag": tag, "url": url}).encode()
    dead = []
    for endpoint, sub in subs.items():
        service = _service(endpoint)
        try:
            subject = sub.get("origin") or "https://srm-dashboard.vercel.app"
            resp = requests.post(endpoint, data=encrypt(payload, sub["keys"]["p256dh"], sub["keys"]["auth"]), timeout=10, headers={
                "TTL": "900", "Urgency": "high", "Topic": re.sub(r"[^A-Za-z0-9_-]", "", tag)[:32] or "srm",
                "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
                "Authorization": f"vapid t={_jwt(endpoint, private, subject)}, k={public}",
            })
            reason = ""
            if resp.status_code >= 300:
                try:
                    reason = str((resp.json() or {}).get("reason") or "")
                except Exception:
                    reason = (resp.text or "")[:80]
            report["results"].append({"service": service, "status": resp.status_code, "reason": reason})
            if resp.status_code in (404, 410):
                dead.append(endpoint)
            elif resp.status_code < 300:
                report["sent"] += 1
        except Exception as exc:  # one bad device never stops the others
            report["results"].append({"service": service, "status": 0, "reason": type(exc).__name__})
    if dead:
        db.hdel(SUBS, *dead)
    db.set(LAST, report)
    return report


def last_report() -> dict | None:
    return db.get(LAST)
