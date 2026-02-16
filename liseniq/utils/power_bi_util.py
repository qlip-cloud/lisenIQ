import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import frappe
import requests

MSAL_AVAILABLE = False
try:
    import msal  # type: ignore
    MSAL_AVAILABLE = True
except Exception:
    MSAL_AVAILABLE = False

AAD_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _conf(pbi_id_name: Optional[str] = None, pbi_mnemonico: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene la configuración de Power BI.
    Puede buscar por pbi_id_name O por pbi_mnemonico.
    """
    filters = {}
    if pbi_id_name:
        filters["pbi_id_name"] = pbi_id_name
    
    if pbi_mnemonico:
        filters["pbi_mnemonico"] = pbi_mnemonico

    # Leer configuración del DocType qp_IQ_PBI
    records = frappe.get_all(
        "qp_IQ_PBI",
        filters=filters,
        fields=[
            "name",
            "pbi_tenant_id",
            "pbi_client_id",
            "pbi_client_secret",
            "pbi_workspace_id",
            "pbi_report_id",
            "pbi_authority_host",
            "pbi_url_base",
            "pbi_template",
            "pbi_id_name",
            "pbi_mnemonico"
        ],
        limit=1,
    )
    
    if not records:
        msg = f"No existe configuración Power BI en qp_IQ_PBI."
        if pbi_id_name:
            msg += f" (ID: {pbi_id_name})"
        if pbi_mnemonico:
            msg += f" (Mnemonico: {pbi_mnemonico})"
        raise frappe.ValidationError(msg)
        
    rec = records[0]
    doc = frappe.get_doc("qp_IQ_PBI", rec["name"])

    # Desencriptar campos tipo Password desde el DocType
    tenant_id = doc.get_password("pbi_tenant_id")
    client_id = doc.get_password("pbi_client_id")
    client_secret = doc.get_password("pbi_client_secret")
    workspace_id = doc.get_password("pbi_workspace_id")

    cfg: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "workspace_id": workspace_id,
        "report_id": rec.get("pbi_report_id"),
        "authority_host": rec.get("pbi_authority_host"),
        "api_base": (rec.get("pbi_url_base") or "https://api.powerbi.com"),
        "template": rec.get("pbi_template"),
        "pbi_id_name": rec.get("pbi_id_name"),
        "pbi_mnemonico": rec.get("pbi_mnemonico")
    }
    required = ("tenant_id", "client_id", "client_secret", "workspace_id", "report_id", "authority_host", "api_base")
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise frappe.ValidationError(f"Faltan claves en qp_IQ_PBI ({rec['name']}): {', '.join(missing)}")
    return cfg

def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    raw = frappe.cache().get_value(key)
    if not raw:
        return None
    try:
        return frappe.parse_json(raw)
    except Exception:
        return None

def _cache_set(key: str, value: Dict[str, Any]) -> None:
    frappe.cache().set_value(key, json.dumps(value))

def get_access_token(force_refresh: bool = False, pbi_id_name: Optional[str] = None, pbi_mnemonico: Optional[str] = None) -> Dict[str, Any]:
    # El cache key debe diferenciar entre configuraciones distintas
    suffix = pbi_id_name or pbi_mnemonico or "default"
    cache_key = f"pbi_access_token::{suffix}"
    
    if not force_refresh:
        cached = _cache_get(cache_key)
        if cached and int(cached.get("exp", 0)) > int(_now_utc().timestamp()) + 60:
            return cached
            
    cfg = _conf(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    tenant_id = cfg["tenant_id"]
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    authority_host = cfg["authority_host"].rstrip("/")
    authority = f"{authority_host}/{tenant_id}"
    token_data: Dict[str, Any]
    
    if MSAL_AVAILABLE:
        try:
            app = msal.ConfidentialClientApplication(client_id=client_id, client_credential=client_secret, authority=authority)
            result = app.acquire_token_for_client(scopes=[AAD_SCOPE])
            if "access_token" not in result:
                raise Exception(result.get("error_description") or "No se pudo obtener access_token con MSAL")
            expires_in = int(result.get("expires_in", 3600))
            exp = int((_now_utc() + timedelta(seconds=max(expires_in - 120, 300))).timestamp())
            token_data = {"token": result["access_token"], "exp": exp}
            _cache_set(cache_key, token_data)
            return token_data
        except Exception as ex:
            frappe.log_error(f"MSAL falló al autenticar: {ex}", "Power BI Auth (MSAL)")
    
    try:
        token_url = f"{authority}/oauth2/v2.0/token"
        resp = requests.post(token_url, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": AAD_SCOPE,
            "grant_type": "client_credentials",
        }, timeout=15)
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
    return {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json", "Accept": "application/json"}

def get_report(report_id: Optional[str] = None, workspace_id: Optional[str] = None, pbi_id_name: Optional[str] = None, pbi_mnemonico: Optional[str] = None) -> Dict[str, Any]:
    cfg = _conf(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    workspace_id = workspace_id or cfg["workspace_id"]
    report_id = report_id or cfg["report_id"]
    api_base = cfg["api_base"].rstrip("/")
    bearer = get_access_token(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico).get("token")
    url = f"{api_base}/v1.0/myorg/groups/{workspace_id}/reports/{report_id}"
    try:
        resp = requests.get(url, headers=_auth_headers(bearer), timeout=15)
        if resp.status_code == 404:
            frappe.log_error(
                f"404 Get Report. groupId={workspace_id}, reportId={report_id}. Validar IDs, permisos, tenant settings, capacidad.",
                "Power BI GET Report (404)"
            )
            frappe.throw("Power BI: Reporte o Workspace no encontrado (404).")
        resp.raise_for_status()

        return resp.json() or {}
    
    except Exception as ex:
        frappe.log_error(f"Fallo al obtener reporte {report_id} en grupo {workspace_id}: {ex}", "Power BI GET Report")
        raise

def generate_embed_token(report_id: Optional[str] = None, 
                         workspace_id: Optional[str] = None, 
                         access_level: str = "View",
                         pbi_id_name: Optional[str] = None,
                         pbi_mnemonico: Optional[str] = None) -> Dict[str, Any]:
    cfg = _conf(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    workspace_id = workspace_id or cfg["workspace_id"]
    report_id = report_id or cfg["report_id"]
    api_base = cfg["api_base"].rstrip("/")
    bearer = get_access_token(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico).get("token")
    report_info = get_report(report_id=report_id, workspace_id=workspace_id, pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    dataset_id = report_info.get("datasetId") 
    
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
            frappe.log_error(f"404 GenerateToken V2. groupId={workspace_id}, reportId={report_id}, datasetId={dataset_id}", "Power BI GenerateToken V2 (404)")
        resp_v2.raise_for_status()
        data_v2 = resp_v2.json()
    
        if data_v2 and data_v2.get("token"):
            return {"token": data_v2["token"], "expiration": data_v2.get("expiration"), "datasetId": dataset_id}
    
    except Exception as ex:
        frappe.log_error(f"Fallo GenerateToken V2: {ex}", "Power BI GenerateToken V2")
    
    url = f"{api_base}/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/GenerateToken"
    
    try:
        resp = requests.post(url, json={"accessLevel": access_level}, headers=_auth_headers(bearer), timeout=15)
        if resp.status_code == 404:
            frappe.log_error(f"404 GenerateToken Report. groupId={workspace_id}, reportId={report_id}", "Power BI GenerateToken (404)")
            frappe.throw("Power BI: 404 al generar token. Verificar relación report/workspace y permisos.")
        resp.raise_for_status()
        data = resp.json()
        if "token" not in data:
            raise Exception(data)
        
        return {"token": data["token"], "expiration": data.get("expiration"), "datasetId": dataset_id}
    
    except Exception as ex:
        frappe.log_error(f"Fallo GenerateToken para reporte {report_id}: {ex}", "Power BI GenerateToken")
        raise

def build_embed_url(report_id: Optional[str] = None, workspace_id: Optional[str] = None, pbi_id_name: Optional[str] = None, pbi_mnemonico: Optional[str] = None) -> str:
    cfg = _conf(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    workspace_id = workspace_id or cfg["workspace_id"]
    report_id = report_id or cfg["report_id"]
    
    try:
        info = get_report(report_id=report_id, workspace_id=workspace_id, pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
        
        if info and info.get("embedUrl"):
            return info["embedUrl"]
    
    except Exception:
        pass
    
    return f"https://app.powerbi.com/reportEmbed?reportId={report_id}&groupId={workspace_id}"

def get_embed_config(report_id: Optional[str] = None,
                     workspace_id: Optional[str] = None,
                     access_level: str = "View",
                     filter_company: Optional[str] = None,
                     pbi_id_name: Optional[str] = None,
                     pbi_mnemonico: Optional[str] = None) -> Dict[str, Any]:
    
    # Obtener configuración base para asegurar que tenemos los IDs si no se pasaron
    cfg = _conf(pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    report_id = report_id or cfg["report_id"]
    workspace_id = workspace_id or cfg["workspace_id"]
    
    # El cache key debe ser específico para este reporte/configuración e identificador
    identifier = pbi_id_name or pbi_mnemonico or "default"
    cache_key = f"pbi_embed_token::{workspace_id}::{report_id}::{identifier}"
    
    cached = _cache_get(cache_key)
    now_epoch = int(_now_utc().timestamp())
    dataset_id: Optional[str] = None
    
    if cached and int(cached.get("exp", 0)) > now_epoch + 60:
        embed_token = cached["token"]
        token_expiration = cached["tokenExpiration"]
        dataset_id = cached.get("datasetId")
    else:
        token_info = generate_embed_token(report_id=report_id, workspace_id=workspace_id, access_level=access_level, pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
        embed_token = token_info["token"]
        token_expiration = token_info.get("expiration")
        dataset_id = token_info.get("datasetId")
        exp_epoch = now_epoch + 600
        
        try:
            if token_expiration:
                dt = datetime.fromisoformat(token_expiration.replace("Z", "+00:00"))
                exp_epoch = int(dt.timestamp()) - 120
        except Exception:
            pass
        _cache_set(cache_key, {"token": embed_token, "tokenExpiration": token_expiration, "datasetId": dataset_id, "exp": exp_epoch})
    
    embed_url = build_embed_url(report_id=report_id, workspace_id=workspace_id, pbi_id_name=pbi_id_name, pbi_mnemonico=pbi_mnemonico)
    
    result = {
        "reportId": report_id,
        "groupId": workspace_id,
        "embedUrl": embed_url,
        "embedToken": embed_token,
        "tokenExpiration": token_expiration,
        "datasetId": dataset_id
    }

    if filter_company: 
        result["filters"] = [{
            "$schema": "http://powerbi.com/product/schema#basicFilter",
            "target": {
                "table": "report",          # Nombre de la tabla en Power BI
                "column": "company_name"    # Nombre de la columna en Power BI
            },
            "operator": "In",
            "values": [filter_company]
        }]
    
    return result