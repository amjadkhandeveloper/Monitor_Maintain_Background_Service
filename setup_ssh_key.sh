#!/bin/bash

# Script to generate SSH key for GitHub account: amjadkhandeveloper
# Email: amjadkhandeveloper@gmail.com

SSH_KEY_NAME="id_ed25519_github_amjadkhandeveloper"
SSH_KEY_PATH="$HOME/.ssh/$SSH_KEY_NAME"
EMAIL="amjadkhandeveloper@gmail.com"

echo "=== SSH Key Setup for GitHub ==="
echo "Account: amjadkhandeveloper"
echo "Email: $EMAIL"
echo ""

# Check if key already exists
if [ -f "$SSH_KEY_PATH" ]; then
    echo "⚠️  SSH key already exists at: $SSH_KEY_PATH"
    read -p "Do you want to generate a new one? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Using existing key..."
        exit 0
    fi
fi

# Generate SSH key
echo "Generating SSH key..."
ssh-keygen -t ed25519 -C "$EMAIL" -f "$SSH_KEY_PATH" -N ""

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SSH key generated successfully!"
    echo ""
    echo "📋 Your public key (copy this to GitHub):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    cat "${SSH_KEY_PATH}.pub"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Next steps:"
    echo "1. Copy the public key above"
    echo "2. Go to: https://github.com/settings/keys"
    echo "3. Click 'New SSH key'"
    echo "4. Paste the key and save"
    echo ""
    echo "5. Add key to SSH agent:"
    echo "   eval \"\$(ssh-agent -s)\""
    echo "   ssh-add $SSH_KEY_PATH"
    echo ""
    echo "6. Test connection:"
    echo "   ssh -T git@github.com"
else
    echo "❌ Failed to generate SSH key"
    exit 1
fi

