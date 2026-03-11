"""
Fleet scope resolution for workspace operations.

Supports:
- company scope: workspace main company only
- ute scope: all member companies of selected UTE
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from db import crud as db_crud
from db.models import OptimizationWorkspaceModel
from services.workspace_options import get_workspace_optimization_options


def resolve_workspace_fleet_scope(
    db,
    workspace: OptimizationWorkspaceModel,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve effective fleet scope for preview/publish/optimize.
    """
    default_company = db_crud.ensure_default_company(db)
    primary_company_id = str(workspace.company_id or "").strip() or str(default_company.id)
    primary_company = db_crud.get_company(db, primary_company_id) or default_company

    opts = options if isinstance(options, dict) else get_workspace_optimization_options(db, str(workspace.id))
    mode = str(opts.get("fleet_scope_mode", "company") or "company").strip().lower()
    ute_id = str(opts.get("fleet_scope_ute_id", "") or "").strip() or None

    if mode != "ute":
        return {
            "scope_mode": "company",
            "scope_company_ids": [str(primary_company.id)],
            "primary_company_id": str(primary_company.id),
            "primary_company_name": str(primary_company.name or ""),
            "ute_id": None,
            "ute_name": None,
        }

    ute = db_crud.get_ute(db, str(ute_id or ""))
    if ute is None or not bool(ute.active):
        return {
            "scope_mode": "company",
            "scope_company_ids": [str(primary_company.id)],
            "primary_company_id": str(primary_company.id),
            "primary_company_name": str(primary_company.name or ""),
            "ute_id": None,
            "ute_name": None,
            "scope_fallback_reason": "ute_not_found_or_inactive",
        }

    company_ids = []
    company_names: Dict[str, str] = {}
    for member in ute.members or []:
        company_id = str(member.company_id or "").strip()
        if not company_id:
            continue
        if company_id not in company_ids:
            company_ids.append(company_id)
        if member.company:
            company_names[company_id] = str(member.company.name or "")

    if not company_ids:
        company_ids = [str(primary_company.id)]
        company_names[str(primary_company.id)] = str(primary_company.name or "")
        return {
            "scope_mode": "company",
            "scope_company_ids": company_ids,
            "primary_company_id": str(primary_company.id),
            "primary_company_name": str(primary_company.name or ""),
            "ute_id": None,
            "ute_name": None,
            "scope_fallback_reason": "ute_without_members",
        }

    if primary_company_id not in company_ids:
        company_ids.insert(0, primary_company_id)
        company_names[primary_company_id] = str(primary_company.name or "")

    return {
        "scope_mode": "ute",
        "scope_company_ids": company_ids,
        "scope_company_names": company_names,
        "primary_company_id": str(primary_company.id),
        "primary_company_name": str(primary_company.name or ""),
        "ute_id": str(ute.id),
        "ute_name": str(ute.name or ""),
    }

