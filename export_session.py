#!/usr/bin/env python3
"""
Instagram Session Exporter for InstaReach v3 (FINAL WORKING VERSION)
Compatible with ALL instagrapi versions
"""

import json
import os
import sys
import time

# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────
def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_success(text): print(f"✅ {text}")
def print_error(text): print(f"❌ {text}")
def print_warning(text): print(f"⚠️  {text}")
def print_info(text): print(f"ℹ️  {text}")

# ─────────────────────────────────────────────
# CHECK DEPENDENCY
# ─────────────────────────────────────────────
def check_instagrapi():
    try:
        import instagrapi
        return True
    except ImportError:
        return False

def install_help():
    print_error("instagrapi not installed!")
    print("\nRun this command:\n")
    print("   pip install instagrapi\n")
    sys.exit(1)

# ─────────────────────────────────────────────
# SESSION EXPORT
# ─────────────────────────────────────────────
def export_session(username, password):
    from instagrapi import Client

    print_info(f"Logging in as @{username}...")

    try:
        cl = Client()

        # mimic human delay
        time.sleep(2)

        cl.login(username, password)
        print_success("Login successful!")

        # ── Fetch account info (safe)
        try:
            info = cl.account_info()
            print_info(f"Account: @{info.username}")
            print_info(f"User ID: {info.pk}")
        except:
            print_warning("Could not fetch account info (safe to ignore)")

        # ─────────────────────────────
        # 🔥 CRITICAL SESSION FIX
        # ─────────────────────────────
        session_data = cl.get_settings()

        # ✅ FIX: extract cookies properly (ALL versions supported)
        cookies_dict = {}

        try:
            # method 1 (new versions)
            for cookie in cl.private.cookies:
                cookies_dict[cookie.name] = cookie.value
        except:
            try:
                # method 2 fallback
                cookies_dict = cl.get_cookies()
            except:
                cookies_dict = {}

        if not cookies_dict:
            print_error("Cookies are EMPTY → session will NOT work")
            print_warning("Try logging into Instagram manually first")
            return None

        session_data["cookies"] = cookies_dict

        # ─────────────────────────────
        # SAVE FILE
        # ─────────────────────────────
        filename = f"session_{username.lower()}.json"

        with open(filename, "w") as f:
            json.dump(session_data, f, indent=2)

        size_kb = os.path.getsize(filename) / 1024
        print_success(f"Session saved → {filename} ({size_kb:.2f} KB)")

        # ─────────────────────────────
        # VERIFY SESSION
        # ─────────────────────────────
        print_info("Verifying session...")

        with open(filename, "r") as f:
            check = json.load(f)

        if not check.get("cookies"):
            print_error("Verification failed: cookies missing")
            return None

        print_success("Session verified (cookies present)")

        return filename

    except Exception as e:
        msg = str(e).lower()

        if "challenge" in msg or "checkpoint" in msg:
            print_error("Instagram checkpoint triggered")
            print("\nDo this:")
            print("1. Open Instagram app")
            print("2. Complete verification")
            print("3. Wait 5–10 minutes")
            print("4. Run script again")

        elif "password" in msg or "incorrect" in msg:
            print_error("Wrong password OR Instagram blocked login")

        elif "rate" in msg:
            print_error("Rate limited → wait 1–2 hours")

        else:
            print_error(f"Login failed: {e}")

        return None

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print_header("Instagram Session Exporter (FINAL VERSION)")

    if not check_instagrapi():
        install_help()

    print("Enter your Instagram credentials:\n")

    username = input("Username (no @): ").strip().lower()
    password = input("Password: ").strip()

    if not username or not password:
        print_error("Username and password required")
        return

    if "@" in username:
        username = username.replace("@", "")
        print_warning(f"Removed @ → {username}")

    session_file = export_session(username, password)

    if not session_file:
        print_error("Session generation failed")
        return

    # ─────────────────────────────
    # NEXT STEPS
    # ─────────────────────────────
    print_header("NEXT STEPS")

    print("1. Upload session file:")
    print(f"   → {session_file}")
    print(f"   → nodejs/data/sessions/{session_file}")

    print("\n2. Restart your app")

    print("\n3. Add account in InstaReach:")
    print("   Username → your username")
    print("   Password → LEAVE EMPTY")

    print("\n4. Run campaign")

    print("\nExpected log:")
    print("   ✅ Session loaded")

    print("\n" + "=" * 60)
    print_success("DONE — your system should now work")
    print("=" * 60 + "\n")

# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Cancelled")
    except Exception as e:
        print_error(f"Unexpected error: {e}")