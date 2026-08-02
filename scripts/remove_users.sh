#!/bin/bash
#
# remove_users.sh - Remove Linux users from the system
# Usage: ./remove_users.sh [-r] username1 [username2 ...]
#   -r  Also remove home directories and mail spools
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REMOVE_HOME=false

# Protected users that should never be removed
PROTECTED_USERS=("root" "nobody" "daemon" "bin" "sys" "sync" "games" "man" "lp" "mail" "news" "uucp" "proxy" "www-data" "backup" "list" "irc" "gnats" "systemd-network" "systemd-resolve" "messagebus" "sshd")

usage() {
    echo "Usage: $0 [-r] username1 [username2 ...]"
    echo ""
    echo "Options:"
    echo "  -r    Remove home directory and mail spool"
    echo ""
    echo "Example:"
    echo "  $0 jsmith jdoe           # Remove users, keep home dirs"
    echo "  $0 -r jsmith jdoe        # Remove users and their home dirs"
    exit 1
}

is_protected() {
    local user="$1"
    for protected in "${PROTECTED_USERS[@]}"; do
        if [[ "$user" == "$protected" ]]; then
            return 0
        fi
    done
    return 1
}

user_exists() {
    id "$1" &>/dev/null
}

remove_user() {
    local username="$1"
    
    # Check if user is protected
    if is_protected "$username"; then
        echo -e "${RED}ERROR: Cannot remove protected system user '$username'${NC}"
        return 1
    fi
    
    # Check if user exists
    if ! user_exists "$username"; then
        echo -e "${YELLOW}WARNING: User '$username' does not exist, skipping${NC}"
        return 0
    fi
    
    # Build userdel command
    local cmd="userdel"
    if [[ "$REMOVE_HOME" == true ]]; then
        cmd="$cmd -r"
    fi
    cmd="$cmd $username"
    
    echo -e "Removing user: ${YELLOW}$username${NC}"
    
    if $cmd 2>&1; then
        echo -e "${GREEN}Successfully removed user '$username'${NC}"
    else
        echo -e "${RED}Failed to remove user '$username'${NC}"
        return 1
    fi
}

# Check for root privileges
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    exit 1
fi

# Parse options
while getopts ":rh" opt; do
    case $opt in
        r)
            REMOVE_HOME=true
            ;;
        h)
            usage
            ;;
        \?)
            echo -e "${RED}Invalid option: -$OPTARG${NC}"
            usage
            ;;
    esac
done
shift $((OPTIND - 1))

# Check for usernames
if [[ $# -eq 0 ]]; then
    echo -e "${RED}ERROR: No usernames provided${NC}"
    usage
fi

# Confirmation prompt
echo ""
echo "The following users will be removed:"
for user in "$@"; do
    echo "  - $user"
done
if [[ "$REMOVE_HOME" == true ]]; then
    echo -e "${YELLOW}NOTE: Home directories and mail spools will also be deleted${NC}"
fi
echo ""
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""

# Process each username
failed=0
for username in "$@"; do
    if ! remove_user "$username"; then
        ((failed++)) || true
    fi
done

echo ""
if [[ $failed -eq 0 ]]; then
    echo -e "${GREEN}All users processed successfully${NC}"
else
    echo -e "${YELLOW}Completed with $failed error(s)${NC}"
    exit 1
fi
