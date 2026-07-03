// Extract interactive elements and generate selectors
function getPageContext() {
  const elements = document.querySelectorAll('input, button, a, textarea');
  const context = [];
  let count = 0;

  for (const el of elements) {
    if (count >= 50) break;

    // Skip hidden elements
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || el.type === 'hidden') continue;

    // Generate unique selector
    let selector = '';
    if (el.id) {
      selector = `#${el.id}`;
    } else if (el.name) {
      selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
    } else {
      // Fallback: nth-of-type
      const parent = el.parentNode;
      if (parent) {
        const siblings = Array.from(parent.children).filter(child => child.tagName === el.tagName);
        const index = siblings.indexOf(el) + 1;
        selector = `${el.tagName.toLowerCase()}:nth-of-type(${index})`;
      } else {
        selector = el.tagName.toLowerCase();
      }
    }

    // Extract text content or value
    const text = el.innerText || el.value || el.placeholder || el.ariaLabel || '';
    
    context.push({
      selector,
      tagName: el.tagName.toLowerCase(),
      type: el.type || null,
      text: text.trim().substring(0, 100) // Trim and cap text length
    });

    count++;
  }

  return context;
}

// Action Dispatcher
function executeAction(action) {
  try {
    switch (action.type) {
      case 'click': {
        const el = document.querySelector(action.selector);
        if (el) el.click();
        return { success: true, message: `Clicked ${action.selector}` };
      }
      case 'fill_input': {
        const el = document.querySelector(action.selector);
        if (el) {
          el.value = action.value;
          // Trigger events so React/Vue sites register the change
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        return { success: true, message: `Filled ${action.selector}` };
      }
      case 'scroll_page': {
        window.scrollBy(0, action.amount || 500);
        return { success: true, message: `Scrolled page` };
      }
      default:
        return { success: false, message: `Unknown action: ${action.type}` };
    }
  } catch (error) {
    return { success: false, message: `Action failed: ${error.message}` };
  }
}

// Listen for messages from Side Panel or Background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract_context') {
    const context = getPageContext();
    sendResponse({ context });
  } else if (request.action === 'execute_tool') {
    const result = executeAction(request.tool);
    sendResponse(result);
  }
  return true; // Keep message channel open for async response if needed
});
