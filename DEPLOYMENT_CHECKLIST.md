# Image Feature - Deployment Checklist

## ✅ Pre-Deployment Verification

### Backend Checks:
- [ ] `backend/uploads/` directory exists
- [ ] Static file serving configured in `main.py`
- [ ] `BASE_UPLOAD_URL` set in `.env` or defaults to localhost
- [ ] Image extraction working (test with HTML file)
- [ ] OCR working (test with PNG file)
- [ ] Database chunks contain `[IMAGE_REF:...]` markers
- [ ] LLM system prompt includes image preservation rules

### Frontend Checks:
- [ ] `MessageBubble.tsx` updated with image rendering
- [ ] No TypeScript errors
- [ ] Images display in chat widget
- [ ] Click to open image works
- [ ] Broken images hidden gracefully
- [ ] Mobile responsive

### Integration Checks:
- [ ] Upload → Storage → Display flow works end-to-end
- [ ] Images appear in SHORT_ANSWER
- [ ] Images appear in DETAILED_ANSWER (Show Details)
- [ ] Multiple images per response work
- [ ] CORS configured correctly

## 🚀 Production Deployment Steps

### 1. Update Environment Variables

**Backend `.env`:**
```env
BASE_UPLOAD_URL=https://api.yourdomain.com
```

### 2. Update CORS Settings

**`backend/app/main.py`:**
```python
ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://www.yourdomain.com",
    "https://chat.yourdomain.com"
]
```

### 3. Configure Image Storage

**Option A: Local Storage (Simple)**
- Ensure `uploads/` directory has proper permissions
- Configure backup for `uploads/` directory

**Option B: Cloud Storage (Recommended)**
- Set up S3/Azure Blob/GCS bucket
- Update `get_public_url()` in `ingestion_service.py`
- Configure CDN for faster delivery

### 4. Optimize Images

**Add image optimization:**
```python
# In ingestion_service.py
from PIL import Image

def optimize_image(image_path, max_width=1200):
    img = Image.open(image_path)
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        img.save(image_path, optimize=True, quality=85)
```

### 5. Security Hardening

- [ ] Validate file types strictly
- [ ] Scan uploaded files for malware
- [ ] Set file size limits (currently 5MB)
- [ ] Implement rate limiting on uploads
- [ ] Use secure file names (already using UUID)
- [ ] Set proper file permissions (read-only for web server)

### 6. Performance Optimization

- [ ] Enable image compression
- [ ] Configure CDN for image delivery
- [ ] Add image lazy loading in frontend
- [ ] Implement image caching headers
- [ ] Monitor storage usage

### 7. Monitoring & Logging

**Add monitoring for:**
- Upload success/failure rates
- Image serving errors (404s)
- Storage usage
- OCR processing time
- Image load times

**Log important events:**
```python
logger.info(f"Image extracted: {filename} → {public_url}")
logger.error(f"Image extraction failed: {filename}")
```

## 🧪 Production Testing

### Test Scenarios:
1. **Upload HTML with images** → Verify extraction
2. **Upload standalone image** → Verify OCR
3. **Ask question** → Verify images in response
4. **Test on mobile** → Verify responsive display
5. **Test slow connection** → Verify loading behavior
6. **Test broken image URL** → Verify graceful handling
7. **Test multiple images** → Verify all display
8. **Test HTTPS** → Verify secure image serving

### Load Testing:
- [ ] Upload 100+ files with images
- [ ] Concurrent uploads (10+ users)
- [ ] Image serving under load
- [ ] Database performance with image refs

## 📊 Monitoring Metrics

### Track These Metrics:
- **Upload metrics:**
  - Files uploaded per day
  - Images extracted per upload
  - Upload failures
  
- **Storage metrics:**
  - Total storage used
  - Average file size
  - Storage growth rate
  
- **Performance metrics:**
  - Image load time
  - OCR processing time
  - Upload processing time
  
- **User metrics:**
  - Responses with images
  - Image click-through rate
  - User satisfaction

## 🔄 Rollback Plan

If issues occur:

1. **Frontend issues:**
   ```bash
   git revert <commit-hash>
   npm run build
   ```

2. **Backend issues:**
   - Revert `ingestion_service.py` changes
   - Images will still be stored but not displayed

3. **Database issues:**
   - Image refs are in `chunk_text` field
   - No schema changes needed for rollback

## 📝 Post-Deployment

### Immediate Actions:
- [ ] Monitor error logs for 24 hours
- [ ] Test with real user uploads
- [ ] Verify image serving performance
- [ ] Check storage usage

### Week 1:
- [ ] Gather user feedback
- [ ] Monitor storage growth
- [ ] Optimize based on usage patterns
- [ ] Document any issues

### Ongoing:
- [ ] Regular storage cleanup
- [ ] Performance monitoring
- [ ] User satisfaction surveys
- [ ] Feature improvements

## 🆘 Emergency Contacts

**If critical issues occur:**
1. Check backend logs: `tail -f backend/logs/app.log`
2. Check frontend console: Browser DevTools
3. Verify image serving: `curl http://domain/uploads/1/test.png`
4. Check database: SQL queries in `TESTING_IMAGES.md`

## ✨ Success Criteria

Deployment is successful when:
- [ ] Users can upload files with images
- [ ] Images display in chat responses
- [ ] No errors in logs
- [ ] Performance is acceptable (<2s image load)
- [ ] Mobile experience is good
- [ ] User feedback is positive

---

**Ready to Deploy?** Complete all checks above before proceeding.
