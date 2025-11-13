from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import frappe
import requests

# Paso 0: Detectar si MSAL está disponible (recomendado por Microsoft).
#   - Librería: msal (https://github.com/AzureAD/microsoft-authentication-library-for-python)
#   - Si no está disponible, se usa el flujo OAuth 2.0 v2.0 con requests.
MSAL_AVAILABLE = False
try:
    import msal  # type: ignore
    MSAL_AVAILABLE = True
except Exception:
    MSAL_AVAILABLE = False

# Paso 0: Constantes de ámbito y URLs base recomendadas por Microsoft para Power BI Embedded.
AAD_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def _now_utc() -> datetime:
    # Paso 1: Utilidad interna para obtener "ahora" en UTC.
    return datetime.now(timezone.utc)


def _conf() -> Dict[str, Any]:
    # Paso 1: Cargar la configuración desde site_config (frappe.conf.power_bi).
    # Paso 2: Validar presencia de llaves mínimas requeridas.
    cfg = frappe.conf.get("power_bi") or {}
    required = ("tenant_id", "client_id", "client_secret", "workspace_id", "report_id", "authority_host", "api_base")
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise frappe.ValidationError(f"Faltan claves en power_bi del site_config: {', '.join(missing)}")
    return cfg


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    # Paso 1: Leer un valor desde cache (Redis) y parsear JSON.
    raw = frappe.cache().get_value(key)
    if not raw:
        return None
    try:
        return frappe.parse_json(raw)
    except Exception:
        return None


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    # Paso 1: Persistir en cache como JSON (sin TTL nativo).
    # Paso 2: La expiración la controlamos manualmente con el campo "exp" en el payload.
    frappe.cache().set_value(key, json.dumps(value))


