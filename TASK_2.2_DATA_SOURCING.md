# Task 2.2: Cost Database Data Sourcing

## Status: BLOCKED - Business Decision Required

**Technical Implementation**: ✅ COMPLETE (100%)
**Data Population**: ⏸️ PENDING - External Data Source Needed

---

## Summary

The production cost database infrastructure is **fully implemented and functional**. The system currently uses deterministic fallback costs for development/testing, but requires real utility cost data for production estimates.

**All code is complete** - only data sourcing/import remains.

---

## What's Been Implemented

### Service Layer (✅ Complete)

1. **Cost Lookup Service** (`src/apex/services/cost_lookup.py`)
   - `get_cost_by_code()` - Query CostCode table by code
   - `get_unit_cost()` - Extract unit costs from database
   - `fallback_unit_cost()` - Deterministic fallbacks when DB empty
   - `estimate_tangent_tower_cost()` - Voltage-aware parametric estimation

2. **Cost Database Integration** (`src/apex/services/cost_database.py`)
   - Lines 22, 47: CostLookupService integration
   - Lines 246-271: Database lookup with fallback logic
   - All quantity mapping and CBS hierarchy building complete

3. **Database Model** (`src/apex/models/database.py`)
   - CostCode table fully defined with indexes
   - Fields: code, description, unit_of_measure, source_database, unit costs

### Current Behavior

**Development/Testing**: Uses deterministic fallback costs
```python
# From cost_lookup.py:66-83
"tangent" → $75,000/EA
"dead-end" → $95,000/EA
"conductor" → $25/LF
"foundation" → $15,000/EA
"clearing" → $10,000/AC
```

**Production (Once Data Loaded)**: Queries CostCode table, falls back only if code not found

---

## What's Needed: Data Sourcing

You need to choose **ONE** of the following data sources:

### Option 1: RSMeans Cost Database (Recommended)

**Pros**:
- Industry-standard utility cost data
- Regular updates and escalation factors
- Regional adjustment factors included
- API access available

**Cons**:
- Requires subscription (~$1,500-5,000/year)
- May require data licensing agreement

**Implementation**:
- Subscribe to RSMeans Electrical Estimating
- Extract relevant cost codes (Section 26: Electrical)
- Import via CSV or API integration

---

### Option 2: Historical Utility Data

**Pros**:
- May already exist internally (past estimates)
- Free if available
- Specific to your utility's geography/practices

**Cons**:
- Requires data extraction/normalization
- May be incomplete or outdated
- Needs validation and escalation

**Implementation**:
- Contact estimating team for historical cost databases
- Export to CSV format (see schema below)
- Import using provided script

---

### Option 3: Industry Partners/Vendors

**Pros**:
- Specialized T&D cost data
- Often includes regional factors
- May include productivity rates

**Cons**:
- Vendor lock-in risk
- May require ongoing subscription
- Data format varies

**Potential Sources**:
- Xcel Energy (if partner agreement exists)
- Engineering consulting firms (HDR, Black & Veatch, etc.)
- Construction cost estimating vendors

---

### Option 4: Sample Data (For Testing Only)

**Pros**:
- Immediate functionality
- No external dependencies
- Proves system works

**Cons**:
- NOT suitable for production estimates
- Placeholder values only
- Requires replacement before go-live

**See**: `docs/sample_cost_codes.csv` (to be created)

---

## Implementation Steps (Once Data Source Selected)

### Step 1: Prepare Data

Create CSV file with this **exact format**:

```csv
code,description,unit_of_measure,source_database,unit_cost_material,unit_cost_labor,unit_cost_other,unit_cost_total
26.01.01.345,345kV Lattice Tangent Structure,EA,RSMeans,45000.00,28000.00,2000.00,75000.00
26.01.01.230,230kV Lattice Tangent Structure,EA,RSMeans,38000.00,22000.00,1500.00,61500.00
26.01.02.345,345kV Dead-End Structure,EA,RSMeans,55000.00,38000.00,2000.00,95000.00
26.02.01,ACSR Conductor 795 kcmil,LF,RSMeans,15.00,8.00,2.00,25.00
26.04.01,Drilled Pier Foundation,EA,RSMeans,8000.00,6000.00,1000.00,15000.00
26.05.01,Right-of-Way Clearing,AC,RSMeans,6000.00,3500.00,500.00,10000.00
```

