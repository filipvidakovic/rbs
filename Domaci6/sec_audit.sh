#!/bin/bash
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================="
echo -e "${GREEN}Starting security system overview...${NC}"
echo "================================================="

echo -e "\n${YELLOW}[+] Checking kernel version:${NC}"
uname -r

echo -e "\n${YELLOW}[+] Searching for users with root privileges (UID 0):${NC}"
awk -F: '($3 == "0") {print $1}' /etc/passwd

echo -e "\n${YELLOW}[+] Searching for users with empty passwords (requires root):${NC}"
sudo awk -F: '($2 == "") {print $1}' /etc/shadow

echo -e "\n${YELLOW}[+] Searching for 'sudo' group users:${NC}"
grep '^sudo:.*$' /etc/group | cut -d: -f4

echo -e "\n${YELLOW}[+] Searching for users with interactive shell access:${NC}"
grep -E '/bin/(bash|sh|zsh)$' /etc/passwd | cut -d: -f1

echo -e "\n${YELLOW}[+] Searching for users in 'adm' group (can read system logs):${NC}"
grep '^adm:.*$' /etc/group | cut -d: -f4

echo -e "\n================================================="
echo -e "${GREEN}Overview finished.${NC}"