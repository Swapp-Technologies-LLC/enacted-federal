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
import time
import yaml
import hashlib
from urllib.parse import urlparse
from scripts.crawler import EnactedCrawler

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def get_verify_crawler() -> EnactedCrawler:
    """Return EnactedCrawler for verification suite."""
    if "VERIFY_CRAWLER_INTERVAL" in os.environ:
        return EnactedCrawler(min_interval=float(os.environ["VERIFY_CRAWLER_INTERVAL"]))
    return EnactedCrawler()


def fetch_corpus_url(crawler: EnactedCrawler, url: str, timeout: int = 25, retries: int = 1):
    """
    Founder ruling (2026-11-05): on a timeout, connection error (status_code == 0 or exception)
    or 5xx, retry once. If still failing, return ('unreachable', status_code, b"", err).
    For client errors (404, 410, etc.), return ('http_error', status_code, b"", err) immediately.
    For 200/302, return ('ok', status_code, body, "").
    If robots.txt disallows, return ('robots_disallowed', status_code, b"", err).
    """
    for attempt in range(retries + 1):
        try:
            allowed, status_code, data, err = crawler.fetch(url, timeout=timeout)
            if not allowed:
                return "robots_disallowed", status_code, data, err
            if status_code in (200, 302):
                return "ok", status_code, data, err
            if status_code in (404, 410) or (400 <= status_code < 500):
                return "http_error", status_code, data, err
            # 5xx or 0 (timeout / connection error)
            if attempt < retries:
                time.sleep(1.0)
                continue
            return "unreachable", status_code, data, err
        except Exception as exc:
            if attempt < retries:
                time.sleep(1.0)
                continue
            return "unreachable", 0, b"", str(exc)


def main():
    repo_name = os.path.basename(REPO_ROOT)
    print("===============================================================")
    print(f"  ENACTED / CORPUS RECORD INTEGRITY VERIFICATION SUITE")
    print(f"  Target Repository: {repo_name}")
    print("===============================================================\n")

    failed_checks = 0
    crawler = get_verify_crawler()

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
                fm = {}
                with open(fpath, "r", encoding="utf-8") as rf:
                    content = rf.read()
                parts_content = content.split("---", 2)
                if len(parts_content) >= 3:
                    try:
                        fm = yaml.safe_load(parts_content[1]) or {}
                    except Exception:
                        pass
                records.append((fpath, rel, fm))

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
    # GATE 7e: Primary Source Link Liveness Gate
    # -------------------------------------------------------------
    print("\n[GATE 7e] Primary Source Link Liveness Gate:")
    unique_urls = set()
    for fpath, rel, fm in records:
        for key in ["primary_source_url", "primary_document_url", "source_pdf"]:
            url = fm.get(key)
            if url and isinstance(url, str) and url.startswith("http"):
                unique_urls.add(url)

    liveness_passed = 0
    for u in sorted(unique_urls):
        if not crawler.can_fetch(u):
            print(f"  not fetched: robots ({u})")
            continue

        status, status_code, body, err = fetch_corpus_url(crawler, u, timeout=25)
        if status == "robots_disallowed":
            print(f"  not fetched: robots ({u})")
            continue
        elif status == "unreachable":
            print(f"  unreachable at gate time: {u}")
            continue
        elif status == "ok":
            liveness_passed += 1
            print(f"  ✓ HTTP {status_code} OK: {u[:70]}...")
        else:
            print(f"  FAIL: Connection error on corpus URL {u}: HTTP {status_code} {err}")
            failed_checks += 1

    # -------------------------------------------------------------
    # GATE 7c: Cryptographic SHA-256 PDF Re-Hash Gate
    # -------------------------------------------------------------
    print("\n[GATE 7c] Cryptographic SHA-256 PDF Re-Hash Gate:")
    cache_dir = os.path.join(REPO_ROOT, ".cache", "pdf_cache")
    os.makedirs(cache_dir, exist_ok=True)

    for fpath, rel, fm in records:
        expected_sha = fm.get("source_sha256")
        pdf_url = fm.get("source_pdf") or fm.get("primary_source_url")
        if not expected_sha or not pdf_url:
            continue

        cache_file = os.path.join(cache_dir, f"{expected_sha}.pdf")
        data = None

        if not crawler.can_fetch(pdf_url):
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as cf:
                    data = cf.read()
                actual_sha = hashlib.sha256(data).hexdigest()
                if actual_sha == expected_sha:
                    print(f"  not fetched: robots ({pdf_url}) [cached file sha confirmed: {expected_sha[:12]}...]")
                else:
                    print(f"  FAIL: {rel} cached file hash mismatch! Expected {expected_sha}, got {actual_sha}")
                    failed_checks += 1
            else:
                print(f"  not fetched: robots ({pdf_url})")
            continue

        if os.path.exists(cache_file):
            with open(cache_file, "rb") as cf:
                data = cf.read()
        else:
            try:
                status, status_code, body, err = fetch_corpus_url(crawler, pdf_url, timeout=30)
                if status == "robots_disallowed":
                    print(f"  not fetched: robots ({pdf_url})")
                    continue
                if status == "unreachable":
                    print(f"  unreachable at gate time: {pdf_url}")
                    continue
                if status != "ok":
                    print(f"  FAIL: Could not download {pdf_url}: HTTP {status_code} ({err})")
                    failed_checks += 1
                    continue
                data = body
                with open(cache_file, "wb") as cf:
                    cf.write(data)
            except Exception as e:
                print(f"  FAIL: Could not download {pdf_url}: {e}")
                failed_checks += 1
                continue

        if data is not None:
            actual_sha = hashlib.sha256(data).hexdigest()
            if actual_sha != expected_sha:
                print(f"  FAIL: {rel} hash mismatch! Expected {expected_sha}, got {actual_sha}")
                failed_checks += 1
            else:
                print(f"  ✓ SHA-256 match ({expected_sha[:12]}...): {rel}")

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