**Required Fields**:
- `code` - Unique identifier (e.g., "26.01.01.345")
- `description` - Human-readable name
- `unit_of_measure` - "EA", "LF", "AC", etc.
- `source_database` - Data origin (e.g., "RSMeans", "UtilityHistorical")

**Cost Fields** (at least one required):
- `unit_cost_material` - Material cost per unit
- `unit_cost_labor` - Labor cost per unit
- `unit_cost_other` - Equipment/overhead per unit
- `unit_cost_total` - Total cost per unit (if null, will sum components)

---

### Step 2: Create Import Script

**File**: `scripts/import_cost_codes.py`

```python
"""
Import cost codes from CSV file into APEX database.

Usage:
    python scripts/import_cost_codes.py --file data/cost_codes.csv --source "RSMeans"
"""
import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apex.database.connection import SessionLocal
from apex.models.database import CostCode


def import_cost_codes(csv_file: Path, source_database: str = "RSMeans"):
    """Import cost codes from CSV."""
    db = SessionLocal()

    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)

            count = 0
            for row in reader:
                # Convert cost fields to Decimal
                cost_code = CostCode(
                    id=uuid4(),
                    code=row["code"],
                    description=row["description"],
                    unit_of_measure=row["unit_of_measure"],
                    source_database=row.get("source_database", source_database),
                    unit_cost_material=Decimal(row["unit_cost_material"]) if row.get("unit_cost_material") else None,
                    unit_cost_labor=Decimal(row["unit_cost_labor"]) if row.get("unit_cost_labor") else None,
                    unit_cost_other=Decimal(row["unit_cost_other"]) if row.get("unit_cost_other") else None,
                    unit_cost_total=Decimal(row["unit_cost_total"]) if row.get("unit_cost_total") else None,
                )

                db.add(cost_code)
                count += 1

                if count % 100 == 0:
                    db.commit()
                    print(f"Imported {count} cost codes...")

        db.commit()
        print(f"✅ Successfully imported {count} cost codes from {csv_file}")

    except Exception as exc:
        db.rollback()
        print(f"❌ Error importing cost codes: {exc}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import cost codes from CSV")
    parser.add_argument("--file", required=True, help="CSV file path")
    parser.add_argument("--source", default="RSMeans", help="Source database name")

    args = parser.parse_args()

    import_cost_codes(Path(args.file), args.source)
```

---

### Step 3: Run Import

```bash
# Create scripts directory if needed
mkdir -p scripts

# Copy import script (from above)
# Create/prepare your CSV file

# Set database environment variables
export AZURE_SQL_SERVER="your-server.database.windows.net"
export AZURE_SQL_DATABASE="apex_db"
# ... other required env vars

# Run import
python scripts/import_cost_codes.py --file data/cost_codes.csv --source "RSMeans"
```

---

### Step 4: Verify Import

```bash
# Connect to database and verify
sqlcmd -S your-server.database.windows.net -d apex_db -Q "SELECT COUNT(*) FROM cost_codes"
sqlcmd -S your-server.database.windows.net -d apex_db -Q "SELECT TOP 10 code, description, unit_cost_total FROM cost_codes"
```

**Or use Python**:

```python
from apex.database.connection import SessionLocal
from apex.services.cost_lookup import CostLookupService

db = SessionLocal()
lookup = CostLookupService()

# Get all codes
codes = lookup.get_all_codes(db)
print(f"Total cost codes: {len(codes)}")

# Test specific lookup
cost_code = lookup.get_cost_by_code(db, "26.01.01.345")
if cost_code:
    unit_cost = lookup.get_unit_cost(db, cost_code)
    print(f"345kV Tangent Tower: ${unit_cost}/EA")
else:
    print("Code not found - will use fallback")

db.close()
```

---

## Testing After Import

### Integration Test

Create test project and generate estimate:

```bash
# Run integration tests with real cost data
pytest tests/integration/test_api_estimates.py -v
```

