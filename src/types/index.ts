export interface PageElement {
  selector: string;
  fallback_selectors?: string[];
  tagName: string;
  type?: string;
  text: string;
  label: string;
  options?: { value: string; text: string }[];
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
}

export interface ToolCall {
  type: string;
  selector?: string;
  value?: string;
  amount?: number;
  url?: string;
}

export interface ChatRequest {
  message: string;
  page_context?: PageElement[];
  page_text?: string;
}

export interface ChatResponse {
  reply: string;
  tool_calls?: ToolCall[];
}

export interface AutofillRequest {
  page_context: PageElement[];
}

export interface AutofillResponse {
  reply: string;
  tool_calls: ToolCall[];
}

export interface ExecutionResult {
  success: boolean;
  action: string;
  selector: string;
  value: string;
  message: string;
}

export interface ContentScriptResponse {
  context?: PageElement[];
  page_text?: string;
}

export interface BackendChatResponse {
  reply: string;
  tool_calls?: ToolCall[];
}

export interface BackendAutofillResponse {
  reply: string;
  tool_calls: ToolCall[];
}
