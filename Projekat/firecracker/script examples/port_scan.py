# handler.py
import socket

def main():
    print("--- [Napad] Pokusavam skeniranje mreze hosta ---")
    
    target_hosts = ["127.0.0.1", "192.168.1.1", "google.com"]
    ports = [80, 8080]
    
    for host in target_hosts:
        for port in ports:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect((host, port))
                print(f"[!] USPEH: Uspostavio vezu sa {host}:{port}")
                s.close()
            except Exception as e:
                print(f"[-] Nemam pristup mreznoj lokaciji {host}:{port}: {e}")

main()