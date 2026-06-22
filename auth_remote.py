"""Validación contra la tabla `usuarios` compartida de Semillero.

Unifica gestor-flota al estándar del ecosistema (app_ctacte/inventario): si hay
Supabase configurado, el login valida contra la MISMA tabla `usuarios` (bcrypt,
gate `puede_flota`). Si NO hay Supabase, cae al store local users.json (modo
transición / standalone). El rol del gestor se deriva del rol del ecosistema:
admin/gerente -> 'admin' (edita), resto con puede_flota -> 'lector'.
"""

import hashlib
import os
import secrets

import requests

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:  # pragma: no cover
    _HAS_BCRYPT = False

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or ""
TENANT_ID = os.getenv("TENANT_ID") or "00000000-0000-0000-0000-000000000001"

SUPABASE_ON = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def _password_ok(plain, hash_):
    """bcrypt ($2…) con fallback sha256 hex legacy — igual que app_ctacte."""
    if not hash_:
        return False
    if hash_.startswith(("$2a$", "$2b$", "$2y$")):
        if not _HAS_BCRYPT:
            return False
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hash_.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    computed = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return secrets.compare_digest(computed, hash_)


def validar(email, password):
    """Devuelve {'username': email, 'role': 'admin'|'lector'} si las credenciales
    son válidas y el usuario puede entrar a flota; si no, None."""
    if not SUPABASE_ON or not email or not password:
        return None
    email = email.strip().lower()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/usuarios",
            params={
                "tenant_id": f"eq.{TENANT_ID}",
                "email": f"ilike.{email}",
                "activo": "eq.true",
                "select": "email,rol,password_hash,puede_flota",
            },
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return None
        rows = r.json()
    except (requests.RequestException, ValueError):
        return None
    if not rows:
        return None
    row = rows[0]
    if not _password_ok(password, row.get("password_hash", "")):
        return None
    rol = row.get("rol", "")
    if rol in ("admin", "gerente"):
        role = "admin"
    elif row.get("puede_flota"):
        role = "lector"
    else:
        return None  # no habilitado para flota
    return {"username": row.get("email", email), "role": role}


def diagnostico():
    """Diagnóstico de la conexión a Supabase. NO expone claves ni hashes —
    solo si la app ve las variables y qué responde la query. Temporal."""
    info = {
        "supabase_on": SUPABASE_ON,
        "url_set": bool(SUPABASE_URL),
        "url_host": (SUPABASE_URL.split("://")[-1].split("/")[0] if SUPABASE_URL else None),
        "key_set": bool(SUPABASE_SERVICE_KEY),
        "key_len": len(SUPABASE_SERVICE_KEY),
        "tenant_id": TENANT_ID,
        "has_bcrypt": _HAS_BCRYPT,
    }
    if not SUPABASE_ON:
        info["resultado"] = "SUPABASE_ON=false: la app NO está viendo SUPABASE_URL y/o SUPABASE_SERVICE_KEY"
        return info
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/usuarios",
            params={"select": "email,puede_flota", "limit": "1"},
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        info["query_status"] = r.status_code
        info["resultado"] = "OK: Supabase responde bien" if r.status_code == 200 else r.text[:200]
    except Exception as e:
        info["query_error"] = str(e)[:200]
    return info
