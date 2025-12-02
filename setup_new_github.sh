#!/bin/bash

# Script to configure Git for a new GitHub account
# Usage: ./setup_new_github.sh

echo "=== GitHub Account Setup ==="
echo ""
echo "Current Git configuration:"
git config user.name
git config user.email
echo ""

read -p "Enter your NEW GitHub username: " NEW_USERNAME
read -p "Enter your NEW GitHub email: " NEW_EMAIL

echo ""
echo "Setting Git configuration for this repository..."
git config user.name "$NEW_USERNAME"
git config user.email "$NEW_EMAIL"

echo ""
echo "New Git configuration:"
git config user.name
git config user.email

echo ""
echo "✅ Git configured successfully!"
echo ""
echo "Next steps:"
echo "1. If you need SSH keys, run: ssh-keygen -t ed25519 -C \"$NEW_EMAIL\""
echo "2. Add the SSH public key to your GitHub account"
echo "3. Test connection: ssh -T git@github.com"