### Manual API Test

```bash
# 1. Create project
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_number": "TEST-COST-001",
    "project_name": "Cost Database Test",
    "voltage_level": 345,
    "line_miles": 10.0,
    "terrain_type": "rolling"
  }'

# 2. Generate estimate (note project_id from response above)
curl -X POST http://localhost:8000/api/v1/estimates/generate \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<project_id>",
    "risk_factors": [],
    "confidence_level": 0.8,
    "monte_carlo_iterations": 1000
  }'

# 3. Check job status
curl http://localhost:8000/api/v1/jobs/<job_id>

# 4. Get estimate details
curl http://localhost:8000/api/v1/estimates/<estimate_id>
```

**Verify**:
- Line item costs match imported database values (not fallbacks)
- Total estimate is reasonable for project scope
- All cost codes have descriptions from database

---

## Acceptance Criteria

- [ ] Cost data source selected and approved
- [ ] CSV file created with minimum 20 representative cost codes
- [ ] Import script created and tested
- [ ] CostCode table populated (verify with SQL query)
- [ ] Integration test passes with database costs
- [ ] Manual estimate generation uses database costs (not fallbacks)
- [ ] Cost codes cover common T&D components:
  - [ ] Tangent structures (multiple voltages)
  - [ ] Dead-end structures
  - [ ] Conductor (ACSR/ACSS)
  - [ ] Foundations
  - [ ] ROW clearing
  - [ ] Substation equipment (if applicable)

---

## Timeline Estimate

**Option 1 (RSMeans)**: 2-4 weeks
- Procurement/subscription: 1-2 weeks
- Data extraction: 3-5 days
- Import/testing: 2-3 days

**Option 2 (Historical Data)**: 1-2 weeks
- Data gathering: 3-5 days
- Normalization: 3-5 days
- Import/testing: 2-3 days

**Option 3 (Vendor)**: 2-6 weeks
- Vendor evaluation: 1-2 weeks
- Agreement negotiation: 1-3 weeks
- Data delivery/import: 3-5 days

**Option 4 (Sample Data)**: 1 day
- Create sample CSV: 2-4 hours
- Import/test: 2-3 hours
- **NOTE**: Must be replaced before production

---

## Questions for Business Team

1. **Budget**: Is there budget for RSMeans subscription (~$2K-5K/year)?
2. **Historical Data**: Do we have access to past estimate databases?
3. **Partners**: Any existing vendor relationships for cost data?
4. **Timeline**: When is production go-live? (Determines urgency)
5. **Accuracy**: What cost variance is acceptable? (±10%, ±20%, ±30%?)
6. **Geography**: Do we need regional cost adjustments?
7. **Escalation**: Do we need time-based cost escalation?

---

## Current Fallback Costs (Development Only)

For reference, current hardcoded fallbacks in `cost_lookup.py:66-83`:

| Component | Unit | Fallback Cost | Production Range |
|-----------|------|---------------|------------------|
| Tangent Structure | EA | $75,000 | $40K-$150K (voltage-dependent) |
| Dead-End Structure | EA | $95,000 | $60K-$200K (voltage-dependent) |
| ACSR Conductor | LF | $25 | $15-$45 (size-dependent) |
| Foundation | EA | $15,000 | $8K-$35K (soil/depth-dependent) |
| ROW Clearing | AC | $10,000 | $5K-$25K (terrain-dependent) |

**These are order-of-magnitude estimates only** - not suitable for regulatory/contractual estimates.

---

## Next Steps

1. **Schedule business decision meeting** to select data source
2. **Assign data procurement owner** (Estimating Manager or Procurement)
3. **Set target date** for data availability
4. **Create sample CSV** (Option 4) if immediate testing needed
5. **Proceed to Phase 3** - infrastructure is ready for data import anytime

---

## Technical Support

If you need assistance with:
- CSV format questions → Check example above or contact dev team
- Import script errors → Check logs and database permissions
- Data validation → Run verification queries (see Step 4)
- Integration testing → Run pytest with `-v` flag for details

**Status**: Infrastructure ready, awaiting business decision on data source.
