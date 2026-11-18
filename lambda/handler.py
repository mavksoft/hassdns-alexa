"""HassDNS Alexa — Smart Home skill Lambda proxy.

Amazon requires a Lambda as the skill endpoint. This function is a thin
proxy: it forwards the raw directive to the HassDNS cloud
(ha-cloud.es/api/alexa.php), which resolves the linked Home Assistant and
relays the message to the user's instance. The response JSON is returned
verbatim to Alexa.

The user's access token travels inside the directive scope/grantee, so the
cloud endpoint can authenticate it without the Lambda knowing anything.
"""
import json
import os
import urllib.request
import urllib.error

CLOUD_URL = os.environ.get("CLOUD_URL", "https://ha-cloud.es/api/alexa.php")
TIMEOUT = float(os.environ.get("CLOUD_TIMEOUT", "7.5"))


def _extract_token(directive: dict) -> str:
    """Access token wherever the directive type puts it."""
    p = directive.get("payload", {})
    ep = directive.get("endpoint", {})
    for scope in (
        ep.get("scope", {}),
        p.get("scope", {}),
        p.get("grantee", {}),
        p.get("scope", {}).get("token", {}) if isinstance(p.get("scope", {}).get("token"), dict) else {},
    ):
        t = scope.get("token") if isinstance(scope, dict) else None
        if isinstance(t, str) and t:
            return t
    # AcceptGrant carries it in payload.grantee.token (covered above);
    # some directives in payload.scope.token.
    return ""


def _error(code: str, message: str, payload: dict | None = None) -> dict:
    return {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "ErrorResponse",
                "messageId": "hassdns-error",
                "payloadVersion": "3",
            },
            "payload": {"type": code, "message": message, **(payload or {})},
        }
    }


def handler(event, _context):
    directive = event.get("directive") or {}
    header = directive.get("header") or {}
    name = f"{header.get('namespace', '?')}/{header.get('name', '?')}"
    token = _extract_token(directive)

    body = json.dumps(event).encode()
    req = urllib.request.Request(
        CLOUD_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}" if token else "",
            "X-Hassdns-Directive": name[:120],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return _error("BRIDGE_UNREACHABLE", f"Cloud responded {e.code}")
    except Exception as e:
        return _error("BRIDGE_UNREACHABLE", f"Cloud unreachable: {e.__class__.__name__}")
