# 🌐 URL Fetch Feature - Documentation

## Overview

The URL Fetch feature allows admins to extract content directly from web pages and add it to the knowledge base without manually downloading files.

## Features

✅ Fetch content from any public URL  
✅ Automatically extracts text and images from HTML pages  
✅ Supports documentation sites, articles, blog posts  
✅ Same processing as file uploads (chunking, embedding, image extraction)  
✅ Easy-to-use UI with mode toggle  

## How to Use

### Frontend (Admin Panel)

1. Go to KB Upload page: `http://localhost:5173/kb-upload/1`
2. Click the **"🌐 Fetch from URL"** button
3. Enter the URL (e.g., `https://docs.example.com/guide`)
4. Click **"Fetch & Index"**
5. Wait for processing (shows progress)
6. Success message shows chunks indexed

### Supported URLs

**✅ Works with:**
- Documentation pages (HTML)
- Blog articles (HTML)
- News articles (HTML)
- Plain text pages
- Any public web page with text content

**❌ Not supported:**
- PDFs hosted online (download and upload as file instead)
- Password-protected pages
- Pages requiring JavaScript rendering
- Binary files (images, videos, etc.)

## Technical Details

### Backend Endpoint

**POST** `/api/admin/fetch-url`

**Request Body:**
```json
{
  "url": "https://example.com/page",
  "bot_id": 1
}
```

**Response:**
```json
{
  "message": "URL content successfully fetched and indexed.",
  "url": "https://example.com/page",
  "file_name": "url_a3f2e1b4.html",
  "category": "general",
  "chunks_inserted": 15,
  "chunks_skipped": 0
}
```

### Processing Flow

```
1. User enters URL
   ↓
2. Backend fetches HTML content
   ↓
3. Saves as .html file in uploads/{bot_id}/
   ↓
4. Ingestion service processes:
   - Extracts text
   - Extracts images
   - Creates chunks
   - Generates embeddings
   ↓
5. Stores in database
   ↓
6. Ready for chat queries!
```

### Image Extraction

If the fetched page contains images:
- External images (http://...) → URL stored as-is
- Relative images → Attempted to download and store locally
- Images appear in chat responses when relevant

## Examples

### Example 1: Documentation Page

```
URL: https://fastapi.tiangolo.com/tutorial/first-steps/
Result: Extracts FastAPI tutorial content + code examples
```

### Example 2: Blog Article

```
URL: https://blog.example.com/how-to-setup-chatbot
Result: Extracts article text + screenshots
```

### Example 3: GitHub README

```
URL: https://raw.githubusercontent.com/user/repo/main/README.md
Result: Extracts markdown content (rendered as HTML)
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "URL must start with http://" | Invalid URL format | Use full URL with protocol |
| "Request timeout" | Page took >30s to load | Try again or use shorter page |
| "Connection error" | Can't reach URL | Check URL is accessible |
| "Unsupported content type" | Not HTML/text | Download file and upload instead |
| "HTTP error: 404" | Page not found | Check URL is correct |
| "HTTP error: 403" | Access forbidden | Page requires authentication |

### Timeout

- Default timeout: 30 seconds
- If page takes longer, request fails
- Solution: Download page manually and upload as file

## Security

### Protections in Place

✅ URL validation (must start with http:// or https://)  
✅ Content type checking (only HTML/text)  
✅ Timeout protection (30 seconds max)  
✅ Filename sanitization  
✅ Same security as file uploads  

### Limitations

- Only fetches public pages
- No authentication support
- No JavaScript rendering
- No recursive crawling (one page at a time)

## Use Cases

### 1. Import Documentation

```
Scenario: Add product documentation to knowledge base
Action: Fetch each doc page URL
Result: Users can ask questions about documentation
```

### 2. Add Blog Content

```
Scenario: Add company blog posts to chatbot
Action: Fetch blog post URLs
Result: Chatbot can reference blog content
```

### 3. Import FAQs

```
Scenario: Add FAQ page to knowledge base
Action: Fetch FAQ page URL
Result: Chatbot answers FAQ questions
```

### 4. Add External Resources

```
Scenario: Reference external guides/tutorials
Action: Fetch guide URLs
Result: Chatbot provides external resource info
```

## Comparison: URL Fetch vs File Upload

| Feature | URL Fetch | File Upload |
|---------|-----------|-------------|
| Speed | Slower (network) | Faster (local) |
| Convenience | Very easy | Requires download |
| File types | HTML, text only | All 18 formats |
| Images | Auto-extracted | Auto-extracted |
| Offline | ❌ Needs internet | ✅ Works offline |
| Large files | May timeout | Works fine |
| Best for | Public docs | PDFs, Office files |

## Tips & Best Practices

### ✅ Do:
- Use for public documentation pages
- Fetch one page at a time
- Verify URL is accessible before fetching
- Use for frequently updated content (re-fetch to update)

### ❌ Don't:
- Try to fetch password-protected pages
- Fetch very large pages (>5MB)
- Fetch binary files (PDFs, images)
- Expect JavaScript-rendered content

## Testing

### Test the Feature

1. **Test valid URL:**
   ```
   URL: https://example.com
   Expected: Success, content indexed
   ```

2. **Test invalid URL:**
   ```
   URL: not-a-url
   Expected: Error "URL must start with http://"
   ```

3. **Test 404 page:**
   ```
   URL: https://example.com/nonexistent
   Expected: Error "HTTP error: 404"
   ```

4. **Test with images:**
   ```
   URL: https://example.com/page-with-images
   Expected: Success, images extracted
   ```

## Troubleshooting

### Issue: "Request timeout"
**Solution:** Page is too large or slow. Download manually and upload as file.

### Issue: "Unsupported content type"
**Solution:** URL points to PDF or other file. Download and upload as file instead.

### Issue: "Connection error"
**Solution:** Check internet connection and URL accessibility.

### Issue: No images extracted
**Solution:** Images may be loaded via JavaScript. Download page and upload as file.

### Issue: Content looks wrong
**Solution:** Page may require JavaScript. Use browser "Save As" and upload HTML file.

## Future Enhancements

Possible improvements:
- Batch URL import (multiple URLs at once)
- Recursive crawling (fetch linked pages)
- JavaScript rendering support
- Sitemap import
- Scheduled re-fetching (auto-update)
- Authentication support (login-protected pages)

## API Usage (for developers)

### cURL Example

```bash
curl -X POST http://localhost:8000/api/admin/fetch-url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/docs",
    "bot_id": 1
  }'
```

### Python Example

```python
import requests

response = requests.post(
    "http://localhost:8000/api/admin/fetch-url",
    json={
        "url": "https://example.com/docs",
        "bot_id": 1
    }
)

print(response.json())
```

### JavaScript Example

```javascript
const response = await fetch('http://localhost:8000/api/admin/fetch-url', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://example.com/docs',
    bot_id: 1
  })
});

const data = await response.json();
console.log(data);
```

---

## Summary

The URL Fetch feature makes it easy to add web content to your knowledge base without manual downloads. Perfect for documentation, articles, and public web pages!

**Quick Start:**
1. Click "🌐 Fetch from URL"
2. Paste URL
3. Click "Fetch & Index"
4. Done!
