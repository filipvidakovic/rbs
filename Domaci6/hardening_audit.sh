#!/bin/bash
# =============================================================================
# hardening_audit.sh
# Linux System Hardening Audit Script
# Inspired by LinPEAS, scoped to: Filesystem Review,
# Services Review (SSH, MySQL, Crontab)
#
# Usage:
#   chmod +x hardening_audit.sh
#   sudo ./hardening_audit.sh          # full audit (recommended)
#   ./hardening_audit.sh               # partial audit (some checks need root)
#
# Output is color-coded:
#   [OK]   - no issue found
#   [WARN] - potential misconfiguration, review recommended
#   [INFO] - informational output, no direct security implication
#   [FAIL] - clear misconfiguration or security risk
#
# Documented security checks:
#   FILESYS-01  /etc/fstab mount options (noatime, noexec, nosuid)
#   FILESYS-02  Permissions on sensitive files (/etc/shadow, SSL keys, etc.)
#   FILESYS-03  SUID/SGID binaries
#   FILESYS-04  World-writable files
#   FILESYS-05  World-readable backup directories/files
#   SERVICE-01  Running services (ps)
#   SERVICE-02  SSH configuration (PermitRootLogin, Protocol, AllowTcpForwarding)
#   SERVICE-03  MySQL binding and anonymous users
#   SERVICE-04  Crontab scripts permissions
# =============================================================================

# ---------- colours ----------
RED='\033[0;31m'
YEL='\033[1;33m'
GRN='\033[0;32m'
CYN='\033[0;36m'
BLD='\033[1m'
RST='\033[0m'

ok()   { echo -e "  ${GRN}[OK]${RST}   $*"; }
warn() { echo -e "  ${YEL}[WARN]${RST} $*"; }
fail() { echo -e "  ${RED}[FAIL]${RST} $*"; }
info() { echo -e "  ${CYN}[INFO]${RST} $*"; }

section() {
    echo ""
    echo -e "${BLD}${CYN}======================================================${RST}"
    echo -e "${BLD}${CYN}  $*${RST}"
    echo -e "${BLD}${CYN}======================================================${RST}"
}

subsection() {
    echo ""
    echo -e "${BLD}--- $* ---${RST}"
}

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        warn "Check zahteva root pristup - preskočeno: $*"
        return 1
    fi
    return 0
}


# =============================================================================
# FILESYSTEM REVIEW
# =============================================================================
section "FILESYSTEM REVIEW"

# ---------------- FILESYS-01: /etc/fstab mount options ----------------------
subsection "FILESYS-01 | /etc/fstab opcije montiranja"
echo "  Bezbednosni cilj: Proverava kritične opcije za /tmp i /home:"
echo "  - noexec: sprečava izvršavanje binarnih fajlova"
echo "  - nosuid: sprečava setuid interpretaciju"
echo "  - noatime: NE treba koristiti jer briše informacije o pristupu fajlovima"
echo ""

if [ -f /etc/fstab ]; then
    info "Sadržaj /etc/fstab:"
    grep -v '^#' /etc/fstab | grep -v '^$' | sed 's/^/    /'
    echo ""

    # Check /tmp
    TMP_LINE=$(grep -E '\s/tmp\s' /etc/fstab 2>/dev/null)
    if [ -n "$TMP_LINE" ]; then
        echo "$TMP_LINE" | grep -q 'noexec' && ok "/tmp ima opciju noexec" || fail "/tmp nema opciju noexec - korisnici mogu izvršavati binarne fajlove iz /tmp"
        echo "$TMP_LINE" | grep -q 'nosuid' && ok "/tmp ima opciju nosuid" || warn "/tmp nema opciju nosuid"
        echo "$TMP_LINE" | grep -q 'noatime' && warn "/tmp koristi noatime - gube se podaci o pristupu (otežava forenziku)" || ok "/tmp ne koristi noatime"
    else
        warn "/tmp nije posebno montiran u /etc/fstab - preporučuje se odvojena particija sa noexec,nosuid"
    fi

    # Check /home
    HOME_LINE=$(grep -E '\s/home\s' /etc/fstab 2>/dev/null)
    if [ -n "$HOME_LINE" ]; then
        echo "$HOME_LINE" | grep -q 'noexec' && ok "/home ima opciju noexec" || warn "/home nema opciju noexec"
        echo "$HOME_LINE" | grep -q 'nosuid' && ok "/home ima opciju nosuid" || warn "/home nema opciju nosuid"
    else
        info "/home nije posebno montiran u /etc/fstab"
    fi
