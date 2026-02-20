# Public APIs GitHub Submission Guide

## Repository
https://github.com/public-apis/public-apis

## Submission Format

Add to the appropriate category in `README.md`:

```markdown
| API | Description | Auth | HTTPS | CORS |
|---|---|---|---|---|
| [eidosSpeech](https://eidosspeech.xyz) | Free text-to-speech API with 1,200+ voices in 75+ languages | `apiKey` | Yes | Yes |
```

## Category
**Text - Speech**

## Full Entry Details

### API Name
eidosSpeech

### Description
Free text-to-speech API with 1,200+ voices in 75+ languages powered by Microsoft Edge TTS

### Link
https://eidosspeech.xyz

### Auth Type
`apiKey`

### HTTPS
Yes

### CORS
Yes

## Additional Info for PR Description

```
### API Information
- **Name:** eidosSpeech
- **Category:** Text - Speech
- **Description:** Free text-to-speech API with 1,200+ neural voices across 75+ languages. Powered by Microsoft Edge TTS.
- **Website:** https://eidosspeech.xyz
- **Documentation:** https://eidosspeech.xyz/api-docs
- **Authentication:** API Key (X-API-Key header)
- **HTTPS:** Yes
- **CORS:** Yes (enabled for all origins)

### Key Features
- 1,200+ neural voices
- 75+ languages supported
- Free tier: 30 requests/day
- Direct MP3 output
- No credit card required
- Rate limit headers
- File caching

### API Endpoint
```
POST https://eidosspeech.xyz/api/v1/tts
```

### Example Request
```bash
curl -X POST https://eidosspeech.xyz/api/v1/tts \
  -H "X-API-Key: esk_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"en-US-JennyNeural"}' \
  --output audio.mp3
```

### Why This API Should Be Included
- Completely free tier (no credit card required)
- Well-documented REST API
- Active maintenance and support
- Useful for developers building voice applications
- Alternative to paid services like Google Cloud TTS
```

## Steps to Submit

### Option 1: Via GitHub Web Interface (Easiest)

1. **Fork the repository**
   - Go to: https://github.com/public-apis/public-apis
   - Click "Fork" button (top right)

2. **Edit README.md**
   - In your fork, navigate to `README.md`
   - Click the pencil icon (Edit)
   - Find the "Text - Speech" section
   - Add the entry in alphabetical order:
   ```markdown
   | [eidosSpeech](https://eidosspeech.xyz) | Free text-to-speech API with 1,200+ voices in 75+ languages | `apiKey` | Yes | Yes |
   ```

3. **Commit changes**
   - Scroll down to "Commit changes"
   - Title: `Add eidosSpeech API`
   - Description: Use the "Additional Info" from above
   - Click "Commit changes"

4. **Create Pull Request**
   - Go to your fork
   - Click "Contribute" → "Open pull request"
   - Title: `Add eidosSpeech - Free TTS API`
   - Description: Paste the "Additional Info" section
   - Click "Create pull request"

### Option 2: Via Git CLI

```bash
# 1. Fork the repo on GitHub first, then clone your fork
git clone https://github.com/YOUR_USERNAME/public-apis.git
cd public-apis

# 2. Create a new branch
git checkout -b add-eidosspeech

# 3. Edit README.md
# Find "Text - Speech" section and add:
# | [eidosSpeech](https://eidosspeech.xyz) | Free text-to-speech API with 1,200+ voices in 75+ languages | `apiKey` | Yes | Yes |

# 4. Commit changes
git add README.md
git commit -m "Add eidosSpeech API"

# 5. Push to your fork
git push origin add-eidosspeech

# 6. Create PR on GitHub
# Go to: https://github.com/YOUR_USERNAME/public-apis
# Click "Compare & pull request"
```

## PR Template

**Title:**
```
Add eidosSpeech - Free TTS API
```

**Description:**
```markdown
## API Information
- **Name:** eidosSpeech
- **Category:** Text - Speech
- **Description:** Free text-to-speech API with 1,200+ neural voices across 75+ languages
- **Website:** https://eidosspeech.xyz
- **Documentation:** https://eidosspeech.xyz/api-docs
- **Authentication:** API Key
- **HTTPS:** ✅ Yes
- **CORS:** ✅ Yes

## Key Features
- 🎙️ 1,200+ neural voices
- 🌍 75+ languages (English, Indonesian, Japanese, Spanish, etc.)
- 🆓 Free tier: 30 requests/day
- 🚀 Direct MP3 output
- 💳 No credit card required
- 📊 Rate limit headers included

## Example Usage
```bash
curl -X POST https://eidosspeech.xyz/api/v1/tts \
  -H "X-API-Key: esk_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"en-US-JennyNeural"}' \
  --output audio.mp3
```

## Why Include This API?
- Truly free tier (no credit card required)
- Well-documented REST API
- Active development and support
- Useful alternative to paid TTS services
- Open for developers worldwide

## Checklist
- [x] API is free or has a free tier
- [x] API is well documented
- [x] API is publicly accessible
- [x] HTTPS enabled
- [x] CORS enabled
- [x] Added in alphabetical order
- [x] Follows the format guidelines
```

## Important Notes

### Requirements (Must Meet)
- ✅ API must be free or have a free tier
- ✅ API must be publicly accessible
- ✅ API must have documentation
- ✅ HTTPS must be enabled
- ✅ Entry must be in alphabetical order
- ✅ Must follow the exact format

### Common Rejection Reasons (Avoid)
- ❌ Not in alphabetical order
- ❌ Wrong format
- ❌ Broken links
- ❌ API requires payment only
- ❌ No documentation
- ❌ Duplicate entry

### Tips for Approval
1. ✅ Double-check alphabetical order
2. ✅ Test all links before submitting
3. ✅ Use exact format from other entries
4. ✅ Be patient (may take days/weeks for review)
5. ✅ Respond to reviewer comments promptly

## Expected Timeline

- **Submission:** Immediate
- **Review:** 1-7 days
- **Approval:** 1-14 days
- **Merge:** After approval

## After Approval

### Benefits
- 🔗 High-quality backlink (DA 90+)
- 📈 500-1,000 monthly referral visits
- 🎯 Developer audience
- 💪 Credibility boost
- 🔍 Better SEO rankings

### Track Results
- Monitor referral traffic in Google Analytics
- Use UTM: `?utm_source=github&utm_medium=public-apis&utm_campaign=listing`
- Track API signups from this source

## Alternative: Awesome Lists

If Public APIs takes too long, also submit to:

1. **awesome-tts** (if exists)
2. **awesome-speech**
3. **awesome-free-apis**
4. **awesome-developer-tools**

Same process, just find the relevant awesome list and submit PR.

## Status Tracking

- [ ] Fork repository
- [ ] Add entry to README.md
- [ ] Create pull request
- [ ] PR submitted
- [ ] PR reviewed
- [ ] PR approved
- [ ] PR merged
- [ ] Monitor traffic

## Next Steps

1. **Right now:** Fork and submit PR (15 minutes)
2. **This week:** Monitor PR for comments
3. **After merge:** Track referral traffic
4. **Ongoing:** Update entry if API changes

---

**Ready to submit?** Follow Option 1 (Web Interface) - it's the easiest! 🚀
