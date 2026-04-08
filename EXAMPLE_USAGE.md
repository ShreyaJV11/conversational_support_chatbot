# Example Usage - Image Feature

## Scenario: Chrome Extension Installation Guide

### Step 1: Admin Uploads HTML File

**File: `chrome_extension_guide.html`**
```html
<h1>Chrome Extension Installation</h1>
<p>Follow these steps to install:</p>
<img src="step1.png" alt="Download">
<img src="step2.png" alt="Enable dev mode">
<img src="step3.png" alt="Load unpacked">
```

**Upload Result:**
- ✅ Text extracted
- ✅ 3 images copied to `uploads/1/`
- ✅ Chunks created with image references
- ✅ "Indexed ✅ 5 chunks"

### Step 2: User Asks Question

**User:** "How do I install the Chrome extension?"

### Step 3: Bot Response (What User Sees)

```
┌─────────────────────────────────────────┐
│ 🤖 Bot                                  │
├─────────────────────────────────────────┤
│ Download the extension, enable          │
│ Developer Mode, and load it.            │
│                                         │
│ [📷 Image: Download button]             │
│                                         │
│ Show Details ▼                          │
└─────────────────────────────────────────┘
```

**After clicking "Show Details":**
```
┌─────────────────────────────────────────┐
│ 🤖 Bot                                  │
├─────────────────────────────────────────┤
│ Download the extension, enable          │
│ Developer Mode, and load it.            │
│                                         │
│ [📷 Image: Download button]             │
│                                         │
│ Hide Details ▲                          │
│ ┌───────────────────────────────────┐   │
│ │ 1. Download extension files       │   │
│ │    [📷 Image: Download screen]    │   │
│ │                                   │   │
│ │ 2. Enable Developer Mode          │   │
│ │    [📷 Image: Dev mode toggle]    │   │
│ │                                   │   │
│ │ 3. Click "Load unpacked"          │   │
│ │    [📷 Image: Load button]        │   │
│ └───────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## What Happens Behind the Scenes

### Backend Processing:
```
1. Chunk retrieved: "Download extension... [IMAGE_REF:http://...]"
2. LLM generates: "SHORT_ANSWER: ... [IMAGE_REF:...]"
3. Response streamed to frontend
```

### Frontend Rendering:
```
1. Regex finds: [IMAGE_REF:http://localhost:8000/uploads/1/step1.png]
2. Extracts URL: http://localhost:8000/uploads/1/step1.png
3. Removes marker from text
4. Renders: <img src="..." />
```

## More Examples

### Example 2: Product Dashboard
**Question:** "How do I access the analytics dashboard?"
**Response:** Text explanation + screenshot of dashboard

### Example 3: Error Troubleshooting  
**Question:** "What does error code 500 mean?"
**Response:** Error explanation + screenshot of error message

### Example 4: API Documentation
**Question:** "Show me the API endpoint structure"
**Response:** Endpoint details + diagram of API architecture

---

**Try it yourself!** Upload any HTML file with images and ask related questions.
