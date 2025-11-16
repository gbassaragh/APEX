"""
Import cost codes from CSV into the database.

Usage:
    python scripts/import_cost_codes.py --file data/cost_codes.csv --source RSMeans
"""
import argparse
import csv
import sys
from pathlib import Path
from uuid import uuid4

# Add src to path for app imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apex.database.connection import SessionLocal  # noqa: E402
from apex.models.database import CostCode  # noqa: E402


def import_cost_codes(csv_file: Path, source_database: str = "RSMeans") -> int:
    """Import cost codes from CSV."""
    db = SessionLocal()
    count = 0

    try:
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cost_code = CostCode(
                    id=uuid4(),
                    code=row["code"],
                    description=row["description"],
                    unit_of_measure=row.get("unit_of_measure"),
                    source_database=source_database,
                    unit_cost_material=_to_decimal(row.get("unit_cost_material")),
                    unit_cost_labor=_to_decimal(row.get("unit_cost_labor")),
                    unit_cost_other=_to_decimal(row.get("unit_cost_other")),
                    unit_cost_total=_to_decimal(row.get("unit_cost_total")),
                )
                db.add(cost_code)
                count += 1
                if count % 200 == 0:
                    db.commit()
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _to_decimal(value: str):
    """Convert CSV string to Decimal-compatible value or None."""
    if value is None or value == "":
        return None
    return float(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import cost codes from CSV")
    parser.add_argument("--file", required=True, help="Path to CSV file")
    parser.add_argument("--source", default="RSMeans", help="Source database label")
    args = parser.parse_args()

    imported = import_cost_codes(Path(args.file), args.source)
    print(f"Imported {imported} cost codes from {args.file}")
