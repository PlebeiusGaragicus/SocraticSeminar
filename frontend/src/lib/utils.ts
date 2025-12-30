import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { Message as LangGraphMessage } from './services/langgraph.js';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Extract text content from a LangGraph message.
 * Handles both string content and array content with text/tool_use blocks.
 * Matches the reference implementation pattern from deep-agents-ui.
 */
export function extractStringFromMessageContent(message: LangGraphMessage): string {
  const content = (message as { content?: unknown }).content;
  
  if (typeof content === 'string') {
    return content;
  }
  
  if (Array.isArray(content)) {
    return content
      .filter((c: unknown) => {
        if (typeof c === 'string') return true;
        if (typeof c === 'object' && c !== null && 'type' in c) {
          return (c as { type: string }).type === 'text';
        }
        return false;
      })
      .map((c: unknown) => {
        if (typeof c === 'string') return c;
        if (typeof c === 'object' && c !== null && 'text' in c) {
          return (c as { text?: string }).text || '';
        }
        return '';
      })
      .join('');
  }
  
  return '';
}

