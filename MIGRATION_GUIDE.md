# Database Migration Guide

## New Tables Added

This update adds two new tables for enhanced security monitoring:

1. **login_attempts** - Track all login attempts for brute-force detection
2. **audit_logs** - Log security-critical events for compliance

## How to Migrate

### Option 1: Automatic (Restart App)

The easiest way - just restart your application:

```bash
# Stop the app
sudo systemctl stop eidosspeech

# Start the app (init_db() runs automatically)
sudo systemctl start eidosspeech
```

The `init_db()` function in `app/main.py` lifespan will automatically create the new tables.

### Option 2: Manual Migration Script

If you want to migrate without restarting:

```bash
# Run migration script
python migrate_db.py
```

### Option 3: Manual SQL

If you prefer to run SQL directly:

```sql
-- Create login_attempts table
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    success BOOLEAN NOT NULL,
    user_agent VARCHAR(500),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_email_timestamp ON login_attempts(email, timestamp);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_timestamp ON login_attempts(ip_address, timestamp);
CREATE INDEX IF NOT EXISTS ix_login_attempts_email ON login_attempts(email);
CREATE INDEX IF NOT EXISTS ix_login_attempts_ip_address ON login_attempts(ip_address);
CREATE INDEX IF NOT EXISTS ix_login_attempts_timestamp ON login_attempts(timestamp);

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(255),
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(500),
    details VARCHAR(1000),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_timestamp ON audit_logs(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_timestamp ON audit_logs(action, timestamp);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs(timestamp);
```

## Verify Migration

Check if tables were created:

```bash
sqlite3 data/db/eidosspeech.db ".tables"
```

You should see:
- api_keys
- audit_logs ✨ NEW
- blacklist
- daily_usage
- login_attempts ✨ NEW
- registration_attempts
- token_revocations
- users

## What These Tables Do

### login_attempts
- Tracks every login attempt (success and failure)
- Enables brute-force detection (auto-block after 5 failed attempts in 15 min)
- Provides forensic data for security analysis
- Auto-cleanup after 30 days

### audit_logs
- Logs security-critical events:
  - Password resets
  - API key regeneration
  - Admin actions (ban user, etc.)
- Compliance-ready audit trail
- Auto-cleanup after 90 days

## Troubleshooting

### Error: "unable to open database file"

Create the data directory:
```bash
mkdir -p data/db
```

### Error: "table already exists"

This is safe to ignore - the migration is idempotent (safe to run multiple times).

### Check Migration Status

```bash
# Check if new tables exist
sqlite3 data/db/eidosspeech.db "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('login_attempts', 'audit_logs');"
```

Should return:
```
login_attempts
audit_logs
```

## Rollback (if needed)

If you need to rollback (not recommended):

```sql
DROP TABLE IF EXISTS login_attempts;
DROP TABLE IF EXISTS audit_logs;
```

Note: This will lose all login attempt and audit log data.