def get_access_token(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Obtiene un access token de Azure AD para invocar las APIs de Power BI.

    Devuelve:
      {
        "token": "<bearer_access_token>",
        "exp": "<epoch_seconds_utc>"
      }

    Seguridad:
    - Nunca se expone en el cliente. Se usa solo server-side para llamar a Power BI.
    """
    # Paso 1: Leer cache si no se fuerza la actualización.
    cache_key = "pbi_access_token"
    if not force_refresh:
        cached = _cache_get(cache_key)
        if cached and int(cached.get("exp", 0)) > int(_now_utc().timestamp()) + 60:
            return cached

    # Paso 2: Cargar configuración.
    cfg = _conf()
    tenant_id = cfg["tenant_id"]
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    authority_host = cfg["authority_host"].rstrip("/")
    authority = f"{authority_host}/{tenant_id}"

    token_data: Dict[str, Any]

    # Paso 3: Intentar con MSAL (recomendado por Microsoft).
    if MSAL_AVAILABLE:
        try:
            # Paso 3.1: Crear la app confidencial (Client Credentials Flow).
            app = msal.ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=authority,
            )
            # Paso 3.2: Solicitar token con el scope de Power BI.
            result = app.acquire_token_for_client(scopes=[AAD_SCOPE])
            if "access_token" not in result:
                raise Exception(result.get("error_description") or "No se pudo obtener access_token con MSAL")

            expires_in = int(result.get("expires_in", 3600))
            exp = int((_now_utc() + timedelta(seconds=max(expires_in - 120, 300))).timestamp())
            token_data = {"token": result["access_token"], "exp": exp}
            # Paso 3.3: Guardar en cache y devolver.
            _cache_set(cache_key, token_data)
            return token_data
        except Exception as ex:
            frappe.log_error(f"MSAL falló al autenticar: {ex}", "Power BI Auth (MSAL)")

    # Paso 4: Fallback sin MSAL usando OAuth 2.0 v2.0 Token Endpoint.
    try:
        token_url = f"{authority}/oauth2/v2.0/token"
        resp = requests.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": AAD_SCOPE,
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise Exception(data)
        expires_in = int(data.get("expires_in", 3600))
        exp = int((_now_utc() + timedelta(seconds=max(expires_in - 120, 300))).timestamp())
        token_data = {"token": data["access_token"], "exp": exp}
        _cache_set(cache_key, token_data)
        return token_data
    except Exception as ex:
        frappe.log_error(f"OAuth client_credentials falló: {ex}", "Power BI Auth (Fallback)")
        raise


def _auth_headers(bearer: str) -> Dict[str, str]:
    # Paso 1: Encabezados estándar para llamadas a Power BI.
    return {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_report(report_id: Optional[str] = None,
               workspace_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Paso a paso:
    - Paso 1: Cargar configuración e IDs por defecto.
    - Paso 2: Obtener access token.
    - Paso 3: Consultar el reporte para validar existencia y obtener embedUrl/datasetId.
    """
    cfg = _conf()
    workspace_id = workspace_id or cfg["workspace_id"]
    report_id = report_id or cfg["report_id"]
    api_base = cfg["api_base"].rstrip("/")
    bearer = get_access_token().get("token")

    url = f"{api_base}/v1.0/myorg/groups/{workspace_id}/reports/{report_id}"
    try:
        resp = requests.get(url, headers=_auth_headers(bearer), timeout=15)
        if resp.status_code == 404:
            # Pistas útiles para 404.
            frappe.log_error(
                f"404 Get Report. groupId={workspace_id}, reportId={report_id}. "
                "Validar: IDs correctos, SP con acceso al workspace, workspace no es 'My workspace', "
                "tenant settings habilitadas y workspace en capacidad.",
                "Power BI GET Report (404)"
            )
            frappe.throw("Power BI: Reporte o Workspace no encontrado (404). Verificar IDs y permisos.")
        resp.raise_for_status()
        return resp.json() or {}
    except Exception as ex:
        frappe.log_error(f"Fallo al obtener reporte {report_id} en grupo {workspace_id}: {ex}", "Power BI GET Report")
        raise


def generate_embed_token(report_id: Optional[str] = None,
                         workspace_id: Optional[str] = None,
                         access_level: str = "View") -> Dict[str, Any]:
    """
    Genera un Embed Token intentando primero el endpoint V2 y, si falla, el endpoint por reporte.
    """
    # Paso 1: Cargar configuración e IDs y validar/obtener datos del reporte.
    cfg = _conf()
    workspace_id = workspace_id or cfg["workspace_id"]
    report_id = report_id or cfg["report_id"]
    api_base = cfg["api_base"].rstrip("/")
    bearer = get_access_token().get("token")

    # Paso 2: Confirmar que el reporte existe y recuperar datasetId/embedUrl.
    report_info = get_report(report_id=report_id, workspace_id=workspace_id)
    dataset_id = report_info.get("datasetId") or cfg.get("dataset_id")

    # Paso 3: Intentar GenerateToken V2 (múltiples recursos).
    try:
        body_v2: Dict[str, Any] = {
            "accessLevel": access_level,
            "reports": [{"id": report_id, "groupId": workspace_id}],
            "targetWorkspaces": [{"id": workspace_id}],
        }
        if dataset_id:
            body_v2["datasets"] = [{"id": dataset_id}]
        url_v2 = f"{api_base}/v1.0/myorg/GenerateToken"
        resp_v2 = requests.post(url_v2, json=body_v2, headers=_auth_headers(bearer), timeout=15)
        if resp_v2.status_code == 404:
            frappe.log_error(
                f"404 GenerateToken V2. groupId={workspace_id}, reportId={report_id}, datasetId={dataset_id}",
                "Power BI GenerateToken V2 (404)"
            )
        resp_v2.raise_for_status()
        data_v2 = resp_v2.json()
        if data_v2 and data_v2.get("token"):
            return {"token": data_v2["token"], "expiration": data_v2.get("expiration")}
    except Exception as ex:
        frappe.log_error(f"Fallo GenerateToken V2: {ex}", "Power BI GenerateToken V2")

    # Paso 4: Fallback al endpoint por Report.
    url = f"{api_base}/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/GenerateToken"
    try:
        resp = requests.post(url, json={"accessLevel": access_level}, headers=_auth_headers(bearer), timeout=15)
        if resp.status_code == 404:
            frappe.log_error(
                f"404 GenerateToken Report. groupId={workspace_id}, reportId={report_id}",
                "Power BI GenerateToken (404)"
            )
            frappe.throw(
                "Power BI: 404 al generar token. Verificar: "
                "- report_id pertenece al workspace_id, "
                "- el Service Principal tiene rol en el workspace, "
                "- tenant settings para SP habilitadas, "
                "- el workspace no es 'My workspace' y está en capacidad."
            )
        resp.raise_for_status()
        data = resp.json()
        if "token" not in data:
            raise Exception(data)
        return {"token": data["token"], "expiration": data.get("expiration")}
    except Exception as ex:
        frappe.log_error(f"Fallo GenerateToken para reporte {report_id}: {ex}", "Power BI GenerateToken")
        raise


def build_embed_url(report_id: Optional[str] = None, workspace_id: Optional[str] = None) -> str:
    """
    Preferir la embedUrl oficial del GET del reporte; si falla, usar la URL armada.
    """
    # Paso 1: Cargar configuración e IDs por defecto.
    cfg = _conf()
    workspace_id = workspace_id or cfg["workspace_id"]
    report_id = report_id or cfg["report_id"]

    # Paso 2: Intentar obtener embedUrl desde la API (más preciso).
    try:
        info = get_report(report_id=report_id, workspace_id=workspace_id)
        if info and info.get("embedUrl"):
            return info["embedUrl"]
    except Exception:
        # Paso 3: Fallback a URL armada.
        pass

    return f"https://app.powerbi.com/reportEmbed?reportId={report_id}&groupId={workspace_id}"


def get_embed_config(report_id: Optional[str] = None,
                     workspace_id: Optional[str] = None,
                     access_level: str = "View") -> Dict[str, Any]:
    """
    Prepara el paquete de configuración para el cliente:
      {
        "reportId": "...",
        "groupId": "...",
        "embedUrl": "...",
        "embedToken": "...",
        "tokenExpiration": "..."
      }

    Seguridad:
    - Solo se expone el Embed Token (temporal) al navegador.
    - Nunca se envían client_id/client_secret al cliente.
    """
    # Paso 1: Cargar configuración base.
    cfg = _conf()
    report_id = report_id or cfg["report_id"]
    workspace_id = workspace_id or cfg["workspace_id"]

    # Paso 2: Intentar cachear el embed token por reporte para reducir latencia.
    cache_key = f"pbi_embed_token::{workspace_id}::{report_id}"
    cached = _cache_get(cache_key)
    now_epoch = int(_now_utc().timestamp())
    if cached and int(cached.get("exp", 0)) > now_epoch + 60:
        # Paso 2.1: Reusar token válido.
        embed_token = cached["token"]
        token_expiration = cached["tokenExpiration"]
    else:
        # Paso 2.2: Generar un nuevo embed token.
        token_info = generate_embed_token(report_id=report_id, workspace_id=workspace_id, access_level=access_level)
        embed_token = token_info["token"]
        token_expiration = token_info.get("expiration")
        # Convertimos expiration ISO8601 a epoch (si existe), con margen de seguridad.
        exp_epoch = now_epoch + 600
        try:
            if token_expiration:
                # Formato esperado: 2025-01-01T00:00:00Z
                dt = datetime.fromisoformat(token_expiration.replace("Z", "+00:00"))
                exp_epoch = int(dt.timestamp()) - 120
        except Exception:
            pass
        _cache_set(cache_key, {"token": embed_token, "tokenExpiration": token_expiration, "exp": exp_epoch})

    # Paso 3: Construir embedUrl (o llamar API GET /reports/{id} si se requiere).
    embed_url = build_embed_url(report_id=report_id, workspace_id=workspace_id)

    # Paso 4: Devolver paquete de configuración para el front-end.
    return {
        "reportId": report_id,
        "groupId": workspace_id,
        "embedUrl": embed_url,
        "embedToken": embed_token,
        "tokenExpiration": token_expiration,
    }


# Recomendación de SDKs/Endpoints (referencia rápida):
#   - SDK JS (cliente): powerbi-client (https://www.npmjs.com/package/powerbi-client)
#   - SDK Python (server): msal (https://pypi.org/project/msal/)
#   - Token endpoint AAD v2.0: https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
#   - Power BI REST API Base: https://api.powerbi.com
#   - GenerateToken (Report): POST /v1.0/myorg/groups/{groupId}/reports/{reportId}/GenerateToken
