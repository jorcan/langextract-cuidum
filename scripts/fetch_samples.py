#!/usr/bin/env python3
"""
Fetch phonecalls from Odoo Cuidum PostgreSQL and save as JSON.
Usage:
    python scripts/fetch_samples.py [--limit 100] [--output data/samples/raw_calls.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def fetch_via_mcp(limit: int = 30) -> list[dict]:
    """Use MCP postgres tool to fetch calls - fallback to sample data."""
    from src.db import load_sample_calls
    print("⚠️  MCP direct query not available at runtime. Loading samples.")
    return load_sample_calls()[:limit]


def fetch_via_psycopg(limit: int = 30) -> list[dict]:
    """Fetch directly via psycopg2 using credentials from env."""
    import os
    import psycopg2
    import re

    # Read Cuidum DB URL from credentials
    with open(os.path.expanduser("~/.hermes/credentials.env")) as f:
        content = f.read()

    # Try to find the cuidum db URL
    # The MCP tool postgres has cuidum target configured
    # Check .env for DB_CUIDUM or similar
    env_path = os.path.expanduser("~/.hermes/.env")
    cuidum_url = None
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DB_CUIDUM=") or line.startswith("CUIDUM_DB_URL="):
                    cuidum_url = line.split("=", 1)[1].strip().strip('"\'')
                    break

    if not cuidum_url:
        print("No DB_CUIDUM URL found. Use MCP tool instead.")
        return fetch_via_mcp(limit)

    try:
        conn = psycopg2.connect(cuidum_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, partner_id, name, description, create_date, clave, subclave
            FROM crm_phonecall
            WHERE description IS NOT NULL AND description != ''
              AND LENGTH(description) > 100
            ORDER BY id DESC
            LIMIT %s
        """, (limit,))

        rows = []
        for row in cur.fetchall():
            rows.append({
                "id": row[0],
                "partner_id": row[1],
                "name": row[2],
                "description": row[3],
                "create_date": str(row[4]) if row[4] else None,
                "clave": row[5],
                "subclave": row[6],
            })
        cur.close()
        conn.close()
        print(f"✅ Fetched {len(rows)} records via psycopg2")
        return rows
    except Exception as e:
        print(f"❌ psycopg2 error: {e}")
        return fetch_via_mcp(limit)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", "-n", type=int, default=30)
    parser.add_argument("--output", "-o", default="data/samples/raw_calls.json")
    args = parser.parse_args()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent.parent / args.output

    rows = fetch_via_psycopg(args.limit)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved {len(rows)} calls to {output_path}")


if __name__ == "__main__":
    main()
