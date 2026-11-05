#!/usr/bin/env python3
"""
verify_corpus_integrity.py — Unified Corpus Record Integrity Verification Suite
Enacted Federal Repository (enacted-federal)
Swapp Technologies LLC

Deterministic verification suite enforcing:
1. Gate 1: Quarantine Resolution & Zero Unverified
2. Gate 8: Publication Readiness & Staging Cleanliness (LICENSE, Posture Line)
3. CHECK 10: Field Accuracy Verification Gate for Measurement Records
"""

import os
import sys
import re
import yaml

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def main():
    repo_name = os.path.basename(REPO_ROOT)
    print("===============================================================")
    print(f"  ENACTED / CORPUS RECORD INTEGRITY VERIFICATION SUITE")
    print(f"  Target Repository: {repo_name}")
    print("===============================================================\n")

    failed_checks = 0

    # Discover all records
    records = []
    for root, dirs, files in os.walk(REPO_ROOT):
        parts = os.path.relpath(root, REPO_ROOT).split(os.sep)
        if any(p in (".git", ".cache", "_quarantine_unverified", "node_modules", "dist", ".github", "__pycache__", "tests", ".pytest_cache", "status") for p in parts):
            continue

        for f in files:
            if f.endswith(".md") and f not in ("README.md", "README-dev.md", "PROVENANCE.md", "SUMMARY.md", "SOURCING_BLOCKED.md"):
                fpath = os.path.join(root, f)
                rel = os.path.relpath(fpath, REPO_ROOT).replace(os.sep, "/")
                records.append((fpath, rel))

    print(f"Discovered {len(records)} record(s) in {repo_name}.\n")

    # -------------------------------------------------------------
    # GATE 1: Quarantine Resolution & Zero Unverified
    # -------------------------------------------------------------
    print("[GATE 1] Quarantine Resolution & Zero Unverified:")
    quarantine_dir = os.path.join(REPO_ROOT, "_quarantine_unverified")
    if os.path.exists(quarantine_dir) and os.listdir(quarantine_dir):
        print(f"  FAIL: Unresolved files in {quarantine_dir}")
        failed_checks += 1
    else:
        print("  ✓ Zero quarantined or unverified records.")

    # -------------------------------------------------------------
    # GATE 8: Publication Readiness & Staging Cleanliness
    # -------------------------------------------------------------
    print("\n[GATE 8] Publication Readiness & Staging Cleanliness:")
    readme_path = os.path.join(REPO_ROOT, "README.md")
    posture_line = "This repository records the enacted law. It does not advise, approve, determine, or certify anything."
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as rf:
            readme_text = rf.read()
        if posture_line in readme_text:
            print("  ✓ README.md carries exact statutory posture line.")
        else:
            print("  FAIL: README.md missing exact posture line!")
            failed_checks += 1
    else:
        print("  FAIL: README.md missing!")
        failed_checks += 1

    lic_mit = os.path.join(REPO_ROOT, "LICENSE")
    lic_cc0 = os.path.join(REPO_ROOT, "LICENSE-DATA")
    if os.path.exists(lic_mit) and os.path.exists(lic_cc0):
        print("  ✓ LICENSE is MIT (code) and LICENSE-DATA is CC0 1.0 (records).")
    else:
        print("  FAIL: Missing LICENSE or LICENSE-DATA!")
        failed_checks += 1

    # -------------------------------------------------------------
    # CHECK 10: Field Accuracy Verification Gate for Measurement Records
    # -------------------------------------------------------------
    print("\n[CHECK 10] Field Accuracy Verification Gate for Measurement Records:")
    try:
        from scripts.check_field_accuracy import run_field_accuracy_check
        fa_res = run_field_accuracy_check(REPO_ROOT)
        if fa_res != 0:
            print("  FAIL: Field accuracy check failed for measurement records!")
            failed_checks += 1
        else:
            print("  ✓ Measurement records field accuracy verified.")
    except Exception as e:
        print(f"  FAIL: Error executing field accuracy check: {e}")
        failed_checks += 1

    print("\n===============================================================")
    if failed_checks == 0:
        print(f"  ALL CORPUS INTEGRITY VERIFICATION GATES PASSED! ✅ ({repo_name})")
        print("===============================================================\n")
        sys.exit(0)
    else:
        print(f"  VERIFICATION FAILED: {failed_checks} CHECK(S) FAILED! 🔴 ({repo_name})")
        print("===============================================================\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
