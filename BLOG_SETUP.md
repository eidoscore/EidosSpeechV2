# Blog Setup Guide - eidosSpeech

## Overview
Simple blog implementation untuk eidosSpeech menggunakan static markdown files + FastAPI rendering.

**Approach:** Keep it simple - Markdown files → HTML rendering → SEO optimized

---

## File Structure

```
app/
├── static/
│   ├── blog/
│   │   └── index.html          # Blog homepage
│   └── css/
│       └── blog.css            # Blog-specific styles
├── blog/
│   ├── posts/
│   │   ├── 2026-02-20-youtube-ai-voice.md
│   │   ├── 2026-02-21-tts-api-tutorial.md
│   │   └── ...
│   └── metadata.json           # Post metadata (title, date, tags, etc)
└── api/
    └── v1/
        └── blog.py             # Blog API endpoints
```

---

## Implementation Steps

### Step 1: Create Blog Homepage

Create `app/static/blog/index.html`:
- List of blog posts
- Search functionality
- Category/tag filters
- Pagination
- RSS feed link

### Step 2: Create Blog Post Template

Create `app/static/blog/post.html`:
- Post content area
- Author info
- Published date
- Reading time
- Social sharing buttons
- Related posts
- Comments (optional)
- Newsletter signup

### Step 3: Create Blog API Endpoints

Add to `app/api/v1/blog.py`:

```python
from fastapi import APIRouter
from pathlib import Path
import markdown
import json
from datetime import datetime

router = APIRouter(prefix="/blog", tags=["blog"])

BLOG_DIR = Path("app/blog/posts")
METADATA_FILE = Path("app/blog/metadata.json")

@router.get("/posts")
async def list_posts(page: int = 1, per_page: int = 10, tag: str = None):
    """List all blog posts with pagination"""
    # Load metadata
    # Filter by tag if provided
    # Paginate
    # Return list
    pass

@router.get("/posts/{slug}")
async def get_post(slug: str):
    """Get single blog post by slug"""
    # Load markdown file
    # Parse frontmatter
    # Convert to HTML
    # Return post data
    pass

@router.get("/tags")
async def list_tags():
    """List all tags with post counts"""
    pass

@router.get("/rss")
async def rss_feed():
    """Generate RSS feed"""
    pass
```

### Step 4: Create Markdown Post Template

Template for new blog posts:

```markdown
---
title: "How to Add AI Voice to YouTube Videos (Free)"
slug: "youtube-ai-voice-tutorial"
date: "2026-02-20"
author: "eidosSpeech Team"
tags: ["tutorial", "youtube", "ai-voice"]
description: "Complete guide to adding AI voiceovers to YouTube videos using free TTS API"
image: "/static/blog/images/youtube-tutorial.png"
---

# How to Add AI Voice to YouTube Videos (Free)

Your content here...

## Step 1: Get Your API Key

...

## Step 2: Generate Audio

...

## Conclusion

...
```

### Step 5: Add Blog Routes to Main App

In `app/main.py`:

```python
from app.api.v1 import blog

# Include blog router
app.include_router(blog.router, prefix="/api/v1")

# Blog page routes
@app.get("/blog", include_in_schema=False)
async def blog_page():
    """Blog homepage"""
    path = STATIC_DIR / "blog" / "index.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Blog not found"}, status_code=404)

@app.get("/blog/{slug}", include_in_schema=False)
async def blog_post_page(slug: str):
    """Individual blog post"""
    path = STATIC_DIR / "blog" / "post.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "Post not found"}, status_code=404)
```

---

## Minimal MVP (Can Launch Today)

### Quick Start - Static HTML Only

1. **Create blog homepage** (`app/static/blog.html`):
   - Simple list of posts
   - Links to external platforms (Dev.to, Medium)
   - "Coming soon" message

2. **Cross-post to existing platforms**:
   - Write on Dev.to
   - Republish on Medium with canonical link
   - Link from eidosSpeech blog page

3. **Benefits**:
   - No backend needed
   - Can launch immediately
   - Still get SEO benefits
   - Easy to maintain

### Example Simple Blog Page

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Blog — eidosSpeech</title>
    <!-- Meta tags -->
</head>
<body>
    <h1>eidosSpeech Blog</h1>
    <p>Tutorials, guides, and insights about text-to-speech technology.</p>
    
    <div class="posts">
        <article>
            <h2><a href="https://dev.to/eidosspeech/youtube-ai-voice">
                How to Add AI Voice to YouTube Videos
            </a></h2>
            <p>Complete guide to adding AI voiceovers...</p>
            <span>Published on Dev.to</span>
        </article>
        
        <!-- More posts -->
    </div>
