# Email Troubleshooting Guide

## Issue: Emails Not Arriving in Inbox

### Symptoms
- Registration successful (201 Created)
- Log shows: `EMAIL_SENT provider=Brevo-SMTP to=user@example.com`
- But email never arrives in inbox

### Root Causes & Solutions

---

## 1. Check Spam/Junk Folder ⚠️

**Most Common Issue!**

Emails from new domains often land in spam initially.

**Action:**
1. Check your spam/junk folder
2. Mark email as "Not Spam" to train filter
3. Add `noreply@eidosspeech.xyz` to contacts

---

## 2. Brevo Sender Verification Required 🔴 CRITICAL

**Brevo requires sender email verification before sending!**

### Steps to Verify Sender in Brevo:

1. **Login to Brevo Dashboard**
   - Go to: https://app.brevo.com/

2. **Navigate to Senders**
   - Click "Senders" in left menu
   - Or go to: https://app.brevo.com/senders

3. **Add Sender Email**
   - Click "Add a sender"
   - Enter: `noreply@eidosspeech.xyz`
   - Brevo will send verification email to this address

4. **Verify the Sender**
   - Check email at `noreply@eidosspeech.xyz`
   - Click verification link from Brevo
   - Status should change to "Verified" ✅

### Alternative: Use Already Verified Email

If you can't access `noreply@eidosspeech.xyz`, use an email you already verified:

```bash
# In .env file
EIDOS_SMTP_FROM=eidosSpeech <your-verified-email@eidosstack.com>
```

**Note:** This is temporary. For production, verify the proper sender email.

---

## 3. Setup SPF Record for Domain 🔴 CRITICAL

**SPF (Sender Policy Framework) tells email servers that Brevo is allowed to send emails on behalf of your domain.**

### Add SPF Record to DNS:

1. **Login to your DNS provider** (Cloudflare, Namecheap, etc.)

2. **Add TXT record:**
   ```
   Type: TXT
   Name: @ (or eidosspeech.xyz)
   Value: v=spf1 include:spf.brevo.com ~all
   TTL: 3600 (or Auto)
   ```

3. **If you already have SPF record:**
   ```
   # OLD (example):
   v=spf1 include:_spf.google.com ~all
   
   # NEW (add Brevo):
   v=spf1 include:_spf.google.com include:spf.brevo.com ~all
   ```

4. **Verify SPF record:**
   ```bash
   # Wait 5-10 minutes for DNS propagation, then test:
   nslookup -type=TXT eidosspeech.xyz
   
   # Or use online tool:
   # https://mxtoolbox.com/spf.aspx
   ```

---

## 4. Setup DKIM (Recommended)

**DKIM adds digital signature to emails for better deliverability.**

### Steps:

1. **Get DKIM keys from Brevo:**
   - Go to: https://app.brevo.com/settings/keys/dkim
   - Click "Generate DKIM keys"
   - Copy the DKIM record

2. **Add DKIM record to DNS:**
   ```
   Type: TXT
   Name: mail._domainkey (or as shown by Brevo)
   Value: [paste DKIM value from Brevo]
   TTL: 3600
   ```

3. **Verify in Brevo:**
   - Click "Verify" button in Brevo dashboard
   - Should show "Verified" ✅

---

## 5. Check Email Provider Status

### Test Email Sending:

```bash
# Check email provider health
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  https://eidosspeech.xyz/api/v1/admin/email/status

# Response shows provider status:
{
  "providers": [
    {
      "name": "Brevo-SMTP",
      "available": true,
      "failure_count": 0,
      "cooldown_remaining_s": 0,
      "last_error": null
    }
  ]
}
```

### Manual Test Registration:

```bash
# Test with your email
curl -X POST https://eidosspeech.xyz/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-test-email@gmail.com",
    "password": "TestPassword123",
    "full_name": "Test User",
    "tos_accepted": true
  }'

# Check backend logs for:
# - EMAIL_SENT provider=Brevo-SMTP to=your-test-email@gmail.com
# - Any error messages
```

---

## 6. Common Brevo Errors

### Error: "550 5.7.0 Daily sending limit reached"
**Solution:** Brevo free tier = 300 emails/day. Wait 24 hours or upgrade plan.

