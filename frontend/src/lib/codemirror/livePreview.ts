/**
 * Live Preview Extension for CodeMirror
 * 
 * Implements Obsidian-style markdown editing where syntax markers
 * are only visible when the cursor is on that line or inside that block.
 */

import {
  Decoration,
  EditorView,
  ViewPlugin,
  WidgetType
} from '@codemirror/view';
import type { DecorationSet, ViewUpdate } from '@codemirror/view';
import { syntaxTree } from '@codemirror/language';
import { Range, RangeSetBuilder } from '@codemirror/state';

// Widget to render a horizontal rule
class HorizontalRuleWidget extends WidgetType {
  toDOM() {
    const hr = document.createElement('hr');
    hr.className = 'cm-hr-rendered';
    return hr;
  }
}

// Get all lines that contain the cursor or selection
function getActiveLines(view: EditorView): Set<number> {
  const activeLines = new Set<number>();
  for (const range of view.state.selection.ranges) {
    const startLine = view.state.doc.lineAt(range.from).number;
    const endLine = view.state.doc.lineAt(range.to).number;
    for (let i = startLine; i <= endLine; i++) {
      activeLines.add(i);
    }
  }
  return activeLines;
}

// Check if cursor is inside a code block
function isInsideCodeBlock(view: EditorView, blockFrom: number, blockTo: number): boolean {
  for (const range of view.state.selection.ranges) {
    if (range.from >= blockFrom && range.to <= blockTo) {
      return true;
    }
  }
  return false;
}