</body>
</html>
```

---

## Full Implementation (Future)

### Phase 1: Basic Blog (Week 1-2)
- [ ] Create blog homepage
- [ ] Create post template
- [ ] Add 5 initial posts
- [ ] Basic styling
- [ ] RSS feed

### Phase 2: Enhanced Features (Week 3-4)
- [ ] Search functionality
- [ ] Tag/category filtering
- [ ] Related posts
- [ ] Social sharing
- [ ] Reading time estimate

### Phase 3: Advanced Features (Month 2)
- [ ] Comments (Disqus or custom)
- [ ] Newsletter integration
- [ ] Analytics tracking
- [ ] A/B testing
- [ ] Personalized recommendations

---

## SEO Optimization for Blog

### Each Post Must Have:
1. **Meta tags**:
   ```html
   <title>Post Title — eidosSpeech Blog</title>
   <meta name="description" content="...">
   <link rel="canonical" href="https://eidosspeech.xyz/blog/slug">
   ```

2. **Open Graph**:
   ```html
   <meta property="og:type" content="article">
   <meta property="og:title" content="...">
   <meta property="og:image" content="...">
   <meta property="article:published_time" content="2026-02-20">
   ```

3. **Article Schema**:
   ```json
   {
     "@context": "https://schema.org",
     "@type": "Article",
     "headline": "...",
     "author": {...},
     "datePublished": "2026-02-20",
     "image": "..."
   }
   ```

4. **Breadcrumbs**:
   ```json
   {
     "@type": "BreadcrumbList",
     "itemListElement": [
       {"@type": "ListItem", "position": 1, "name": "Home", "item": "..."},
       {"@type": "ListItem", "position": 2, "name": "Blog", "item": "..."},
       {"@type": "ListItem", "position": 3, "name": "Post Title"}
     ]
   }
   ```

---

## Content Workflow

### Writing Process
1. **Research** - Keyword research, competitor analysis
2. **Outline** - Structure the post
3. **Write** - First draft
4. **Edit** - Grammar, clarity, SEO
5. **Images** - Create/find images
6. **Publish** - Deploy to site
7. **Promote** - Share on social media

### Tools Needed
- **Writing**: Google Docs, Notion
- **Grammar**: Grammarly, LanguageTool
- **SEO**: Ahrefs, SEMrush (or free alternatives)
- **Images**: Canva, Unsplash
- **Code snippets**: Carbon.now.sh
- **Analytics**: Google Analytics

---

## Quick Win: External Blog Strategy

### Instead of building blog infrastructure now:

1. **Write on Dev.to** (Primary):
   - Create eidosSpeech organization
   - Publish all content there
   - Great SEO, built-in audience
   - Free hosting

2. **Cross-post to Medium**:
   - Republish with canonical link to Dev.to
   - Reach different audience
   - Additional backlinks

3. **Link from eidosSpeech**:
   - Create simple `/blog` page
   - List posts with links to Dev.to
   - "Read on Dev.to" buttons

4. **Benefits**:
   - Launch today (no development)
   - Built-in audience
   - Better SEO (high DA platforms)
   - Easy to maintain
   - Can migrate later if needed

### Example Dev.to Setup

1. Create organization: https://dev.to/settings/organization
2. Customize with eidosSpeech branding
3. Write first post
4. Share on social media
5. Link from eidosspeech.xyz/blog

---

## Recommendation: Start Simple

### This Week:
1. ✅ Create simple `/blog` landing page
2. ✅ Set up Dev.to organization
3. ✅ Write first 2 posts on Dev.to
4. ✅ Link from eidosSpeech site

### Next Month:
5. Publish 8 more posts on Dev.to
6. Build backlinks
7. Monitor traffic
8. Decide if custom blog needed

### Later (If Needed):
9. Build custom blog infrastructure
10. Migrate content from Dev.to
11. Add advanced features

---

## Metrics to Track

### Traffic
- Blog page views
- Post views
- Referral traffic to main site
- Time on page

### Engagement
- Social shares
- Comments
- Newsletter signups
- API key signups from blog

### SEO
- Keyword rankings
- Backlinks from blog posts
- Domain authority impact
- Featured snippets

---

## Next Steps

**Option A: Quick Launch (Recommended)**
1. Create simple blog landing page
2. Set up Dev.to organization
3. Write first post
4. Launch today

**Option B: Full Build**
1. Build blog infrastructure (2-3 days)
2. Create post templates
3. Write first 5 posts
4. Launch next week

**My Recommendation:** Start with Option A, migrate to Option B later if needed.

---

## Resources

### Markdown Parsers (Python)
- `python-markdown` - Basic markdown
- `markdown-it-py` - Advanced features
- `mistune` - Fast parser

### Syntax Highlighting
- `Pygments` - Code highlighting
- `highlight.js` - Client-side

### RSS Feed
- `feedgen` - Python RSS generator

### Static Site Generators (Alternative)
- Hugo - Fast, Go-based
- Jekyll - Ruby-based
- Pelican - Python-based
- Next.js - React-based

---

## Conclusion

**Start simple, iterate fast.**

Launch with Dev.to cross-posting strategy today, build custom blog later if traffic justifies it. Focus on content quality over infrastructure.
