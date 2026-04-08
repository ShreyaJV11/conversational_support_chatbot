# Testing Image Feature - Quick Guide

## Test Scenario 1: Upload HTML with Images

### Step 1: Create a test HTML file
Create `test_tutorial.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Chrome Extension Setup</title>
</head>
<body>
    <h1>How to Install Chrome Extension</h1>
    
    <h2>Step 1: Download the Extension</h2>
    <p>First, download the extension files from our repository.</p>
    <img src="screenshot1.png" alt="Download button">
    
    <h2>Step 2: Enable Developer Mode</h2>
    <p>Go to chrome://extensions and toggle Developer Mode.</p>
    <img src="screenshot2.png" alt="Developer mode toggle">
    
    <h2>Step 3: Load Unpacked</h2>
    <p>Click "Load unpacked" and select the extension folder.</p>
    <img src="screenshot3.png" alt="Load unpacked button">
</body>
</html>
```

### Step 2: Add corresponding images
Place `screenshot1.png`, `screenshot2.png`, `screenshot3.png` in the same directory as the HTML file.

### Step 3: Upload via Admin Panel
1. Go to `http://localhost:5173/kb-upload/1` (or your admin URL)
2. Select `test_tutorial.html`
3. Click Upload

**Expected Result:**
- Backend extracts text from HTML
- Copies images to `backend/uploads/1/`
- Creates chunks with `[IMAGE_REF:...]` markers
- Console shows: "Indexed ✅ X chunks"

### Step 4: Test in Chat
1. Open chat widget
2. Login with name and email
3. Ask: "How do I install the Chrome extension?"

**Expected Response:**
```
SHORT_ANSWER:
Download the extension, enable Developer Mode in chrome://extensions, 
and click "Load unpacked" to select the folder.
[Image appears here showing download button]

DETAILED_ANSWER: (click "Show Details")
1. Download the extension files from our repository
   [Image: Download button]
2. Go to chrome://extensions and toggle Developer Mode
   [Image: Developer mode toggle]
3. Click "Load unpacked" and select the extension folder
   [Image: Load unpacked button]
```

---

## Test Scenario 2: Upload Image File Directly

### Step 1: Create/Find an Image
Use any PNG or JPG file (e.g., a diagram, flowchart, or screenshot)

### Step 2: Upload via Admin Panel
1. Go to KB Upload
2. Select the image file (e.g., `architecture_diagram.png`)
3. Upload

**Expected Result:**
- OCR extracts any text from the image
- Image is stored in `uploads/{bot_id}/`
- Chunk created with image reference

### Step 3: Test in Chat
Ask a question related to the image content.

**Expected Response:**
The bot will show the image along with any extracted text.

---

## Test Scenario 3: Upload Text File with Image References

### Create test file: `product_guide.txt`
```
Product Setup Guide

To configure the dashboard, follow these steps:

1. Navigate to Settings > Configuration
2. Enter your API key
3. Click Save

[IMAGE_REF:http://localhost:8000/uploads/1/dashboard_screenshot.png]

For advanced settings, refer to the admin panel.
```

**Note:** This won't work automatically - images must be uploaded separately. 
The system is designed to extract images from HTML/PDF/Image files, not from text references.

---

## Verification Checklist

### Backend Verification:
- [ ] Images copied to `backend/uploads/{bot_id}/`
- [ ] Accessible at `http://localhost:8000/uploads/{bot_id}/{filename}`
- [ ] Database chunks contain `[IMAGE_REF:...]` markers
- [ ] No errors in backend console during upload

### Frontend Verification:
- [ ] Images render in chat messages
- [ ] Images appear in both SHORT_ANSWER and DETAILED_ANSWER
- [ ] Click on image opens in new tab
- [ ] Failed images are hidden (not showing broken image icon)
- [ ] Text flows naturally without `[IMAGE_REF:...]` markers visible

### SQL Query to Check Chunks:
```sql
SELECT chunk_text 
FROM kb_chunks 
WHERE bot_id = 1 
AND chunk_text LIKE '%IMAGE_REF%'
LIMIT 5;
```

This will show you chunks that contain image references.

---

## Common Issues & Solutions

### Issue: Images not extracted from HTML
**Solution:** Ensure images are in the same directory as HTML file or use absolute URLs

### Issue: OCR returns empty text
**Solution:** 
- Install Tesseract: `pip install pytesseract`
- Install Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki
- Verify: `tesseract --version`

### Issue: Images show 404 in browser
**Solution:**
- Check `backend/uploads/{bot_id}/` directory exists
- Verify FastAPI static mount: `app.mount("/uploads", StaticFiles(directory="uploads"))`
- Check CORS settings in `main.py`

### Issue: Images not in LLM response
**Solution:**
- Check if chunks with images are being retrieved (add logging in `retrieval_service.py`)
- Verify LLM system prompt includes image preservation rules
- Check if `build_chunk_text_with_images()` is being called during ingestion

---

## Advanced Testing

### Test with Multiple Images
Upload an HTML file with 5+ images and verify all are displayed correctly.

### Test with Large Images
Upload a high-resolution image and verify it displays with proper sizing.

### Test Image Formats
Try different formats: PNG, JPG, JPEG, GIF (if supported)

### Test Broken Image URLs
Manually edit a chunk in the database to have an invalid URL and verify the frontend hides it gracefully.

---

## Production Testing Checklist

Before deploying to production:

- [ ] Update `BASE_UPLOAD_URL` in backend `.env`
- [ ] Test with production domain URLs
- [ ] Verify HTTPS works for image serving
- [ ] Test with CDN if using one
- [ ] Check image loading performance
- [ ] Verify mobile responsiveness of images
- [ ] Test with slow network connections
- [ ] Ensure images are optimized (compressed)

---

## Need Help?

If images aren't working:
1. Check backend logs during upload
2. Verify file permissions on `uploads/` directory
3. Test image URL directly in browser
4. Check browser console for errors
5. Review `IMAGE_FEATURE_GUIDE.md` for detailed troubleshooting
