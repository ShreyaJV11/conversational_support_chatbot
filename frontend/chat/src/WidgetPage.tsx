import { useMemo } from 'react';
import ChatWidget from "./components/ChatWidget";

export default function WidgetPage() {
  const botId = useMemo(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const idParam = urlParams.get('bot_id');
    const parsedId = idParam ? Number(idParam) : undefined;

    console.log("🎯 Bot ID locked in:", parsedId);
    return parsedId;
  }, []);

  if (!botId) {
    console.warn("⚠️ WidgetPage: No bot_id found in URL.");
    return null;
  }

  return (
    
  <div
    style={{
      width: "100vw",
      height: "100vh",
      backgroundColor: "transparent",
      overflow: "hidden",
      display: "flex",
      justifyContent: "flex-end", 
      alignItems: "flex-end",    
      padding: "20px",           
      boxSizing: "border-box"
    }}
  >
    <ChatWidget config={{ botId }} />
  </div>
);
   
}