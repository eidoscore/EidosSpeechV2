-- Delete User and All Related Data
-- Replace 'khoerulanwar752@gmail.com' with the email you want to delete

-- 1. Get user_id first (optional, for verification)
SELECT id, email, full_name, is_verified, created_at 
FROM users 
WHERE email = 'khoerulanwar752@gmail.com';

-- 2. Delete related data (in order to avoid foreign key constraints)

-- Delete daily usage records
DELETE FROM daily_usage 
WHERE api_key_id IN (
    SELECT id FROM api_keys 
    WHERE user_id IN (
        SELECT id FROM users WHERE email = 'khoerulanwar752@gmail.com'
    )
);

-- Delete API keys
DELETE FROM api_keys 
WHERE user_id IN (
    SELECT id FROM users WHERE email = 'khoerulanwar752@gmail.com'
);

-- Delete audit logs
DELETE FROM audit_logs 
WHERE user_id IN (
    SELECT id FROM users WHERE email = 'khoerulanwar752@gmail.com'
);

-- Delete login attempts
DELETE FROM login_attempts 
WHERE email = 'khoerulanwar752@gmail.com';

-- 3. Finally, delete the user
DELETE FROM users 
WHERE email = 'khoerulanwar752@gmail.com';

-- 4. Verify deletion
SELECT COUNT(*) as remaining_users 
FROM users 
WHERE email = 'khoerulanwar752@gmail.com';
-- Should return 0

-- 5. Check all related data is gone
SELECT 
    (SELECT COUNT(*) FROM users WHERE email = 'khoerulanwar752@gmail.com') as users_count,
    (SELECT COUNT(*) FROM api_keys WHERE user_id IN (SELECT id FROM users WHERE email = 'khoerulanwar752@gmail.com')) as api_keys_count,
    (SELECT COUNT(*) FROM daily_usage WHERE api_key_id IN (SELECT id FROM api_keys WHERE user_id IN (SELECT id FROM users WHERE email = 'khoerulanwar752@gmail.com'))) as usage_count,
    (SELECT COUNT(*) FROM audit_logs WHERE user_id IN (SELECT id FROM users WHERE email = 'khoerulanwar752@gmail.com')) as audit_count,
    (SELECT COUNT(*) FROM login_attempts WHERE email = 'khoerulanwar752@gmail.com') as login_attempts_count;
-- All should return 0
