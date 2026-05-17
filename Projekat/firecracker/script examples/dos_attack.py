# handler.py
import time

def main():
    print("--- [Napad] Pokrecem Denial of Service (DoS) ---")
    
    # CPU napad kroz beskorisno racunanje
    print("[*] Pokrecem CPU stres...")
    start = time.time()
    while time.time() - start < 2:
        _ = 2 ** 1000000  # Trosi CPU cikluse sekundu-dve
        
    print("[*] CPU preziveo. Pokrecem agresivnu alokaciju RAM-a...")
    huge_list = []
    try:
        # Beskonacno dodajemo velike blokove podataka u memoriju
        while True:
            huge_list.append("X" * 10_000_000)  # Dodaj po 10MB u svakom krugu
            print(f"[+] Alocirano trenutno: {len(huge_list) * 10} MB")
    except MemoryError:
        print("[-] Uhvacen MemoryError unutar masine!")
    except Exception as e:
        print(f"[-] Greska: {e}")

main()