# Image Feature - Quick Reference Card

## 🎯 What's New
Your chatbot now displays images from uploaded documents in chat responses!

## 📤 Upload Files with Images

### Supported Formats:
- **HTML/HTM** - Extracts `<img>` tags
- **PNG/JPG/JPEG** - OCR text extraction
- **PDF/PPTX** - May extract embedded images

### How to Upload:
1. Go to Admin Panel → KB Upload
2. Select file (max 5MB)
3. Click Upload
4. Wait for "Indexed ✅" confirmation

### Where Images Are Stored:
```
backend/uploads/{bot_id}/filename.png
```

### Access URL:
```
http://localhost:8000/uploads/{bot_id}/filename.png
```

## 💬 Chat Display

### User Experience:
1. User asks question
2. Bot responds with text + images
3. Images appear below text
4. Click image to open full size

### Example Response:
```
SHORT_ANSWER:
To install the extension, enable Developer Mode 
and click Load Unpacked.

[Image showing the steps appears here]

Show Details ▼
  DETAILED_ANSWER:
  1. Go to chrome://extensions
  2. Toggle Developer Mode
     [Image: Developer mode toggle]
  3. Click "Load unpacked"
     [Image: Load unpacked button]
```

## 🔧 Technical Details

### Image Marker Format:
```
[IMAGE_REF:http://localhost:8000/uploads/1/image.png]
```

### Processing Flow:
```
Upload → Extract → Store → Embed → Retrieve → Display
```

### Key Files:
- **Backend:** `ingestion_service.py`, `llm_service.py`
- **Frontend:** `MessageBubble.tsx`
- **Storage:** `backend/uploads/{bot_id}/`

## ✅ Verification

### Check Upload Success:
```bash
# Backend logs should show:
"Indexed ✅ X chunks"

# Check file exists:
ls backend/uploads/1/
```

### Check Database:
```sql
SELECT chunk_text 
FROM kb_chunks 
WHERE chunk_text LIKE '%IMAGE_REF%' 
LIMIT 1;
```

### Check Frontend:
- Open chat widget
- Ask related question
- Verify images display
- No `[IMAGE_REF:...]` text visible

## 🐛 Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| Images not uploading | Check file format, size (<5MB), backend logs |
| Images not showing | Check URL accessibility, CORS, browser console |
| OCR not working | Install Tesseract: `brew install tesseract` |
| Images in wrong place | Check chunk retrieval, LLM prompt |

## 🚀 Production Setup

### Required Changes:
1. Update `.env`:
   ```env
   BASE_UPLOAD_URL=https://yourdomain.com
   ```

2. Configure CORS in `main.py`:
   ```python
   ALLOWED_ORIGINS = ["https://yourdomain.com"]
   ```

3. Test image serving over HTTPS

## 📚 Full Documentation

- **Complete Guide:** `IMAGE_FEATURE_GUIDE.md`
- **Testing Guide:** `TESTING_IMAGES.md`
- **Implementation Summary:** `IMPLEMENTATION_SUMMARY.md`

## 🎉 Ready to Use!

Your image feature is complete. Upload a document with images and start testing!

---

**Need Help?** Check the troubleshooting sections in the full guides.
