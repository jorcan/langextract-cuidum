"""Enriquecer los FieldSpec de un schema con el vocabulario REAL de Odoo.

Cuando un campo mapea a una columna selection de res.partner (p.ej.
x_nivel_formativo, x_sexo), los valores permitidos NO son texto libre: son
los códigos de `ir_model_fields_selection`. Esto:

1. Restringe `allowed` del FieldSpec a los códigos reales de Odoo (mejora
   el acierto: el LLM no inventa vocabulario).
2. Añade al description la lista "código (label)" para que el LLM elija el
   código correcto.
3. Si el partner YA tiene un valor en esa columna, se devuelve en
   `known_values` para pasarlo como existing_data (no re-extraerlo).

El core sigue siendo agnóstico: esto es glue del adapter de Cuidum.
"""
from __future__ import annotations

import logging
from typing import Any

from core.schema import FieldSpec

logger = logging.getLogger(__name__)


def enrich_fields_with_odoo(
    fields: list[FieldSpec],
    partner_ctx: dict[str, Any] | None,
    odoo_field_to_schema: dict[str, str] | None = None,
) -> list[FieldSpec]:
    """Devuelve una copia de `fields` con `allowed` restringido al vocabulario Odoo.

    - fields: FieldSpecs del schema.
    - partner_ctx: salida de fetch_partner_selection_context(partner_id) →
      {"selections": {columna: {"opciones": [{value, label}], ...}}, ...}
    - odoo_field_to_schema: if provided, mapea columna Odoo → nombre de campo
      del schema (cuando el FieldSpec no declara `external_field`). Si el FieldSpec
      ya tiene `external_field`, gana ese.

    Solo afecta a campos con `external_field` que existan en selections como
    ttype='selection'. El resto se devuelve intacto.
    """
    if not partner_ctx:
        return list(fields)
    selections = partner_ctx.get("selections") or {}
    if not selections:
        return list(fields)

    out: list[FieldSpec] = []
    for spec in fields:
        odoo_col = spec.external_field
        if not odoo_col and odoo_field_to_schema:
            for col, field_name in odoo_field_to_schema.items():
                if field_name == spec.name:
                    odoo_col = col
                    break
        if not odoo_col or odoo_col not in selections:
            out.append(spec)
            continue

        opts = selections[odoo_col].get("opciones") or []
        if not opts:
            out.append(spec)
            continue

        codes = [o["value"] for o in opts]
        labels = ", ".join(f"{o['value']} ({o['label']})" for o in opts)
        enriched = spec.model_copy(deep=True)

        if enriched.type == "literal":
            # allowed real de Odoo (el vocabulario manda, no el hardcoded)
            enriched.allowed = codes
        elif enriched.type == "string":
            # textos libres que en Odoo son selection: forzar literal
            # (cambio de tipo declarativo: el JSON declara string pero el
            # vocabulario real es cerrado)
            enriched.type = "literal"
            enriched.allowed = codes
        base_desc = spec.description or ""
        sep = ": " if base_desc and not base_desc.rstrip().endswith(".") else " "
        enriched.description = (
            f"{base_desc}{sep}Valores permitidos en Odoo: {labels}"
        ).strip()
        out.append(enriched)

    return out


def existing_values_from_partner(
    fields: list[FieldSpec],
    partner_ctx: dict[str, Any] | None,
    odoo_field_to_schema: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Devuelve {nombre_de_campo: valor_actual_del_partner} para campos ya poblados.

    El extractor usa existing_data para NO re-extraer campos que Odoo ya
    tiene. Solo devuelve campos del schema que mapean a columnas selection
    con valor_actual no nulo.
    """
    if not partner_ctx:
        return {}
    selections = partner_ctx.get("selections") or {}
    out: dict[str, Any] = {}

    for spec in fields:
        odoo_col = spec.external_field
        if not odoo_col and odoo_field_to_schema:
            for col, field_name in odoo_field_to_schema.items():
                if field_name == spec.name:
                    odoo_col = col
                    break
        if not odoo_col or odoo_col not in selections:
            continue
        sel = selections[odoo_col]
        if sel.get("valor_actual") is not None:
            out[spec.name] = sel["label_actual"] or sel["valor_actual"]
    return out