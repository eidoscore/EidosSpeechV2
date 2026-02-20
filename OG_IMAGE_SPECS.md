# OG Image Specifications for eidosSpeech

## Required Image: og-image.png

### Dimensions
- **Width:** 1200px
- **Height:** 630px
- **Format:** PNG or JPG
- **Max Size:** < 1MB (recommended < 300KB)

### Design Requirements

#### Background
- Dark theme matching website (#050a06 or similar)
- Subtle gradient with emerald/brand colors

#### Content to Include
1. **Logo** - eidosSpeech icon (top-left or center)
2. **Main Text:**
   - "eidosSpeech"
   - "Free Text-to-Speech API"
3. **Key Features:**
   - "1,200+ AI Voices"
   - "75+ Languages"
   - "100% Free Forever"
4. **Visual Elements:**
   - Waveform or audio visualization
   - Language flags (🇺🇸 🇮🇩 🇯🇵 🇪🇸)
   - Subtle glow effects

#### Typography
- Font: Inter (Bold/Black for headings)
- Primary text: White (#FFFFFF)
- Accent text: Emerald (#10b981)

#### Brand Colors
- Primary: #10b981 (Emerald)
- Background: #050a06 (Dark)
- Text: #FFFFFF (White)
- Accent: #34d399 (Light Emerald)

### Safe Zones
- Keep important content within 1200x600px center area
- Some platforms crop edges

### File Location
Place the final image at: `app/static/og-image.png`

### Testing
After creating, test on:
- Facebook Sharing Debugger: https://developers.facebook.com/tools/debug/
- Twitter Card Validator: https://cards-dev.twitter.com/validator
- LinkedIn Post Inspector: https://www.linkedin.com/post-inspector/

### Quick Creation Options

#### Option 1: Canva
1. Go to Canva.com
2. Create custom size: 1200x630px
3. Use dark background
4. Add text and logo
5. Export as PNG

#### Option 2: Figma
1. Create 1200x630px frame
2. Design with brand colors
3. Export as PNG @2x

#### Option 3: Online Tools
- https://www.opengraph.xyz/
- https://www.bannerbear.com/
- https://www.canva.com/create/open-graph/

### Example Layout

```
┌─────────────────────────────────────────────────┐
│  [Logo]                                         │
│                                                 │
│           eidosSpeech                          │
│     Free Text-to-Speech API                    │
│                                                 │
│  🎙️ 1,200+ AI Voices  |  🌍 75+ Languages     │
│  ⚡ 100% Free Forever  |  🚀 No Credit Card    │
│                                                 │
│  🇺🇸 🇮🇩 🇯🇵 🇪🇸 🇫🇷 🇩🇪 🇨🇳 🇰🇷              │
│                                                 │
│                    eidosspeech.xyz             │
└─────────────────────────────────────────────────┘
```

### Current Status
⚠️ **TODO:** Create og-image.png and place in app/static/

Once created, the meta tags are already configured in landing.html:
```html
<meta property="og:image" content="https://eidosspeech.xyz/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
```
