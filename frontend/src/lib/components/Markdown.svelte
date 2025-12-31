<script lang="ts">
  import { marked } from 'marked';
  import Prism from 'prismjs';
  import DOMPurify from 'dompurify';
  import { browser } from '$app/environment';

  // Import common languages for Prism
  import 'prismjs/components/prism-typescript';
  import 'prismjs/components/prism-javascript';
  import 'prismjs/components/prism-python';
  import 'prismjs/components/prism-bash';
  import 'prismjs/components/prism-json';
  import 'prismjs/components/prism-markdown';
  import 'prismjs/components/prism-css';
  import 'prismjs/components/prism-yaml';
  import 'prismjs/components/prism-rust';
  import 'prismjs/components/prism-go';

  interface Props {
    content: string;
    className?: string;
  }

  let { content, className = "" }: Props = $props();

  // Configure marked with Prism highlighting once
  const renderer = new marked.Renderer();
  
  renderer.code = function({ text, lang }: { text: string, lang?: string }) {
    const language = lang || 'plaintext';
    let highlighted = text;
    
    if (Prism.languages[language]) {
      highlighted = Prism.highlight(text, Prism.languages[language], language);
    } else {
      // Escape HTML for plain text code blocks
      highlighted = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }
    
    return `<pre class="language-${language}"><code class="language-${language}">${highlighted}</code></pre>`;
  };

  marked.setOptions({
    renderer,
    breaks: true,
    gfm: true
  });

  // Reactive derived HTML
  const html = $derived.by(() => {
    if (!content) return '';
    const rawHtml = marked.parse(content) as string;
    
    // Use DOMPurify only in the browser to avoid SSR issues
    if (browser) {
      return DOMPurify.sanitize(rawHtml);
    }
    return rawHtml;
  });
</script>

<svelte:head>
  <!-- Prism Tomorrow Theme -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" />
</svelte:head>

<div 
  class="markdown-content prose prose-sm prose-invert max-w-none 
    prose-p:leading-relaxed prose-pre:bg-zinc-900/50 prose-pre:border prose-pre:border-zinc-700/50
    prose-code:text-amber-200/90 prose-code:bg-zinc-900/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
    prose-a:text-amber-500 hover:prose-a:text-amber-400 prose-a:no-underline hover:prose-a:underline
    prose-headings:text-zinc-100 prose-headings:font-semibold
    {className}"
>
  {@html html}
</div>

<style>
  /* Fix for Prism's default background and padding to match our prose styling */
  :global(.markdown-content pre[class*="language-"]) {
    margin: 1.5rem 0;
    padding: 1rem;
    border-radius: 0.5rem;
    background: rgba(24, 24, 27, 0.5); /* zinc-900 at 50% */
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }

  :global(.markdown-content code[class*="language-"]) {
    background: transparent !important;
    padding: 0 !important;
    font-size: 0.875rem;
    color: inherit;
    text-shadow: none;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* Custom scrollbar for code blocks */
  :global(.markdown-content pre::-webkit-scrollbar) {
    height: 8px;
  }
  :global(.markdown-content pre::-webkit-scrollbar-track) {
    background: transparent;
  }
  :global(.markdown-content pre::-webkit-scrollbar-thumb) {
    background: rgba(63, 63, 70, 0.5); /* zinc-700 */
    border-radius: 4px;
  }
  :global(.markdown-content pre::-webkit-scrollbar-thumb:hover) {
    background: rgba(82, 82, 91, 0.5); /* zinc-600 */
  }
</style>
