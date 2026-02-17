
import ReactDOM from 'react-dom/client';
import ChatWidget from './components/ChatWidget';
import { ChatWidgetConfig } from './types';
import './styles/index.css';



// Global interface for the widget API
declare global {
  interface Window {
    ChatbotWidget: {
      init: (config?: ChatWidgetConfig) => void;
      destroy: () => void;
      open: () => void;
      close: () => void;
      isOpen: () => boolean;
    };
  }
}

class ChatbotWidgetAPI {
  private root: ReactDOM.Root | null = null;
  private container: HTMLDivElement | null = null;

  init(config: ChatWidgetConfig = {}) {
    // Clean up existing widget
    this.destroy();

    // Create container
    this.container = document.createElement('div');
    this.container.id = 'chatbot-widget-container';
    this.container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 9999;
    `;
    
    // Allow pointer events only on the widget itself
    this.container.addEventListener('click', (e) => {
      if (e.target === this.container) {
        e.stopPropagation();
      }
    });

    document.body.appendChild(this.container);

    // Create React root and render widget
    this.root = ReactDOM.createRoot(this.container);
    this.root.render(
      <div style={{ pointerEvents: 'auto', position: 'relative', height: '100%' }}>
        <ChatWidget config={config} />
      </div>
    );

    console.log('🤖 MPS Support Chatbot Widget initialized');
  }

  destroy() {
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
    
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
      this.container = null;
    }
  }

  open() {
    // This would need to be implemented with a ref or state management
    console.log('Opening chatbot widget');
  }

  close() {
    // This would need to be implemented with a ref or state management
    console.log('Closing chatbot widget');
  }

  isOpen(): boolean {
    // This would need to be implemented with a ref or state management
    return false;
  }
}

// Create global API
const chatbotAPI = new ChatbotWidgetAPI();

// Expose API to window
window.ChatbotWidget = {
  init: (config?: ChatWidgetConfig) => chatbotAPI.init(config),
  destroy: () => chatbotAPI.destroy(),
  open: () => chatbotAPI.open(),
  close: () => chatbotAPI.close(),
  isOpen: () => chatbotAPI.isOpen()
};

// Auto-initialize if config is provided via data attributes
document.addEventListener('DOMContentLoaded', () => {
  const script = document.querySelector('script[data-chatbot-config]');
  if (script) {
    try {
      const config = JSON.parse(script.getAttribute('data-chatbot-config') || '{}');
      window.ChatbotWidget.init(config);
    } catch (error) {
      console.error('Failed to parse chatbot config:', error);
      window.ChatbotWidget.init();
    }
  }
});

// Export for module usage
export { ChatWidget };
export type { ChatWidgetConfig };
export default chatbotAPI;