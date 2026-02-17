# Enterprise Support Chatbot Widget

A floating chat widget for enterprise websites that provides deterministic, retrieval-based customer support with automatic escalation to Salesforce.

## Features

- **Floating Button**: Appears in bottom-right corner with pulse animation
- **Chat Panel**: Anchored to bottom-right, doesn't occupy full screen
- **Non-conversational**: Each question treated independently
- **Static Responses**: Pre-defined messages, no AI generation
- **Salesforce Integration**: Automatic escalation for unhandled queries
- **Professional UI**: Matches corporate design standards
- **Mobile Responsive**: Works on all device sizes
- **Accessibility**: Full keyboard navigation and screen reader support

## Quick Start

### 1. Include the Widget Script

```html
<!-- Include the widget script -->
<script src="https://your-cdn.com/chatbot-widget.umd.js"></script>

<!-- Initialize the widget -->
<script>
  window.ChatbotWidget.init({
    apiBaseUrl: 'https://your-api.com',
    userName: 'John Doe',
    initialMessage: true
  });
</script>
```

### 2. Auto-initialization with Data Attributes

```html
<script 
  src="https://your-cdn.com/chatbot-widget.umd.js"
  data-chatbot-config='{"apiBaseUrl": "https://your-api.com", "userName": "John Doe"}'
></script>
```

## Configuration Options

```typescript
interface ChatWidgetConfig {
  // API Configuration
  apiBaseUrl?: string;          // Default: 'http://localhost:3000'
  
  // User Configuration
  userName?: string;            // User's name for personalization
  sessionId?: string;           // Custom session ID
  
  // UI Configuration
  theme?: {
    primaryColor?: string;      // Primary color for buttons and accents
    backgroundColor?: string;   // Background color for chat panel
    textColor?: string;         // Text color
    borderRadius?: string;      // Border radius for elements
  };
  
  // Position Configuration
  position?: {
    bottom?: string;            // Default: '20px'
    right?: string;             // Default: '20px'
  };
  
  // Behavior Configuration
  initialMessage?: boolean;     // Show initial greeting (default: true)
  maxMessages?: number;         // Max messages to keep in memory (default: 50)
  typingDelay?: number;         // Typing indicator delay in ms (default: 1000)
}
```

## API Methods

```javascript
// Initialize the widget
window.ChatbotWidget.init(config);

// Destroy the widget
window.ChatbotWidget.destroy();

// Open the chat panel
window.ChatbotWidget.open();

// Close the chat panel
window.ChatbotWidget.close();

// Check if chat is open
const isOpen = window.ChatbotWidget.isOpen();
```

## Integration Examples

### Basic Integration

```html
<!DOCTYPE html>
<html>
<head>
  <title>My Website</title>
</head>
<body>
  <!-- Your existing website content -->
  <div class="content">
    <h1>Welcome to My Website</h1>
    <p>Your existing content here...</p>
  </div>

  <!-- Chatbot Widget -->
  <script src="https://your-cdn.com/chatbot-widget.umd.js"></script>
  <script>
    window.ChatbotWidget.init({
      apiBaseUrl: 'https://your-api.com',
      userName: 'Visitor'
    });
  </script>
</body>
</html>
```

### Advanced Integration with Custom Theme

```html
<script>
  window.ChatbotWidget.init({
    apiBaseUrl: 'https://your-api.com',
    userName: 'John Doe',
    theme: {
      primaryColor: '#2563eb',
      backgroundColor: '#ffffff',
      textColor: '#374151',
      borderRadius: '12px'
    },
    position: {
      bottom: '30px',
      right: '30px'
    },
    maxMessages: 100,
    typingDelay: 800
  });
</script>
```

### React Integration

```jsx
import { useEffect } from 'react';

function App() {
  useEffect(() => {
    // Load the widget script
    const script = document.createElement('script');
    script.src = 'https://your-cdn.com/chatbot-widget.umd.js';
    script.onload = () => {
      window.ChatbotWidget.init({
        apiBaseUrl: 'https://your-api.com',
        userName: 'React User'
      });
    };
    document.body.appendChild(script);

    // Cleanup
    return () => {
      window.ChatbotWidget?.destroy();
      document.body.removeChild(script);
    };
  }, []);

  return (
    <div className="App">
      {/* Your React app content */}
    </div>
  );
}
```

### WordPress Integration

```php
// Add to your theme's functions.php
function add_chatbot_widget() {
    ?>
    <script src="https://your-cdn.com/chatbot-widget.umd.js"></script>
    <script>
      window.ChatbotWidget.init({
        apiBaseUrl: 'https://your-api.com',
        userName: '<?php echo wp_get_current_user()->display_name; ?>'
      });
    </script>
    <?php
}
add_action('wp_footer', 'add_chatbot_widget');
```

## Styling and Customization

The widget is designed to not interfere with your existing website styles. It uses:

- **Isolated CSS**: All styles are scoped to the widget
- **CSS Reset**: Prevents inheritance from parent page
- **Z-index**: High z-index (9999) to appear above other content
- **Responsive Design**: Adapts to different screen sizes

### Custom CSS

You can override widget styles if needed:

```css
/* Override widget button color */
.chat-widget button {
  background-color: #your-color !important;
}

/* Override chat panel width */
.chat-widget .w-80 {
  width: 350px !important;
}
```

## Browser Support

- Chrome 60+
- Firefox 60+
- Safari 12+
- Edge 79+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance

- **Bundle Size**: ~50KB gzipped
- **Load Time**: <100ms on modern browsers
- **Memory Usage**: <5MB typical usage
- **Network**: Minimal API calls, efficient caching

## Security

- **XSS Protection**: All user input sanitized
- **CORS**: Proper CORS headers required
- **Rate Limiting**: Built-in rate limiting
- **No Data Storage**: No local storage of sensitive data

## Troubleshooting

### Widget Not Appearing

1. Check console for JavaScript errors
2. Verify API endpoint is accessible
3. Check CORS configuration
4. Ensure script is loaded after DOM

### API Connection Issues

1. Verify `apiBaseUrl` is correct
2. Check network connectivity
3. Verify API is running and healthy
4. Check browser developer tools for network errors

### Styling Issues

1. Check for CSS conflicts
2. Verify z-index is sufficient
3. Check responsive design on mobile
4. Use browser developer tools to inspect elements

## Development

### Local Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### Testing

```bash
# Run tests
npm test

# Run linting
npm run lint
```

## Support

For technical support or questions:

- **Documentation**: [API Documentation](../API_DOCUMENTATION.md)
- **Issues**: Create an issue in the repository
- **Email**: support@your-company.com

## License

MIT License - see LICENSE file for details.