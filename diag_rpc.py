import asyncio
import json
import os
import uuid
from time import time

import websockets

from app.core.config import settings
from app.services.device_identity import (
    build_device_auth_payload,
    load_or_create_device_identity,
    public_key_raw_base64url_from_pem,
    sign_device_payload,
)

PROTOCOL_VERSION = 3
SCOPES = [
    "operator.read",
    "operator.admin",
    "operator.approvals",
    "operator.pairing",
]


def build_device_payload(connect_nonce: str | None) -> dict:
    identity = load_or_create_device_identity()
    signed_at_ms = int(time() * 1000)
    payload = build_device_auth_payload(
        device_id=identity.device_id,
        client_id="gateway-client",
        client_mode="backend",
        role="operator",
        scopes=SCOPES,
        signed_at_ms=signed_at_ms,
        token=settings.OPENCLAW_API_TOKEN,
        nonce=connect_nonce,
    )
    device_payload = {
        "id": identity.device_id,
        "publicKey": public_key_raw_base64url_from_pem(identity.public_key_pem),
        "signature": sign_device_payload(identity.private_key_pem, payload),
        "signedAt": signed_at_ms,
    }
    if connect_nonce:
        device_payload["nonce"] = connect_nonce
    return device_payload


async def recv_first_message_or_none(ws):
    try:
        return await asyncio.wait_for(ws.recv(), timeout=2.0)
    except asyncio.TimeoutError:
        return None


async def await_response(ws, request_id: str):
    while True:
        raw = await ws.recv()
        print(f"Frame: {raw}")
        data = json.loads(raw)
        if data.get("type") == "res" and data.get("id") == request_id:
            return data


async def test_rpc():
    os.environ["OPENCLAW_GATEWAY_DEVICE_IDENTITY_PATH"] = settings.OPENCLAW_DEVICE_IDENTITY_PATH
    uri = settings.OPENCLAW_API_URL + "/v1/rpc"
    print(f"Connecting to {uri}")
    print(f"Dedicated identity path: {settings.OPENCLAW_DEVICE_IDENTITY_PATH}")

    async with websockets.connect(uri, ping_interval=None) as ws:
        connect_nonce = None
        first = await recv_first_message_or_none(ws)
        if first:
            print(f"Initial msg: {first}")
            try:
                data = json.loads(first)
                if data.get("type") == "event" and data.get("event") == "connect.challenge":
                    payload = data.get("payload") or {}
                    nonce = payload.get("nonce")
                    if isinstance(nonce, str) and nonce.strip():
                        connect_nonce = nonce.strip()
            except Exception:
                pass

        connect_id = str(uuid.uuid4())
        connect_payload = {
            "type": "req",
            "id": connect_id,
            "method": "connect",
            "params": {
                "minProtocol": PROTOCOL_VERSION,
                "maxProtocol": PROTOCOL_VERSION,
                "client": {
                    "id": "gateway-client",
                    "version": "1.0.0",
                    "platform": "python",
                    "mode": "backend",
                },
                "role": "operator",
                "scopes": SCOPES,
                "device": build_device_payload(connect_nonce),
                "auth": {"token": settings.OPENCLAW_API_TOKEN},
            },
        }
        print(f"Sending connect: {json.dumps(connect_payload)}")
        await ws.send(json.dumps(connect_payload))
        connect_resp = await await_response(ws, connect_id)
        print(f"Connect resp: {json.dumps(connect_resp)}")

        if connect_resp.get("ok") is False:
            print("Connect failed; aborting before chat.send")
            return

        chat_id = str(uuid.uuid4())
        chat_payload = {
            "type": "req",
            "id": chat_id,
            "method": "chat.send",
            "params": {
                "sessionKey": settings.SESSION_ID,
                "message": "hola buen dia test RPC",
                "deliver": False,
                "idempotencyKey": str(uuid.uuid4()),
            },
        }
        print(f"Sending chat.send: {json.dumps(chat_payload)}")
        await ws.send(json.dumps(chat_payload))
        chat_resp = await await_response(ws, chat_id)
        print(f"chat.send resp: {json.dumps(chat_resp)}")

        end_time = asyncio.get_event_loop().time() + 10.0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print(f"Stream MSG: {msg}")
            except asyncio.TimeoutError:
                if asyncio.get_event_loop().time() > end_time:
                    break


if __name__ == "__main__":
    asyncio.run(test_rpc())
