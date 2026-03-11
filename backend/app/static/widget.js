(function () {
 
  let script = document.currentScript;

  
  if (!script) {
    const allScripts = document.getElementsByTagName('script');
    for (let i = 0; i < allScripts.length; i++) {
      if (allScripts[i].getAttribute("data-bot-id")) {
        script = allScripts[i];
        break;
      }
    }
  }

  if (!script) {
    console.error("Chatbot widget: Could not locate our script tag on the page.");
    return;
  }

  
  const botId = script.getAttribute("data-bot-id");
  const appUrl = script.getAttribute("data-app-url") || "http://localhost:5173";

  console.log(" [Widget.js] Extracted Bot ID:", botId);

  if (!botId) {
    console.error(" Chatbot widget: data-bot-id attribute is missing from script tag.");
    return;
  }

 
  const iframe = document.createElement("iframe");


  iframe.src = `${appUrl}/widget?bot_id=${encodeURIComponent(botId)}`;
  console.log(" [Widget.js] Loading Iframe from:", iframe.src);

  iframe.style.position = "fixed";
  iframe.style.bottom = "20px";
  iframe.style.right = "20px";
  iframe.style.width = "80px";   // Small width initially
  iframe.style.height = "80px";  // Small height initially
  iframe.style.border = "none";
  iframe.style.zIndex = "999999";
  iframe.style.transition = "all 0.3s ease-in-out"; // Smooth resizing animation
  iframe.style.colorScheme = "normal"; // Prevent host site's dark mode from breaking your UI

  document.body.appendChild(iframe);


  window.addEventListener("message", (event) => {
    if (event.data.type === "CHAT_OPENED") {
      iframe.style.width = "400px";  
      iframe.style.height = "600px";
      iframe.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1)";
      iframe.style.borderRadius = "12px";
    } 
    else if (event.data.type === "CHAT_CLOSED" || event.data.type === "CHAT_MINIMIZED") {
      iframe.style.width = "80px";
      iframe.style.height = "80px";
      iframe.style.boxShadow = "none";
    }
    
    else if (event.data.type === "RESIZE_WIDGET") {
      iframe.style.width = (event.data.width + 20) + "px"; 
      iframe.style.height = (event.data.height + 20) + "px";
    }
  });

})();