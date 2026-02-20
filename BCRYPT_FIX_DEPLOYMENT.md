# Bcrypt Fix Deployment Guide

## Issue Fixed
Registration was failing with error: `ValueError: password cannot be longer than 72 bytes`

## Root Cause
Bcrypt version 5.0.0+ introduced stricter validation that causes errors during internal initialization, even with short passwords. This is a known compatibility issue with passlib.

## Solution Applied
Pinned bcrypt to version 4.1.3 in requirements.txt

## Deployment Steps

### 1. Pull Latest Code
```bash
cd /path/to/eidosspeech
git pull origin main
```

### 2. Update Python Dependencies
```bash
# Activate virtual environment if using one
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Reinstall dependencies with pinned bcrypt version
pip install -r requirements.txt --upgrade
```

### 3. Verify Bcrypt Version
```bash
pip show bcrypt
# Should show: Version: 4.1.3
```

### 4. Restart Application
```bash
# If using systemd
sudo systemctl restart eidosspeech

# If using docker
docker-compose down
docker-compose up -d --build

# If running manually
# Stop the current process (Ctrl+C)
python run.py
```

### 5. Test Registration
Try registering a new user with a 15-character password to verify the fix works.

## What Changed

### Files Modified:
1. `requirements.txt` - Added `bcrypt==4.1.3` pin
2. `app/api/v1/auth.py` - Simplified hash_password() function
3. `app/models/schemas.py` - Kept 72-byte validation for clear errors
4. `AUDIT.md` - Documented the fix

### No Database Changes
No database migration needed. This is purely a library compatibility fix.

## Verification

After deployment, test:
```bash
# Test registration endpoint
curl -X POST https://eidosspeech.xyz/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123",
    "full_name": "Test User",
    "tos_accepted": true
  }'

# Should return 201 Created (not 500 Internal Server Error)
```

## Rollback Plan (if needed)

If issues occur:
```bash
# Revert to previous commit
git revert HEAD
pip install -r requirements.txt --upgrade
sudo systemctl restart eidosspeech
```

## References
- [Passlib bcrypt documentation](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html)
- Known issue: bcrypt 5.0.0+ strict validation incompatible with passlib
- Solution: Use stable bcrypt 4.1.3 version