// Build decorations for live preview
function buildDecorations(view: EditorView): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>();
  const activeLines = getActiveLines(view);
  const decorations: Range<Decoration>[] = [];

  // Walk through the syntax tree
  syntaxTree(view.state).iterate({
    enter(node) {
      const lineStart = view.state.doc.lineAt(node.from).number;
      const lineEnd = view.state.doc.lineAt(node.to).number;
      const isActive = [...activeLines].some(l => l >= lineStart && l <= lineEnd);

      // ATX Headings (#, ##, etc.)
      if (node.name === 'ATXHeading1' || node.name === 'ATXHeading2' || 
          node.name === 'ATXHeading3' || node.name === 'ATXHeading4' ||
          node.name === 'ATXHeading5' || node.name === 'ATXHeading6') {
        const level = parseInt(node.name.slice(-1));
        const line = view.state.doc.lineAt(node.from);
        
        // Find the header mark (# symbols)
        const text = view.state.sliceDoc(node.from, node.to);
        const hashMatch = text.match(/^(#{1,6})\s*/);
        
        if (hashMatch) {
          const markEnd = node.from + hashMatch[0].length;
          
          // Add styling class to the whole heading
          decorations.push(
            Decoration.line({ class: `cm-header cm-header-${level}` }).range(line.from)
          );
          
          // Hide hash marks when not active
          if (!isActive) {
            decorations.push(
              Decoration.replace({}).range(node.from, markEnd)
            );
          } else {
            // Show hash marks faintly when active
            decorations.push(
              Decoration.mark({ class: 'cm-formatting-header' }).range(node.from, markEnd)
            );
          }
        }
      }

      // Strong/Bold (**text** or __text__)
      if (node.name === 'StrongEmphasis') {
        const text = view.state.sliceDoc(node.from, node.to);
        const marker = text.startsWith('**') ? '**' : '__';
        const markerLen = 2;
        
        // Add bold styling
        decorations.push(
          Decoration.mark({ class: 'cm-strong' }).range(node.from, node.to)
        );
        
        if (!isActive) {
          // Hide markers
          decorations.push(
            Decoration.replace({}).range(node.from, node.from + markerLen)
          );
          decorations.push(
            Decoration.replace({}).range(node.to - markerLen, node.to)
          );
        } else {
          // Show markers faintly
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.from, node.from + markerLen)
          );
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.to - markerLen, node.to)
          );
        }
      }

      // Emphasis/Italic (*text* or _text_)
      if (node.name === 'Emphasis') {
        // Add italic styling
        decorations.push(
          Decoration.mark({ class: 'cm-emphasis' }).range(node.from, node.to)
        );
        
        if (!isActive) {
          // Hide markers
          decorations.push(
            Decoration.replace({}).range(node.from, node.from + 1)
          );
          decorations.push(
            Decoration.replace({}).range(node.to - 1, node.to)
          );
        } else {
          // Show markers faintly
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.from, node.from + 1)
          );
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.to - 1, node.to)
          );
        }
      }

      // Inline code (`code`)
      if (node.name === 'InlineCode') {
        decorations.push(
          Decoration.mark({ class: 'cm-inline-code' }).range(node.from, node.to)
        );
        
        if (!isActive) {
          decorations.push(
            Decoration.replace({}).range(node.from, node.from + 1)
          );
          decorations.push(
            Decoration.replace({}).range(node.to - 1, node.to)
          );
        } else {
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.from, node.from + 1)
          );
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.to - 1, node.to)
          );
        }
      }

      // Fenced code blocks (```)
      if (node.name === 'FencedCode') {
        const cursorInside = isInsideCodeBlock(view, node.from, node.to);
        
        // Add code block styling to all lines
        const startLine = view.state.doc.lineAt(node.from);
        const endLine = view.state.doc.lineAt(node.to);
        
        for (let i = startLine.number; i <= endLine.number; i++) {
          const line = view.state.doc.line(i);
          decorations.push(
            Decoration.line({ class: 'cm-codeblock-line' }).range(line.from)
          );
        }
        
        // Find the opening and closing fence
        const text = view.state.sliceDoc(node.from, node.to);
        const lines = text.split('\n');
        const openFenceLine = view.state.doc.lineAt(node.from);
        const closeFenceLine = view.state.doc.lineAt(node.to);
        
        if (!cursorInside) {
          // Hide opening fence line (``` or ```language)
          decorations.push(
            Decoration.replace({}).range(openFenceLine.from, openFenceLine.to + 1)
          );
          
          // Hide closing fence line if it exists and is just ```
          if (lines[lines.length - 1].trim().match(/^`{3,}$/)) {
            decorations.push(
              Decoration.replace({}).range(closeFenceLine.from - 1, closeFenceLine.to)
            );
          }
        } else {
          // Show fences faintly when cursor is inside
          decorations.push(
            Decoration.mark({ class: 'cm-formatting-code-fence' }).range(openFenceLine.from, openFenceLine.to)
          );
          if (lines[lines.length - 1].trim().match(/^`{3,}$/)) {
            decorations.push(
              Decoration.mark({ class: 'cm-formatting-code-fence' }).range(closeFenceLine.from, closeFenceLine.to)
            );
          }
        }
      }

      // Block quotes (>)
      if (node.name === 'Blockquote') {
        const startLine = view.state.doc.lineAt(node.from);
        const endLine = view.state.doc.lineAt(node.to);
        
        for (let i = startLine.number; i <= endLine.number; i++) {
          const line = view.state.doc.line(i);
          const lineText = line.text;
          const quoteMatch = lineText.match(/^(\s*>\s*)/);
          
          if (quoteMatch) {
            decorations.push(
              Decoration.line({ class: 'cm-blockquote-line' }).range(line.from)
            );
            
            const lineActive = activeLines.has(i);
            if (!lineActive) {
              decorations.push(
                Decoration.replace({}).range(line.from, line.from + quoteMatch[1].length)
              );
            } else {
              decorations.push(
                Decoration.mark({ class: 'cm-formatting' }).range(line.from, line.from + quoteMatch[1].length)
              );
            }
          }
        }
      }

      // Links [text](url)
      if (node.name === 'Link') {
        decorations.push(
          Decoration.mark({ class: 'cm-link' }).range(node.from, node.to)
        );
        
        // Find the URL part
        const text = view.state.sliceDoc(node.from, node.to);
        const linkMatch = text.match(/^\[([^\]]*)\]\(([^)]*)\)$/);
        
        if (linkMatch && !isActive) {
          // Hide [ and ]( and )
          const textStart = node.from + 1;
          const textEnd = node.from + 1 + linkMatch[1].length;
          const urlStart = textEnd + 2; // ](
          const urlEnd = node.to - 1;
          
          decorations.push(Decoration.replace({}).range(node.from, textStart)); // [
          decorations.push(Decoration.replace({}).range(textEnd, node.to)); // ](url)
        }
      }

      // Horizontal rules (---, ***, ___)
      if (node.name === 'HorizontalRule') {
        const line = view.state.doc.lineAt(node.from);
        if (!activeLines.has(line.number)) {
          decorations.push(
            Decoration.replace({ widget: new HorizontalRuleWidget() }).range(node.from, node.to)
          );
        } else {
          decorations.push(
            Decoration.mark({ class: 'cm-formatting' }).range(node.from, node.to)
          );
        }
      }

      // List items
      if (node.name === 'ListItem') {
        const line = view.state.doc.lineAt(node.from);
        decorations.push(
          Decoration.line({ class: 'cm-list-item' }).range(line.from)
        );
      }
    }
  });

  // Sort decorations by position and add to builder
  decorations.sort((a, b) => a.from - b.from || a.value.startSide - b.value.startSide);
  
  for (const deco of decorations) {
    builder.add(deco.from, deco.to, deco.value);
  }

  return builder.finish();
}

