#!/bin/bash
# sys_net_audit.sh - Script for auditing network configurations, time sync, and logging

RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
CYN='\033[0;36m'
BLD='\033[1m'
NC='\033[0m'

echo -e "${BLD}${CYN}======================================================${NC}"
echo -e "${BLD}${CYN}  NETWORK, SYSTEM, TIME AND LOGGING - AUDIT${NC}"
echo -e "${BLD}${CYN}======================================================${NC}"

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${YEL}[WARN] Some checks (e.g., iptables) require root privileges. Running with sudo is recommended.${NC}\n"
fi

echo -e "${BLD}--- 1. OS AND KERNEL VERSION ---${NC}"
echo -e "${CYN}[INFO] Operating System version:${NC}"
[ -f /etc/debian_version ] && cat /etc/debian_version || cat /etc/os-release | grep PRETTY_NAME

echo -e "\n${CYN}[INFO] Kernel and uptime:${NC}"
uname -a
uptime

echo -e "\n${BLD}--- 2. NETWORK CONFIGURATIONS ---${NC}"
echo -e "${CYN}[INFO] Network interfaces and routing:${NC}"
ip a 2>/dev/null || ifconfig -a
echo ""
ip r 2>/dev/null || route -n

echo -e "\n${CYN}[INFO] DNS (/etc/resolv.conf) and Hosts (/etc/hosts):${NC}"
grep -v '^#' /etc/resolv.conf | grep -v '^$' || echo "No resolv.conf data found"
grep -v '^#' /etc/hosts | grep -v '^$'

echo -e "\n${BLD}--- 3. FIREWALL RULES ---${NC}"
if command -v iptables >/dev/null 2>&1; then
    echo -e "${CYN}[INFO] IPv4 iptables rules:${NC}"
    iptables -L -v -n 2>/dev/null || echo -e "${RED}[FAIL] No permission to read iptables (root required).${NC}"
else
    echo -e "${YEL}[WARN] iptables is not installed.${NC}"
fi

echo ""
if command -v ip6tables >/dev/null 2>&1; then
    echo -e "${CYN}[INFO] IPv6 iptables rules:${NC}"
    ip6tables -L -v -n 2>/dev/null || echo -e "${RED}[FAIL] No permission to read ip6tables.${NC}"
else
    echo -e "${YEL}[WARN] ip6tables is not installed.${NC}"
fi

echo -e "\n${BLD}--- 4. TIME (NTP) ---${NC}"
echo -e "${CYN}[INFO] Time zone:${NC}"
cat /etc/timezone 2>/dev/null || timedatectl | grep "Time zone"

echo -e "\n${CYN}[INFO] Active NTP processes:${NC}"
ps -edf | grep -E 'ntpd|chronyd|systemd-timesyncd' | grep -v grep || echo -e "${YEL}[WARN] No running NTP process detected.${NC}"

if command -v ntpq >/dev/null 2>&1; then
    echo -e "\n${CYN}[INFO] Synchronization status (ntpq -p -n):${NC}"
    ntpq -p -n 2>/dev/null
fi

echo -e "\n${BLD}--- 5. LOGGING (RSYSLOG) ---${NC}"
echo -e "${CYN}[INFO] Checking remote logging in /etc/rsyslog.conf:${NC}"
if [ -f /etc/rsyslog.conf ]; then
    if grep -q -E '@[a-zA-Z0-9_-]+' /etc/rsyslog.conf 2>/dev/null; then
        echo -e "${GRN}[OK] System is sending logs to a remote server:${NC}"
        grep -E '@[a-zA-Z0-9_-]+' /etc/rsyslog.conf
    else
        echo -e "${RED}[FAIL] Remote logging is not configured. If the server is compromised, local logs can be deleted.${NC}"
    fi
else
    echo -e "${YEL}[WARN] /etc/rsyslog.conf does not exist.${NC}"
fi

echo -e "\n${BLD}--- 6. INSTALLED PACKAGES ---${NC}"
if command -v dpkg >/dev/null 2>&1; then
    PKG_COUNT=$(dpkg -l | grep '^ii' | wc -l)
    echo -e "${CYN}[INFO] Total number of installed packages: ${PKG_COUNT}${NC}"
    echo -e "${YEL}Advice: It is recommended to check for unnecessary packages, such as graphical interfaces or games.${NC}"
fi

echo -e "\n${BLD}${GRN}Network, time, and logging audit completed.${NC}"