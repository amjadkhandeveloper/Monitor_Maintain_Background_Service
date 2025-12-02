# GitHub Setup Guide for amjadkhandeveloper

## ✅ Git Configuration Complete
- **Username**: amjadkhandeveloper
- **Email**: amjadkhandeveloper@gmail.com
- **Repository**: Initialized

## Next Steps: Connect to GitHub

### Option 1: Using SSH (Recommended)

1. **Generate SSH Key** (if you don't have one):
   ```bash
   ssh-keygen -t ed25519 -C "amjadkhandeveloper@gmail.com" -f ~/.ssh/id_ed25519_github_amjadkhandeveloper
   ```

2. **Add SSH Key to SSH Agent**:
   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519_github_amjadkhandeveloper
   ```

3. **Copy Public Key**:
   ```bash
   cat ~/.ssh/id_ed25519_github_amjadkhandeveloper.pub
   ```

4. **Add to GitHub**:
   - Go to: https://github.com/settings/keys
   - Click "New SSH key"
   - Paste your public key
   - Save

5. **Test Connection**:
   ```bash
   ssh -T git@github.com
   ```

### Option 2: Using HTTPS with Personal Access Token

1. **Create Personal Access Token**:
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `repo` (full control)
   - Copy the token

2. **Add Remote**:
   ```bash
   git remote add origin https://github.com/amjadkhandeveloper/ProcessProgram.git
   ```

3. **When Pushing**:
   - Username: `amjadkhandeveloper`
   - Password: Use your Personal Access Token (not your GitHub password)

## Initial Commit and Push

```bash
# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Java JAR Service Monitor"

# Add remote (replace with your actual repo URL)
git remote add origin git@github.com:amjadkhandeveloper/ProcessProgram.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Create Repository on GitHub First

Before pushing, create a new repository on GitHub:
1. Go to: https://github.com/new
2. Repository name: `ProcessProgram` (or any name you prefer)
3. Choose Public or Private
4. **Don't** initialize with README, .gitignore, or license (we already have files)
5. Click "Create repository"
6. Copy the repository URL and use it in the `git remote add origin` command above