### Error: "550 Sender not verified"
**Solution:** Verify sender email in Brevo dashboard (see #2 above).

### Error: "421 Service not available"
**Solution:** Temporary Brevo issue. Email will fallback to Mailtrap/Resend automatically.

---

## 7. Fallback Providers

If Brevo fails, emails automatically fallback to:

1. **Mailtrap SMTP** (if configured)
2. **Resend API** (if configured)

### Configure Fallback Providers:

```bash
# .env file

# Mailtrap (1000 emails/month free)
EIDOS_SMTP_FALLBACK_HOST=live.smtp.mailtrap.io
EIDOS_SMTP_FALLBACK_PORT=587
EIDOS_SMTP_FALLBACK_USERNAME=your_mailtrap_username
EIDOS_SMTP_FALLBACK_PASSWORD=your_mailtrap_password

# Resend (100 emails/day free)
EIDOS_RESEND_API_KEY=re_your_resend_api_key
```

---

## Quick Checklist ✅

Before going live, verify:

- [ ] Sender email verified in Brevo dashboard
- [ ] SPF record added to DNS (`include:spf.brevo.com`)
- [ ] DKIM record added to DNS (optional but recommended)
- [ ] Test email received in inbox (not spam)
- [ ] Fallback providers configured (Mailtrap/Resend)
- [ ] Email provider status endpoint returns healthy

---

## Testing Email Delivery

### 1. Test with Gmail/Yahoo/Outlook

Send test registration to different email providers:
- Gmail: `test@gmail.com`
- Yahoo: `test@yahoo.com`
- Outlook: `test@outlook.com`

### 2. Check Email Headers

If email arrives in spam, check headers for clues:
```
Authentication-Results: spf=pass / spf=fail
DKIM-Signature: pass / fail
```

### 3. Use Email Testing Tools

- **Mail Tester:** https://www.mail-tester.com/
  - Send test email to provided address
  - Get spam score and recommendations

- **MXToolbox:** https://mxtoolbox.com/
  - Check SPF, DKIM, DMARC records
  - Verify DNS configuration

---

## Production Recommendations

### For Best Deliverability:

1. ✅ **Verify sender email** in Brevo
2. ✅ **Setup SPF record** (`include:spf.brevo.com`)
3. ✅ **Setup DKIM** for email authentication
4. ✅ **Setup DMARC** (optional, advanced):
   ```
   Type: TXT
   Name: _dmarc
   Value: v=DMARC1; p=none; rua=mailto:dmarc@eidosspeech.xyz
   ```
5. ✅ **Warm up domain** - Start with low volume, gradually increase
6. ✅ **Monitor bounce rate** - Keep below 5%
7. ✅ **Configure fallback providers** - Mailtrap + Resend

### Email Best Practices:

- Use professional sender name: `eidosSpeech <noreply@eidosspeech.xyz>`
- Include unsubscribe link (for marketing emails)
- Keep HTML clean and simple
- Test on multiple email clients
- Monitor spam complaints

---

## Still Not Working?

### Check Backend Logs:

```bash
# View recent logs
docker logs eidosspeech-app --tail 100

# Or if running directly:
tail -f logs/app.log
```

Look for:
- `EMAIL_SENT` - Email sent successfully
- `EMAIL_FAIL` - Provider failed, trying next
- `ALL_EMAIL_PROVIDERS_FAILED` - All providers failed

### Contact Support:

If emails still not arriving after:
1. ✅ Sender verified in Brevo
2. ✅ SPF record added
3. ✅ Checked spam folder
4. ✅ Tested with multiple email providers

Then check:
- Brevo account status (not suspended)
- DNS records propagated (wait 24 hours)
- Firewall not blocking SMTP port 587

---

## Summary

**Most common fix:** Verify sender email in Brevo dashboard + Add SPF record to DNS.

**Quick fix for testing:** Use already verified email from eidosstack.com:
```bash
EIDOS_SMTP_FROM=eidosSpeech <verified-email@eidosstack.com>
```

**Production fix:** Verify `noreply@eidosspeech.xyz` in Brevo + Setup SPF/DKIM records.
