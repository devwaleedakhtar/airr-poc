from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cloudinary.utils
from openpyxl import load_workbook
from openpyxl.utils.datetime import to_excel

from ..core.cloudinary import upload_raw
from ..core.config import settings
from ..schemas.mapping import MappingResult
from ..schemas.sessions import ExportAppliedField, ExportResponse

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "constants" / "model_input_sheet.xlsx"
TARGET_SHEET_NAME = "PERPETUITY MIDDLEMAN INPUT TAB"

# Canonical scalar fields -> cell references in the template sheet.
SCALAR_CELL_MAP: Dict[Tuple[str, str], str] = {
    # Growth assumptions
    ("growth_assumptions", "market_rent_growth"): "I35",
    ("growth_assumptions", "affordable_rent_growth"): "I36",
    ("growth_assumptions", "other_income_growth"): "I37",
    ("growth_assumptions", "controllables_growth"): "I38",
    ("growth_assumptions", "taxes_growth"): "I39",
    ("growth_assumptions", "insurance_growth"): "I40",
    # Senior loan terms
    ("senior_loan_terms", "loan_to_cost_pct"): "F5",
    ("senior_loan_terms", "interest_type"): "F6",
    ("senior_loan_terms", "curve"): "F7",
    ("senior_loan_terms", "sofr_spread_pct"): "F8",
    ("senior_loan_terms", "sofr_floor_pct"): "F9",
    ("senior_loan_terms", "sofr_cap_pct"): "F10",
    ("senior_loan_terms", "interest_only_period_months"): "F11",
    ("senior_loan_terms", "amortization_schedule_years"): "F12",
    ("senior_loan_terms", "initial_term_months"): "F13",
    ("senior_loan_terms", "loan_maturity_months"): "F14",
    ("senior_loan_terms", "origination_fee_pct"): "F15",
    ("senior_loan_terms", "rate_stepdown_dscr_multiple"): "F16",
    ("senior_loan_terms", "rate_stepdown_dy_pct"): "F17",
    ("senior_loan_terms", "stepdown_rate_pct"): "F18",
    ("senior_loan_terms", "exit_fee_pct"): "F20",
    # Exit assumptions
    ("exit_assumptions", "sale_date"): "F24",
    ("exit_assumptions", "sale_month"): "F25",
    ("exit_assumptions", "noi_type"): "F26",
    ("exit_assumptions", "sale_costs_pct"): "F27",
    ("exit_assumptions", "exit_cap_rate_mf_pct"): "F28",
    ("exit_assumptions", "exit_cap_rate_retail_pct"): "F29",
    # Tax reassessment at exit
    ("tax_reassessment_at_exit", "reassess_at_sale"): "E33",
    ("tax_reassessment_at_exit", "property_tax_millage_rate_pct"): "F34",
    ("tax_reassessment_at_exit", "county_assessment_pct"): "F35",
    ("tax_reassessment_at_exit", "market_value_as_pct_of_sale_price"): "F36",
    # Revenue / opex knobs
    ("revenue_and_other_income", "vacancy_pct"): "C22",
    ("revenue_and_other_income", "loss_to_lease_pct"): "C23",
    ("revenue_and_other_income", "bad_debt_pct"): "C24",
    ("revenue_and_other_income", "model_units"): "C25",
    ("revenue_and_other_income", "concessions_lease_up_new_pct"): "C27",
    ("revenue_and_other_income", "concessions_lease_up_renewal_pct"): "C28",
    ("revenue_and_other_income", "concessions_stabilized_new_pct"): "C29",
    ("revenue_and_other_income", "concessions_stabilized_renewal_pct"): "C30",
    ("revenue_and_other_income", "renewal_probability_pct"): "C37",
    ("revenue_and_other_income", "lease_term_months"): "C38",
    ("revenue_and_other_income", "leased_units_per_month"): "C36",
    # Construction / timeline
    ("construction_schedule", "actuals_through_date"): "C5",
    ("construction_schedule", "model_start_date"): "C6",
    ("construction_schedule", "model_start_month"): "C7",
    ("construction_schedule", "transaction_closing_date"): "C11",
    ("construction_schedule", "construction_start_date"): "C12",
    ("construction_schedule", "construction_start_month"): "C13",
    ("construction_schedule", "construction_period_months"): "C14",
    ("construction_schedule", "construction_completion_month"): "C15",
    ("construction_schedule", "first_units_delivered_month"): "C16",
    ("construction_schedule", "absorption_start_month"): "C33",
    ("construction_schedule", "absorption_start_date"): "C34",
    ("construction_schedule", "last_units_delivered_month"): "C18",
    ("construction_schedule", "asset_management_model_start_month"): "C7",
    ("construction_schedule", "asset_management_model_start_date"): "C6",
    # Sources and uses
    ("sources_and_uses", "senior_loan_amount"): "J5",
    ("sources_and_uses", "preferred_equity_amount"): "J6",
    ("sources_and_uses", "investor_equity_amount"): "J7",
    ("sources_and_uses", "ace_development_equity"): "J8",
    ("sources_and_uses", "total_sources"): "J9",
    ("uses", "land_cost"): "J13",
    ("uses", "hard_costs_total"): "J14",
    ("uses", "soft_costs_total"): "J15",
    ("uses", "financing_costs"): "J16",
    ("uses", "operating_reserve"): "J17",
    ("uses", "senior_interest_reserve"): "J18",
    ("uses", "total_uses"): "J19",
}

