import os
import threading
import requests
from flask import Flask

# Flask App Initialization (Render Port Binding Ke Liye)
app = Flask(__name__)

# Terminal Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_firebase_status(url):
    """
    Firebase Realtime Database ka accurate status check karta hai.
    HTTP Status Code ke sath Response Body ko inspect karta hai.
    """
    url = url.strip()
    if not url:
        return None

    clean_url = url.split("?")[0].rstrip("/")
    target_url = f"{clean_url}/.json"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        response = requests.get(target_url, headers=headers, timeout=7)
        body = response.text.lower()
        status = response.status_code

        # 1. Deactivated ya Disabled Check
        if "database disabled" in body or "project disabled" in body:
            return {"url": clean_url, "status": "DEAD", "reason": "Database Disabled", "color": RED}

        # 2. Permission Denied (Active DB par rules locked hain)
        elif "permission denied" in body:
            return {"url": clean_url, "status": "ACTIVE_LOCKED", "reason": "Permission Denied (Locked)", "color": YELLOW}

        # 3. Open / Accessible Database (Data read ho raha hai ya Empty hai)
        elif status == 200:
            return {"url": clean_url, "status": "ACTIVE_OPEN", "reason": "Open Read Access", "color": GREEN}

        # 4. Other Error Codes
        else:
            return {"url": clean_url, "status": "DEAD", "reason": f"HTTP {status}", "color": RED}

    except requests.exceptions.Timeout:
        return {"url": clean_url, "status": "ERROR", "reason": "Connection Timeout", "color": RED}
    except requests.exceptions.RequestException:
        return {"url": clean_url, "status": "ERROR", "reason": "Network Error", "color": RED}

def run_checker_task():
    """Background Thread Me Sahi Se Execute Hone Waala Main Logic"""
    print("=== Firebase Realtime Database Accurate Checker Started ===\n")
    
    file_path = "urls.txt"
    
    if not os.path.exists(file_path):
        print(f"{RED}Error: '{file_path}' file nahi mili! Folder me 'urls.txt' add karein.{RESET}")
        return

    with open(file_path, "r") as file:
        urls = [line.strip() for line in file if line.strip()]

    print(f"Total URLs to check: {len(urls)}\n" + "-"*40)

    active_urls = []
    dead_urls = []

    for index, url in enumerate(urls, 1):
        result = check_firebase_status(url)
        if result:
            color = result["color"]
            print(f"[{index}/{len(urls)}] {color}[{result['status']}] {result['url']} -> {result['reason']}{RESET}")
            
            if "ACTIVE" in result["status"]:
                active_urls.append(result["url"])
            else:
                dead_urls.append(result["url"])

    # Output Files Me Save Karein
    with open("active_result.txt", "w") as f:
        f.write("\n".join(active_urls))

    print("-" * 40)
    print(f"{GREEN}Checking Completed!{RESET}")
    print(f"🟢 Total Active: {len(active_urls)}")
    print(f"🔴 Total Dead/Disabled: {len(dead_urls)}")
    print(f"\nSaved Active URLs in: active_result.txt")

@app.route('/')
def health_check():
    # Render Dashboard Ke Liye Health Check Route
    return "Firebase Checker Service is Running!"

if __name__ == "__main__":
    # Main Task Ko Background Thread Me Start Karein
    thread = threading.Thread(target=run_checker_task)
    thread.daemon = True
    thread.start()

    # Render ka Dynamic Port Listen Karein
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
