# Supported File Types - Complete Reference

## ✅ Currently Supported File Types

Your chatbot now supports the following file types for knowledge base uploads:

### 📝 Text Formats
| Extension | Description | Image Support | Notes |
|-----------|-------------|---------------|-------|
| `.txt` | Plain text | ❌ | Simple text files |
| `.md` | Markdown | ❌ | Formatted text with markdown |
| `.json` | JSON data | ❌ | Structured data files |
| `.yaml` | YAML config | ❌ | Configuration files |
| `.yml` | YAML config | ❌ | Alternative YAML extension |

### 📄 Document Formats
| Extension | Description | Image Support | Notes |
|-----------|-------------|---------------|-------|
| `.pdf` | PDF documents | ✅ | May extract embedded images |
| `.docx` | Word documents | ❌ | Microsoft Word format |
| `.pptx` | PowerPoint | ✅ | May extract embedded images |

### 📊 Spreadsheet Formats
| Extension | Description | Image Support | Notes |
|-----------|-------------|---------------|-------|
| `.xlsx` | Excel spreadsheet | ❌ | Modern Excel format |
| `.xls` | Excel spreadsheet | ❌ | Legacy Excel format |
| `.csv` | CSV data | ❌ | Comma-separated values |

### 🌐 Web Formats
| Extension | Description | Image Support | Notes |
|-----------|-------------|---------------|-------|
| `.html` | HTML page | ✅ | Extracts `<img>` tags |
| `.htm` | HTML page | ✅ | Alternative HTML extension |

### 🖼️ Image Formats (with OCR)
| Extension | Description | Image Support | Notes |
|-----------|-------------|---------------|-------|
| `.png` | PNG image | ✅ | OCR text extraction |
| `.jpg` | JPEG image | ✅ | OCR text extraction |
| `.jpeg` | JPEG image | ✅ | Alternative JPEG extension |

## 📏 File Limitations

### Size Limits:
- **Maximum file size:** 5 MB
- Configurable in `backend/app/routes/kb_upload.py`

### Processing:
- Text extraction for all formats
- Image extraction for HTML, PDF, PPTX, and image files
- OCR for standalone image files (requires Tesseract)

## 🔧 How Each Format is Processed

### Text Files (.txt, .md, .json, .yaml, .yml)
```
Upload → Read text → Split into chunks → Embed → Store
```
- Simple text extraction
- No special processing
- Fast ingestion

### PDF Files (.pdf)
```
Upload → Extract text + images → Split → Embed → Store
```
- Uses UnstructuredPDFLoader (high-res strategy)
- Falls back to PyPDFLoader if needed
- May extract embedded images
- Preserves document structure

### Word Documents (.docx)
```
Upload → Extract text → Split → Embed → Store
```
- Uses Docx2txtLoader
- Text-only extraction
- No image support currently

### PowerPoint (.pptx)
```
Upload → Extract text + images → Split → Embed → Store
```
- Uses UnstructuredPowerPointLoader
- May extract embedded images
- Processes all slides

### Excel Files (.xlsx, .xls)
```
Upload → Extract data → Split → Embed → Store
```
- Uses UnstructuredExcelLoader
- Converts tables to text
- Preserves data structure

### CSV Files (.csv)
```
Upload → Parse data → Split → Embed → Store
```
- Uses CSVLoader
- Converts rows to text
- Good for structured data

### HTML Files (.html, .htm)
```
Upload → Extract text + images → Copy images → Split → Embed → Store
```
- Parses HTML with BeautifulSoup
- Extracts `<img>` tags
- Copies images to uploads directory
- Generates public URLs
- Clean text extraction (no HTML tags)

### Image Files (.png, .jpg, .jpeg)
```
Upload → OCR text extraction → Copy image → Embed → Store
```
- Uses Tesseract OCR
- Extracts readable text from images
- Stores original image
- Generates public URL
- Fallback text if no text detected

## 🚫 Not Supported (Yet)