UNIT_MIX_START_ROW = 23
UNIT_MIX_COLUMNS = {
    "unit_type": "H",
    "num_units": "I",
    "avg_sf": "J",
    "rent": "K",
    "rent_psf": "L",
    "original_label": "H",
}


def _coerce_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (datetime, date)):
        return to_excel(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Percent strings like "6%" -> 0.06
        if text.endswith("%"):
            try:
                return float(text.rstrip("%").replace(",", "")) / 100.0
            except Exception:
                return text
        # Currency / numeric strings
        cleaned = text.replace(",", "").replace("$", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return float(cleaned)
        except Exception:
            pass
        # ISO date
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return to_excel(dt)
        except Exception:
            return text
    return value


def _apply_scalar_values(ws, mapped: Dict[str, Any], applied: List[ExportAppliedField]) -> None:
    for (table, field), cell in SCALAR_CELL_MAP.items():
        table_val = mapped.get(table)
        if not isinstance(table_val, dict):
            continue
        raw = table_val.get(field)
        coerced = _coerce_value(raw)
        if coerced is None:
            continue
        ws[cell].value = coerced
        applied.append(ExportAppliedField(table=table, field=field, cell=cell, value=raw))


def _apply_unit_mix(ws, mapped: Dict[str, Any], applied: List[ExportAppliedField]) -> None:
    rows = mapped.get("unit_mix")
    if not isinstance(rows, list):
        return
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        target_row = UNIT_MIX_START_ROW + idx
        for field, col in UNIT_MIX_COLUMNS.items():
            if field not in row:
                continue
            raw = row.get(field)
            coerced = _coerce_value(raw)
            if coerced is None:
                continue
            cell = f"{col}{target_row}"
            ws[cell].value = coerced
            applied.append(ExportAppliedField(table="unit_mix", field=field, cell=cell, value=raw))


def export_mapping(session_id: str, mapping: MappingResult) -> ExportResponse:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template workbook not found at {TEMPLATE_PATH}")

    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / f"{session_id}-model.xlsx"
    shutil.copy(TEMPLATE_PATH, tmp_path)

    wb = load_workbook(tmp_path)
    if TARGET_SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"Sheet '{TARGET_SHEET_NAME}' not found in template")
    ws = wb[TARGET_SHEET_NAME]

    applied_fields: List[ExportAppliedField] = []
    _apply_scalar_values(ws, mapping.mapped, applied_fields)
    _apply_unit_mix(ws, mapping.mapped, applied_fields)

    wb.save(tmp_path)

    folder = f"{settings.cloudinary_base_folder}/exports/{session_id}".rstrip("/")
    upload_res = upload_raw(str(tmp_path), public_id="model-input", folder=folder)

    # Generate signed URL for private file access (valid for 4 hours)
    public_id = upload_res.get("public_id", "")
    signed_url = cloudinary.utils.private_download_url(
        public_id,
        "xlsx",
        resource_type="raw",
        type="private",
        expires_at=int((datetime.utcnow().timestamp()) + 14400),
    )

    return ExportResponse(download_url=signed_url, applied_fields=applied_fields)
