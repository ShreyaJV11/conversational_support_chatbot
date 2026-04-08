# Image Support in Chatbot - Implementation Guide

## Overview
Your chatbot now supports uploading documents with images and displaying those images in chat responses when relevant to user questions.

## How It Works

### 1. Admin Upload (Backend)
When an admin uploads a file through the KB Upload interface:

**Supported Formats:**
- `.txt`, `.md`, `.pdf`, `.docx`, `.html`, `.htm`, `.json`, `.csv`, `.png`, `.jpg`, `.jpeg`

**Image Processing:**
- **HTML files**: Images are extracted from `<img>` tags, copied to `uploads/{bot_id}/`, and referenced
- **Image files**: OCR is performed using Tesseract to extract text, image is stored
- **PDF/PPTX**: Embedded images may be extracted (if supported by UnstructuredLoader)

**Storage:**
- Images are stored in: `backend/uploads/{bot_id}/`
- Accessible via: `http://localhost:8000/uploads/{bot_id}/{filename}`
- Image references are embedded in chunks as: `[IMAGE_REF:https://...]`

### 2. Retrieval & Response (LLM)
When a user asks a question:

1. **Vector search** retrieves relevant chunks from the knowledge base
2. Chunks containing `[IMAGE_REF:url]` markers are passed to the LLM
3. **LLM is instructed** to preserve these markers in its response
4. Response format:
   ```
   SHORT_ANSWER:
   Brief answer text
   [IMAGE_REF:http://localhost:8000/uploads/1/image.jpg]

   DETAILED_ANSWER:
   Detailed explanation
   [IMAGE_REF:http://localhost:8000/uploads/1/diagram.png]
   ```

### 3. Frontend Display
The chat widget automatically:

1. **Detects** `[IMAGE_REF:url]` markers in bot responses
2. **Extracts** image URLs from the text
3. **Removes** the markers from displayed text
4. **Renders** images below the text content

**Features:**
- Images appear in both SHORT_ANSWER and DETAILED_ANSWER sections
- Click on images to open in new tab
- Images that fail to load are hidden automatically
- Responsive sizing with rounded borders

## Usage Example

### Admin Side:
1. Go to KB Upload page
2. Select a file (e.g., `tutorial.html` with screenshots)
3. Upload → System extracts text and images
4. Images are stored and linked to the document chunks

### User Side:
1. User asks: "How do I configure the Chrome extension?"
2. System retrieves relevant chunks (including image references)
3. Bot responds with text + images showing the configuration steps
4. User sees formatted answer with embedded screenshots

## Configuration

### Backend Environment Variables
```env
BASE_UPLOAD_URL=http://localhost:8000  # Change in production
```

### Frontend Configuration
Images are automatically rendered - no configuration needed.

### File Size Limits
- Maximum file size: 5MB (configured in `kb_upload.py`)
- Adjust if needed for larger documents

## Troubleshooting

### Images Not Showing
1. **Check backend logs** - Are images being extracted during ingestion?
2. **Verify file serving** - Can you access `http://localhost:8000/uploads/{bot_id}/{filename}` directly?
3. **Check CORS** - Ensure frontend origin is in `ALLOWED_ORIGINS` (main.py)
4. **Browser console** - Look for 404 or CORS errors

### Images Not in Responses
1. **Check LLM output** - Are `[IMAGE_REF:...]` markers in the raw response?
2. **Check retrieval** - Are chunks with images being retrieved? (Check logs)
3. **Check prompt** - LLM system prompt instructs preservation of image markers

### OCR Not Working (for image files)
1. **Install Tesseract**: 
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Linux: `sudo apt-get install tesseract-ocr`
   - Mac: `brew install tesseract`
2. **Verify installation**: `tesseract --version`

## Technical Details

### Image Reference Format
```
[IMAGE_REF:http://localhost:8000/uploads/1/html_img_a3f2e1_screenshot.png]
```

### Frontend Regex Pattern
```typescript
const imageRegex = /\[IMAGE_REF:(https?:\/\/[^\]]+)\]/g;
```

### Database Storage
Images are NOT stored in the database. Only:
- Image URLs are embedded in `chunk_text` field
- Original files are in filesystem: `uploads/{bot_id}/`

## Production Deployment

### Important Changes for Production:

1. **Update BASE_UPLOAD_URL** in backend `.env`:
   ```env
   BASE_UPLOAD_URL=https://yourdomain.com
   ```

2. **Configure static file serving** (if using reverse proxy):
   - Nginx: Serve `/uploads` directory directly
   - Or ensure FastAPI static mount is accessible

3. **Storage considerations**:
   - Consider cloud storage (S3, Azure Blob) for scalability
   - Update `get_public_url()` function in `ingestion_service.py`

4. **Security**:
   - Validate image file types strictly
   - Scan uploaded files for malware
   - Set appropriate file permissions on uploads directory

## Files Modified

### Backend:
- `backend/app/services/ingestion_service.py` - Image extraction and storage
- `backend/app/services/llm_service.py` - LLM prompt with image preservation rules
- `backend/app/main.py` - Static file serving for `/uploads`
- `backend/app/routes/kb_upload.py` - File upload handling

### Frontend:
- `frontend/chat/src/components/MessageBubble.tsx` - Image rendering in chat messages

## Next Steps

Your image feature is now complete! To test:

1. Upload an HTML file with images or a PNG/JPG file
2. Ask a question related to that content
3. Verify images appear in the bot's response

For questions or issues, check the troubleshooting section above.
