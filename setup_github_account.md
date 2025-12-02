# Setting Up Multiple GitHub Accounts

## Option 1: Per-Repository Configuration (Recommended)

If you want to use different GitHub accounts for different repositories:

### For this repository (ProcessProgram):
```bash
cd /Users/Amjad/Documents/ProcessProgram
git config user.name "Your New GitHub Username"
git config user.email "your.new.email@example.com"
```

### For other repositories:
```bash
cd /path/to/other/repo
git config user.name "Your Other GitHub Username"
git config user.email "your.other.email@example.com"
```

## Option 2: Global Configuration Change

To change your global Git configuration:
```bash
git config --global user.name "Your New GitHub Username"
git config --global user.email "your.new.email@example.com"
```

## Option 3: Multiple GitHub Accounts with SSH Keys

### Step 1: Generate SSH Key for New Account
```bash
ssh-keygen -t ed25519 -C "your.new.email@example.com" -f ~/.ssh/id_ed25519_github_new
```

### Step 2: Add SSH Key to SSH Agent
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github_new
```

### Step 3: Add Public Key to GitHub
1. Copy the public key:
   ```bash
   cat ~/.ssh/id_ed25519_github_new.pub
   ```
2. Go to GitHub → Settings → SSH and GPG keys → New SSH key
3. Paste the public key

### Step 4: Configure SSH Config
Create/edit `~/.ssh/config`:
```
# GitHub Account 1 (Original)
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_rsa  # or your existing key

# GitHub Account 2 (New)
Host github-new
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_github_new
```

### Step 5: Use Different Host for New Account
When cloning or adding remotes for the new account:
```bash
git clone git@github-new:username/repo.git
# or
git remote set-url origin git@github-new:username/repo.git
```

## Quick Setup Script

Run this script to set up the new account for this repository:

```bash
# Replace with your actual details
NEW_GITHUB_USERNAME="your-username"
NEW_GITHUB_EMAIL="your-email@example.com"

cd /Users/Amjad/Documents/ProcessProgram
git config user.name "$NEW_GITHUB_USERNAME"
git config user.email "$NEW_GITHUB_EMAIL"
echo "Git configured for this repository:"
git config user.name
git config user.email
```

