"""
Reset trial period for developer testing.
Usage: python reset_trial.py
"""
import os
import sys

appdata = os.environ.get("APPDATA", "")
if not appdata:
    print("ERROR: APPDATA env var not found")
    sys.exit(1)

trial_dat = os.path.join(appdata, "Transkrib", "storage", "trial.dat")

if os.path.exists(trial_dat):
    os.remove(trial_dat)
    print(f"Deleted: {trial_dat}")
    print("Trial reset. Restart Transkrib to start a fresh trial.")
else:
    print(f"Not found: {trial_dat}")
    print("Trial is already reset (or was never started).")
