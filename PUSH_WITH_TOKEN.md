# Push Using Personal Access Token

## Issue
Git is using cached credentials from a different account. We need to use a Personal Access Token.

## Solution: Use Personal Access Token

### Step 1: Create Personal Access Token
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name: `ProcessProgram Push`
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
5. Click "Generate token"
6. **COPY THE TOKEN IMMEDIATELY** (you won't see it again!)

### Step 2: Push Using Token

When you run `git push`, it will ask for:
- **Username**: `amjadkhandeveloper`
- **Password**: Paste your Personal Access Token (NOT your GitHub password)

### Alternative: Configure Git Credential Helper

You can also configure Git to use the token:

```bash
# Remove old remote
git remote remove origin

# Add remote with token in URL (temporary)
git remote add origin https://amjadkhandeveloper:YOUR_TOKEN@github.com/amjadkhandeveloper/Monitor_Maintain_Background_Service.git

# Push
git push -u origin main

# Then remove token from URL for security
git remote set-url origin https://github.com/amjadkhandeveloper/Monitor_Maintain_Background_Service.git
```

### Or Use SSH (if network allows)

If SSH works later, you can switch:
```bash
git remote set-url origin git@github.com:amjadkhandeveloper/Monitor_Maintain_Background_Service.git
```