### Common Formats Not Supported:
- `.doc` (old Word format) - Use .docx instead
- `.odt` (OpenDocument) - Convert to .docx
- `.rtf` (Rich Text Format) - Convert to .txt or .docx
- `.epub` (eBooks) - Convert to .pdf
- `.zip` / `.rar` (Archives) - Extract and upload individually
- `.gif` / `.bmp` / `.svg` (Other images) - Convert to .png or .jpg
- `.mp4` / `.avi` (Videos) - Not supported
- `.mp3` / `.wav` (Audio) - Not supported

## 🔄 Adding New File Types

To add support for a new file type:

### 1. Install Required Loader
```bash
pip install langchain-community
# Or specific loader package
```

### 2. Update Ingestion Service
**File:** `backend/app/services/ingestion_service.py`

```python
def get_loader(file_path: str):
    _, ext = os.path.splitext(file_path.lower())
    
    # Add your new format
    elif ext == ".epub":
        return UnstructuredEPubLoader(file_path)
```

### 3. Update Allowed Extensions
**File:** `backend/app/routes/kb_upload.py`

```python
ALLOWED_EXTENSIONS = {
    # ... existing extensions ...
    ".epub"  # Add new extension
}
```

### 4. Update Frontend
**File:** `frontend/admin/src/pages/KBUpload.tsx`

```typescript
const ALLOWED_EXTENSIONS = [
  // ... existing extensions ...
  ".epub"  // Add new extension
];
```

### 5. Test
- Upload test file
- Verify text extraction
- Check chunk creation
- Test in chat

## 📊 Format Comparison

### Best for Text Content:
1. `.txt` - Fastest, simplest
2. `.md` - Good for formatted docs
3. `.pdf` - Best for official documents

### Best for Images:
1. `.html` - Best image extraction
2. `.pdf` - Good for embedded images
3. `.png/.jpg` - Direct image upload with OCR

### Best for Data:
1. `.csv` - Structured data
2. `.json` - API responses, configs
3. `.xlsx` - Complex spreadsheets

### Best for Documentation:
1. `.html` - Web docs with images
2. `.pdf` - Official documentation
3. `.md` - Developer documentation

## 🎯 Recommendations

### For Admins:
- **Use HTML** for content with images
- **Use PDF** for official documents
- **Use TXT/MD** for simple text
- **Use CSV** for data tables
- **Convert unsupported formats** before upload

### For Best Results:
- Keep files under 5MB
- Use clear, readable text
- Include relevant images in HTML
- Optimize images before upload
- Use descriptive filenames

## 🔍 Verification

### Check Supported Formats:
```bash
# Backend
grep "ALLOWED_EXTENSIONS" backend/app/routes/kb_upload.py

# Frontend
grep "ALLOWED_EXTENSIONS" frontend/admin/src/pages/KBUpload.tsx
```

### Test Upload:
1. Go to Admin Panel → KB Upload
2. Try uploading each format
3. Verify "Indexed ✅" message
4. Check chunks in database

## 📝 Format-Specific Notes

### PDF Files:
- Requires `unstructured` package
- May need `poppler-utils` for images
- Large PDFs may take longer to process

### Image Files:
- Requires Tesseract OCR installed
- Works best with clear, high-contrast text
- Handwriting may not be recognized

### Excel Files:
- Converts tables to text format
- May lose formatting
- Large spreadsheets split into chunks

### HTML Files:
- Best format for images
- Preserves structure
- Cleans out HTML tags

## 🆘 Troubleshooting

### "Unsupported file type" Error:
- Check file extension is in ALLOWED_EXTENSIONS
- Verify file is not corrupted
- Try converting to supported format

### "File too large" Error:
- Compress file or split into smaller parts
- Current limit: 5MB
- Increase limit in kb_upload.py if needed

### OCR Not Working:
- Install Tesseract: `brew install tesseract` (Mac)
- Windows: Download from GitHub
- Linux: `sudo apt-get install tesseract-ocr`

### PDF Processing Fails:
- Install dependencies: `pip install unstructured[pdf]`
- May need: `apt-get install poppler-utils`

---

**Summary:** Your chatbot now supports 18 different file formats including text, documents, spreadsheets, web pages, and images with OCR!