else
    warn "/etc/fstab nije pronađen"
fi

# ---------------- FILESYS-02: Sensitive file permissions ---------------------
subsection "FILESYS-02 | Dozvole na osetljivim fajlovima"
echo "  Bezbednosni cilj: Fajlovi sa lozinkama i privatnim ključevima ne smeju"
echo "  biti čitljivi svim korisnicima. Proveravaju se /etc/shadow, MySQL config,"
echo "  SSH ključevi, i eventualni backup-ovi shadow fajla."
echo ""

check_file_perm() {
    local filepath="$1"
    local desc="$2"
    if [ -e "$filepath" ]; then
        PERMS=$(stat -c "%a" "$filepath" 2>/dev/null)
        OWNER=$(stat -c "%U:%G" "$filepath" 2>/dev/null)
        # World-readable check (others read bit)
        if [ $((8#$PERMS & 8#004)) -ne 0 ]; then
            fail "$desc ($filepath) je čitljiv svim korisnicima! Dozvole: $PERMS, Vlasnik: $OWNER"
        else
            ok "$desc ($filepath) - Dozvole: $PERMS, Vlasnik: $OWNER"
        fi
    else
        info "$filepath nije pronađen (servis možda nije instaliran)"
    fi
}

check_file_perm /etc/shadow          "Shadow fajl (hešovi lozinki)"
check_file_perm /etc/mysql/my.cnf    "MySQL konfiguracija"
check_file_perm /etc/mysql/debian.cnf "MySQL Debian maintenance lozinka"

# Check for shadow backup files
SHADOW_BACKUPS=$(find /etc -name "shadow*" -not -name "shadow" 2>/dev/null)
if [ -n "$SHADOW_BACKUPS" ]; then
    while IFS= read -r f; do
        PERMS=$(stat -c "%a" "$f" 2>/dev/null)
        if [ $((8#$PERMS & 8#004)) -ne 0 ]; then
            fail "Backup shadow fajla $f je čitljiv svim korisnicima (dozvole: $PERMS) - KRITIČNO!"
        else
            warn "Pronađen backup shadow fajla: $f (dozvole: $PERMS) - proveriti da li je neophodan"
        fi
    done <<< "$SHADOW_BACKUPS"
else
    ok "Nisu pronađeni backup fajlovi /etc/shadow"
fi

# SSL private keys
SSL_KEYS=$(find /etc/ssl/private /etc/apache2/ssl /etc/nginx/ssl -name "*.key" -o -name "*.pem" 2>/dev/null | head -20)
if [ -n "$SSL_KEYS" ]; then
    while IFS= read -r k; do
        PERMS=$(stat -c "%a" "$k" 2>/dev/null)
        if [ $((8#$PERMS & 8#044)) -ne 0 ]; then
            fail "SSL privatni ključ $k je čitljiv neprivilegovanim korisnicima (dozvole: $PERMS)"
        else
            ok "SSL ključ $k - dozvole: $PERMS"
        fi
    done <<< "$SSL_KEYS"
fi

# ---------------- FILESYS-03: SUID/SGID binaries -----------------------------
subsection "FILESYS-03 | SUID/SGID binarni fajlovi"
echo "  Bezbednosni cilj: SUID fajlovi se izvršavaju sa privilegijama vlasnika."
echo "  Svaki SUID root fajl je potencijalni vektor eskalacije privilegija."
echo "  Lista se mora ručno proveriti - traže se nestandardni ili neočekivani fajlovi."
echo ""

info "SUID fajlovi (izvršavaju se kao vlasnik fajla):"
find / -perm -4000 -ls 2>/dev/null | grep -v '/proc' | sed 's/^/    /'
echo ""

# Flag non-standard SUID root files
KNOWN_SUID="/bin/su /bin/ping /bin/ping6 /bin/umount /bin/mount /usr/bin/passwd /usr/bin/sudo /usr/bin/newgrp /usr/bin/gpasswd /usr/bin/chsh /usr/bin/chfn /usr/sbin/uuidd"
UNEXPECTED=$(find / -perm -4000 -user root 2>/dev/null | grep -v '/proc' | while read -r f; do
    is_known=0
    for k in $KNOWN_SUID; do [ "$f" = "$k" ] && is_known=1 && break; done
    [ $is_known -eq 0 ] && echo "$f"
done)

if [ -n "$UNEXPECTED" ]; then
    warn "Potencijalno nestandardni SUID root fajlovi (zahtevaju ručnu proveru):"
    echo "$UNEXPECTED" | sed 's/^/    /'
else
    ok "Nisu pronađeni neočekivani SUID root fajlovi"
fi

info "SGID fajlovi (izvršavaju se sa grupnim privilegijama vlasnika):"
find / -perm -2000 -ls 2>/dev/null | grep -v '/proc' | sed 's/^/    /'

# ---------------- FILESYS-04: World-writable files ---------------------------
subsection "FILESYS-04 | Fajlovi zapisivi svim korisnicima (world-writable)"
echo "  Bezbednosni cilj: Fajlovi koje može menjati bilo koji korisnik su rizik."
echo "  Napadač koji dobije pristup može modifikovati konfiguracijske fajlove,"
echo "  skripte ili web sadržaj da bi proširio pristup."
echo ""

info "Fajlovi zapisivi svim korisnicima (isključen /proc):"
WW_FILES=$(find / -type f -perm -002 2>/dev/null | grep -v '/proc' | grep -v '/sys' | head -50)
if [ -n "$WW_FILES" ]; then
    COUNT=$(echo "$WW_FILES" | wc -l)
    fail "Pronađeno $COUNT world-writable fajlova:"
    echo "$WW_FILES" | head -20 | sed 's/^/    /'
    [ $COUNT -gt 20 ] && warn "  ... prikazano prvih 20 od $COUNT"
else
    ok "Nisu pronađeni world-writable fajlovi (van /proc)"
fi

# Web root specifically
WEB_ROOT=""
for d in /var/www /srv/www /usr/share/nginx/html; do
    [ -d "$d" ] && WEB_ROOT="$d" && break
done
if [ -n "$WEB_ROOT" ]; then
    WW_WEB=$(find "$WEB_ROOT" -type f -perm -002 2>/dev/null | head -20)
    if [ -n "$WW_WEB" ]; then
        fail "World-writable fajlovi u web root-u ($WEB_ROOT) - napadač može modifikovati web aplikaciju:"
        echo "$WW_WEB" | sed 's/^/    /'
    else
        ok "Nema world-writable fajlova u $WEB_ROOT"
    fi
fi

# ---------------- FILESYS-05: Backup directories -----------------------------
subsection "FILESYS-05 | Dozvole na backup direktorijumima i fajlovima"
echo "  Bezbednosni cilj: Backup fajlovi često sadrže osetljive podatke (shadow,"
echo "  konfiguracije, baze). Ako su čitljivi svim, napadač može doći do lozinki."
echo ""

BACKUP_DIRS="/backup /var/backup /var/backups /home/backup /root/backup"
for d in $BACKUP_DIRS; do
    if [ -d "$d" ]; then
        DPERMS=$(stat -c "%a" "$d" 2>/dev/null)
        if [ $((8#$DPERMS & 8#005)) -ne 0 ]; then
            fail "Backup direktorijum $d je čitljiv/pristupačan svim korisnicima (dozvole: $DPERMS)"
            # List contents
            find "$d" -maxdepth 2 -ls 2>/dev/null | sed 's/^/    /'
        else
            ok "Backup direktorijum $d - dozvole: $DPERMS"
        fi
    fi
done

# Check for .tgz/.tar.gz readable by all in common locations
READABLE_BACKUPS=$(find /root /home /var/backups /backup 2>/dev/null -name "*.tgz" -o -name "*.tar.gz" -o -name "*.tar" 2>/dev/null | while read -r f; do
    P=$(stat -c "%a" "$f" 2>/dev/null)
    [ $((8#$P & 8#004)) -ne 0 ] && echo "$f (dozvole: $P)"
done)
if [ -n "$READABLE_BACKUPS" ]; then
    fail "Arhive čitljive svim korisnicima:"
    echo "$READABLE_BACKUPS" | sed 's/^/    /'
else
    ok "Nisu pronađene arhive čitljive svim korisnicima"
fi


# =============================================================================
# SERVICES REVIEW
# =============================================================================
section "SERVICES REVIEW"

# ---------------- SERVICE-01: Running services -------------------------------
subsection "SERVICE-01 | Pokrenuti servisi"
echo "  Bezbednosni cilj: Identifikuje sve pokrenute servise. Svaki nepotreban"
echo "  servis povećava površinu napada i treba ga onemogućiti."
echo ""

info "Procesi koji ne spadaju u kernel (user-space servisi):"
ps -eo pid,user,comm,args 2>/dev/null | grep -v '^\s*[0-9]* root.*\[' | grep -v 'PID' | sed 's/^/    /'

echo ""
# Check for NTP
if ps -edf 2>/dev/null | grep -q '[n]tpd\|[c]hronyc\|[c]hronyd\|[t]imedatectl'; then
    ok "NTP servis je pokrenut (sinhronizacija vremena)"
else
    warn "NTP servis nije pronađen - vreme možda nije sinhronizovano (rizik za logove i SSL sertifikate)"
fi

# Check for syslog
if ps -edf 2>/dev/null | grep -qE '[r]syslogd|[s]yslogd|[j]ournald'; then
    ok "Syslog servis je pokrenut"
    # Check remote logging
    if [ -f /etc/rsyslog.conf ]; then
        if grep -qE '^\s*\*\.\*\s+@' /etc/rsyslog.conf 2>/dev/null; then
            ok "rsyslog je konfigurisan za slanje logova na udaljeni server"
        else
            warn "rsyslog NIJE konfigurisan za slanje logova na udaljeni server - logovi se čuvaju samo lokalno"
        fi
    fi
else
    fail "Syslog servis nije pokrenut - sistem možda ne beleži događaje!"
fi

# ---------------- SERVICE-02: SSH configuration ------------------------------
subsection "SERVICE-02 | SSH konfiguracija"
echo "  Bezbednosni cilj: SSH je najčešći vektor napada na servere."
echo "  Proverava se: zabrana direktnog root logina, isključenost SSHv1,"
echo "  zabrana TCP forwardinga, i korišćenje nestandardnog porta."
echo ""

SSH_CONFIG=""
for f in /etc/ssh/sshd_config /etc/sshd_config; do
    [ -f "$f" ] && SSH_CONFIG="$f" && break
done

if [ -n "$SSH_CONFIG" ]; then
    info "SSH konfiguracioni fajl: $SSH_CONFIG"
    echo ""

    # PermitRootLogin
    ROOT_LOGIN=$(grep -iE '^\s*PermitRootLogin' "$SSH_CONFIG" 2>/dev/null | awk '{print $2}' | tail -1)
    if [ -z "$ROOT_LOGIN" ]; then
        warn "PermitRootLogin nije eksplicitno postavljen - default je 'yes' u starijim verzijama"
    elif echo "$ROOT_LOGIN" | grep -qi '^no$'; then
        ok "PermitRootLogin je 'no' - direktan root login je zabranjen"
    elif echo "$ROOT_LOGIN" | grep -qi 'prohibit-password\|without-password'; then
        warn "PermitRootLogin je '$ROOT_LOGIN' - root može da se loguje ključem; preporučuje se 'no'"
    else
        fail "PermitRootLogin je '$ROOT_LOGIN' - root se može direktno ulogovati!"
    fi

    # Protocol version
    PROTO=$(grep -iE '^\s*Protocol' "$SSH_CONFIG" 2>/dev/null | awk '{print $2}' | tail -1)
    if [ -z "$PROTO" ]; then
        info "Protocol nije eksplicitno postavljen (moderne verzije OpenSSH koriste samo v2)"
    elif [ "$PROTO" = "2" ]; then
        ok "SSH protokol v2 (SSHv1 je onemogućen)"
    else
        fail "SSH protokol uključuje SSHv1 (vrednost: $PROTO) - SSHv1 ima poznate ranjivosti!"
    fi

    # AllowTcpForwarding
    TCP_FWD=$(grep -iE '^\s*AllowTcpForwarding' "$SSH_CONFIG" 2>/dev/null | awk '{print $2}' | tail -1)
    if [ -z "$TCP_FWD" ] || echo "$TCP_FWD" | grep -qi 'yes'; then
        warn "AllowTcpForwarding je '${TCP_FWD:-yes (default)}' - korisnici mogu koristiti SSH kao proxy/tunnel; preporučuje se 'no'"
    else
        ok "AllowTcpForwarding je '$TCP_FWD'"
    fi

    # Port
    SSH_PORT=$(grep -iE '^\s*Port' "$SSH_CONFIG" 2>/dev/null | awk '{print $2}' | tail -1)
    if [ -z "$SSH_PORT" ] || [ "$SSH_PORT" = "22" ]; then
        warn "SSH koristi standardni port 22 - laka meta za automatizovane brute-force skenere; razmotriti promenu porta"
    else
        ok "SSH koristi nestandardni port $SSH_PORT"
    fi

    # PasswordAuthentication
    PASS_AUTH=$(grep -iE '^\s*PasswordAuthentication' "$SSH_CONFIG" 2>/dev/null | awk '{print $2}' | tail -1)
    if [ -z "$PASS_AUTH" ] || echo "$PASS_AUTH" | grep -qi 'yes'; then
        warn "PasswordAuthentication je '${PASS_AUTH:-yes (default)}' - preporučuje se isključiti i koristiti samo SSH ključeve"
    else
        ok "PasswordAuthentication je '$PASS_AUTH' (samo ključevi)"
    fi

else
    warn "SSH konfiguracioni fajl nije pronađen - SSH možda nije instaliran"
fi

# ---------------- SERVICE-03: MySQL ------------------------------------------
subsection "SERVICE-03 | MySQL konfiguracija"
echo "  Bezbednosni cilj: MySQL ne sme da bude dostupan sa spoljnih interfejsa."
echo "  Proverava se bind-address i prisustvo korisnika bez lozinke."
echo ""

MYSQL_CONFIG=""
for f in /etc/mysql/my.cnf /etc/mysql/mysql.conf.d/mysqld.cnf /etc/my.cnf; do
    [ -f "$f" ] && MYSQL_CONFIG="$f" && break
done

if [ -n "$MYSQL_CONFIG" ]; then
    info "MySQL konfiguracioni fajl: $MYSQL_CONFIG"

    BIND=$(grep -iE '^\s*bind.address' "$MYSQL_CONFIG" 2>/dev/null | awk -F'=' '{print $2}' | tr -d ' ' | tail -1)
    if [ -z "$BIND" ]; then
        warn "bind-address nije postavljen u $MYSQL_CONFIG - MySQL može slušati na svim interfejsima"
    elif [ "$BIND" = "127.0.0.1" ] || [ "$BIND" = "localhost" ] || [ "$BIND" = "::1" ]; then
        ok "MySQL bind-address je '$BIND' - dostupan samo lokalno"
    else
        fail "MySQL bind-address je '$BIND' - MySQL je dostupan sa spoljnih interfejsa!"
    fi
else
    info "MySQL konfiguracioni fajl nije pronađen (MySQL možda nije instaliran)"
fi

# Check if MySQL is accessible without password (only if mysql client exists)
if command -v mysql &>/dev/null; then
    if mysql -u root --connect-timeout=3 -e "SELECT 1;" &>/dev/null 2>&1; then
        fail "MySQL root korisnik nema lozinku - pristup bez autentifikacije je moguć!"
    else
        ok "MySQL root korisnik zahteva lozinku (ili MySQL nije pokrenut)"
    fi
fi

# ---------------- SERVICE-04: Crontab script permissions ---------------------
subsection "SERVICE-04 | Dozvole na skriptama pozvanim iz crontab-a"
echo "  Bezbednosni cilj: Skripte koje izvršava root cron moraju biti zapisive"
echo "  samo od strane root-a. Inače, bilo koji korisnik može ubaciti maliciozan"
echo "  kod koji će biti izvršen sa root privilegijama."
echo ""

CRON_DIRS="/var/spool/cron/crontabs /var/spool/cron /etc/cron.d /etc/cron.daily /etc/cron.weekly /etc/cron.monthly"

for cron_dir in $CRON_DIRS; do
    [ -d "$cron_dir" ] || continue
    info "Pregled cron fajlova u $cron_dir:"

    find "$cron_dir" -type f 2>/dev/null | while read -r cfile; do
        # Extract script paths from cron entries
        grep -vE '^\s*#|^\s*$' "$cfile" 2>/dev/null | grep -oP '(/[^\s;|&>]+\.(sh|py|pl|rb))' | while read -r script; do
            if [ -f "$script" ]; then
                SPERMS=$(stat -c "%a" "$script" 2>/dev/null)
                SOWNER=$(stat -c "%U" "$script" 2>/dev/null)
                # World-writable
                if [ $((8#$SPERMS & 8#002)) -ne 0 ]; then
                    fail "Cron skripta $script je world-writable (dozvole: $SPERMS, vlasnik: $SOWNER) - eskalacija privilegija moguća!"
                elif [ $((8#$SPERMS & 8#020)) -ne 0 ]; then
                    warn "Cron skripta $script je group-writable (dozvole: $SPERMS, vlasnik: $SOWNER)"
                else
                    ok "Cron skripta $script - dozvole: $SPERMS, vlasnik: $SOWNER"
                fi
            fi
        done
    done
done

# Also check /etc/crontab directly
if [ -f /etc/crontab ]; then
    info "Sadržaj /etc/crontab:"
    grep -vE '^\s*#|^\s*$' /etc/crontab 2>/dev/null | sed 's/^/    /'
fi

# Check root's crontab
if require_root "root crontab" 2>/dev/null; then
    ROOT_CRON=$(crontab -u root -l 2>/dev/null | grep -vE '^\s*#|^\s*$')
    if [ -n "$ROOT_CRON" ]; then
        info "Root crontab zadaci:"
        echo "$ROOT_CRON" | sed 's/^/    /'

        # Check scripts in root's crontab
        echo "$ROOT_CRON" | grep -oP '(/[^\s;|&>]+\.(sh|py|pl|rb))' | while read -r script; do
            if [ -f "$script" ]; then
                SPERMS=$(stat -c "%a" "$script" 2>/dev/null)
                if [ $((8#$SPERMS & 8#002)) -ne 0 ]; then
                    fail "Root cron skripta $script je world-writable (dozvole: $SPERMS) - KRITIČNO!"
                else
                    ok "Root cron skripta $script - dozvole: $SPERMS"
                fi
            fi
        done
    else
        ok "Root nema zakazanih cron zadataka"
    fi
fi


# =============================================================================
# SUMMARY
# =============================================================================
section "SUMARNI PREGLED"

echo ""
echo -e "  Audit završen: $(date)"
echo -e "  Hostname:      $(hostname)"
echo -e "  Kernel:        $(uname -r)"
echo ""
echo -e "  Pregled pokrivenih oblasti:"
echo -e "    ${CYN}FILESYSTEM${RST}: /etc/fstab opcije, osetljivi fajlovi, SUID, world-writable, backupi"
echo -e "    ${CYN}SERVICES${RST}:   Pokrenuti procesi, SSH config, MySQL config, crontab skripte"
echo ""
echo -e "  Legenda: ${GRN}[OK]${RST} bezbedan | ${YEL}[WARN]${RST} proveriti | ${RED}[FAIL]${RST} bezbednosni problem | ${CYN}[INFO]${RST} informacija"
echo ""