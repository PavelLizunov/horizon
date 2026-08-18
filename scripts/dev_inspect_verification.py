import json
import glob
from pathlib import Path

reports = sorted(glob.glob("data/verification/runs/*/reports/*.json"))
print(f"Total reports: {len(reports)}")
for p in reports[-10:]:
    with open(p, "r", encoding="utf-8") as f:
        r = json.load(f)
    print("FILE:", p)
    print("  item_id:", r.get("item_id"))
    print("  status_by_claim:", r.get("status_by_claim"))
    print("  verification_error:", r.get("verification_error"))
    print("  claim_results count:", len(r.get("claim_results", [])))
    for cr in r.get("claim_results", []):
        print("    claim:", cr.get("claim_id"), "status:", cr.get("status"), "errors:", cr.get("search_errors"), cr.get("fetch_errors"), cr.get("eval_error"))
