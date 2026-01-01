/**
 * CodeMirror extension for inline diff display
 * 
 * Shows pending patches as inline decorations with subtle styling,
 * similar to VS Code / Cursor inline edits.
 */

import {
  EditorView,
  Decoration,
  WidgetType
} from '@codemirror/view';
import type { DecorationSet } from '@codemirror/view';
import { StateField, StateEffect, RangeSetBuilder } from '@codemirror/state';
import type { PendingPatch } from '../stores/types.js';

// =============================================================================
// STATE EFFECTS
// =============================================================================

/** Effect to set the pending patches for this editor */
export const setPendingPatches = StateEffect.define<PendingPatch[]>();

/** Effect to accept a single patch */
export const acceptPatchEffect = StateEffect.define<string>();

/** Effect to reject a single patch */
export const rejectPatchEffect = StateEffect.define<string>();

// =============================================================================
// INLINE REPLACEMENT WIDGET - Minimal, clean design
// =============================================================================

class InlineReplacementWidget extends WidgetType {
  constructor(
    private replaceText: string,
    private patchId: string,
    private onAccept: (id: string) => void,
    private onReject: (id: string) => void
  ) {
    super();
  }

  toDOM(): HTMLElement {
    const wrapper = document.createElement('span');
    wrapper.className = 'cm-inline-addition';
    
    // For multi-line replacements, use block display
    const isMultiline = this.replaceText.includes('\n');
    
    if (isMultiline) {
      wrapper.style.cssText = `
        display: block;
        background: rgba(34, 197, 94, 0.12);
        border-left: 2px solid #22c55e;
        padding: 2px 8px;
        margin: 2px 0;
        color: #4ade80;
        font-family: inherit;
        white-space: pre-wrap;
        position: relative;
      `;
    } else {
      wrapper.style.cssText = `
        display: inline;
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        padding: 0 2px;
        border-radius: 2px;
        font-family: inherit;
      `;
    }

    // Just show the text - no inline buttons (use header buttons instead)
    wrapper.textContent = this.replaceText || '';
    
    // Add data attribute for potential hover interactions
    wrapper.dataset.patchId = this.patchId;

    return wrapper;
  }

  eq(other: WidgetType): boolean {
    return other instanceof InlineReplacementWidget && 
           other.patchId === this.patchId &&
           other.replaceText === this.replaceText;
  }

  ignoreEvent(): boolean {
    return true; // Don't capture events - let them pass through
  }
}

// =============================================================================
// DECORATION STYLES
// =============================================================================

const deletionMark = Decoration.mark({
  class: 'cm-deletion'
});

// =============================================================================
// STATE FIELD FOR PATCHES
// =============================================================================

export interface InlineDiffCallbacks {
  onAccept: (patchId: string) => void;
  onReject: (patchId: string) => void;
}

export function createInlineDiffField(callbacks: InlineDiffCallbacks) {
  return StateField.define<{ patches: PendingPatch[]; decorations: DecorationSet }>({
    create() {
      return { patches: [], decorations: Decoration.none };
    },

    update(value, tr) {
      let patches = value.patches;
      let needsRebuild = false;

      for (const effect of tr.effects) {
        if (effect.is(setPendingPatches)) {
          patches = effect.value;
          needsRebuild = true;
        }
      }

      // If document changed, we need to rebuild decorations
      if (tr.docChanged) {
        needsRebuild = true;
      }

      if (needsRebuild) {
        const decorations = buildDecorations(tr.state.doc.toString(), patches, callbacks);
        return { patches, decorations };
      }

      return value;
    },

    provide: (field) => EditorView.decorations.from(field, (value) => value.decorations)
  });
}

function buildDecorations(
  content: string,
  patches: PendingPatch[],
  callbacks: InlineDiffCallbacks
): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>();
  
  // Sort patches by their position in the document
  const patchPositions: Array<{
    patch: PendingPatch;
    start: number;
    end: number;
  }> = [];

  for (const patch of patches) {
    if (patch.status !== 'pending') continue;
    
    const start = content.indexOf(patch.search);
    if (start === -1) continue;
    
    patchPositions.push({
      patch,
      start,
      end: start + patch.search.length
    });
  }

  // Sort by start position
  patchPositions.sort((a, b) => a.start - b.start);

  // Add decorations for each patch
  for (const { patch, start, end } of patchPositions) {
    // Mark the text being replaced as a deletion
    builder.add(start, end, deletionMark);

    // Add a widget after the deleted text showing the replacement
    const widget = Decoration.widget({
      widget: new InlineReplacementWidget(
        patch.replace,
        patch.id,
        callbacks.onAccept,
        callbacks.onReject
      ),
      side: 1
    });
    builder.add(end, end, widget);
  }

  return builder.finish();
}

// =============================================================================
// THEME EXTENSION
// =============================================================================

export const inlineDiffTheme = EditorView.theme({
  '.cm-deletion': {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    textDecoration: 'line-through',
    color: '#f87171'
  },
  '.cm-inline-addition': {
    color: '#4ade80'
  }
}, { dark: true });

// =============================================================================
// HELPER TO CREATE THE EXTENSION
// =============================================================================

export function inlineDiffExtension(callbacks: InlineDiffCallbacks) {
  return [
    createInlineDiffField(callbacks),
    inlineDiffTheme
  ];
}