// The live preview plugin
export const livePreviewPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = buildDecorations(view);
    }

    update(update: ViewUpdate) {
      if (update.docChanged || update.selectionSet || update.viewportChanged) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations
  }
);

// Theme extension for live preview styling
export const livePreviewTheme = EditorView.theme({
  // Headers
  '.cm-header': {
    fontWeight: 'bold'
  },
  '.cm-header-1': {
    fontSize: '2em',
    lineHeight: '1.2'
  },
  '.cm-header-2': {
    fontSize: '1.5em',
    lineHeight: '1.3'
  },
  '.cm-header-3': {
    fontSize: '1.25em',
    lineHeight: '1.4'
  },
  '.cm-header-4': {
    fontSize: '1.1em'
  },
  '.cm-header-5': {
    fontSize: '1em'
  },
  '.cm-header-6': {
    fontSize: '0.9em'
  },

  // Formatting markers (shown faintly when active)
  '.cm-formatting': {
    opacity: '0.4',
    color: '#888'
  },
  '.cm-formatting-header': {
    opacity: '0.4',
    color: '#f59e0b'
  },
  '.cm-formatting-code-fence': {
    opacity: '0.4',
    color: '#888'
  },

  // Strong/Bold
  '.cm-strong': {
    fontWeight: 'bold'
  },

  // Emphasis/Italic
  '.cm-emphasis': {
    fontStyle: 'italic'
  },

  // Inline code
  '.cm-inline-code': {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    padding: '0.1em 0.3em',
    borderRadius: '3px',
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    fontSize: '0.9em'
  },

  // Code blocks
  '.cm-codeblock-line': {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    fontSize: '0.9em'
  },

  // Blockquotes
  '.cm-blockquote-line': {
    borderLeft: '3px solid #f59e0b',
    paddingLeft: '1em',
    color: '#a1a1aa',
    fontStyle: 'italic'
  },

  // Links
  '.cm-link': {
    color: '#3b82f6',
    textDecoration: 'underline',
    cursor: 'pointer'
  },

  // Horizontal rule
  '.cm-hr-rendered': {
    border: 'none',
    borderTop: '1px solid #52525b',
    margin: '1em 0'
  },

  // List items
  '.cm-list-item': {
    paddingLeft: '0.5em'
  }
}, { dark: true });

// Combined extension
export const livePreview = [livePreviewPlugin, livePreviewTheme];

