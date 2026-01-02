# File Templates

The system provides a set of pre-defined templates for creating new artifacts (files). These templates allow users to quickly scaffold common document types like project plans, research notes, and meeting transcripts.

## Storage Location

The templates are stored in a dedicated library file:

**File Path:** `frontend/src/lib/templates.ts`

```typescript
export interface FileTemplate {
  title: string;
  content: string;
}

export const FILE_TEMPLATES: FileTemplate[] = [
  { 
    title: 'Socratic Seminar', 
    content: '---\nauthor: [nostr public key]\nevent: [nostr event id]\ntitle: "[Title]"\ndate: [YYYY-MM-DD]\nreply_to: [parent nostr event id]\n---\n\n# <span style="color:yellow">Thesis:</span> [Title]\n\n**Abstract:** [Brief summary of the position]\n\n## 📜 <span style="color:green">Supporting Clause:</span> [Clause Title]\n\n### 📝 <span style="color:orange">Definitions and supporting evidence:</span>\n\n`[Term]:` [Definition]\n\n**Source:** [Citation]\n\n---\n\n### 💬 <span style="color:purple">Narrative</span>\n[Explain the reasoning behind this clause.]\n\n## 🗣️ <span style="color:red">Argument:</span> [Core Position]\n\n### 📝 <span style="color:orange">Definitions and supporting evidence:</span>\n\n`[Term]:` [Definition]\n\n---\n\n### 💬 <span style="color:purple">Narrative</span>\n[Synthesize the supporting clauses into the main argument.]\n\n## 🗣️ <span style="color:red">Refutation to:</span> [Core Position] | <span style="color:red">Argument:</span> [Counter-Argument]\n\n### 📝 <span style="color:orange">Definitions and supporting evidence:</span>\n\n`[Term]:` [Definition]\n\n---\n\n### 💬 <span style="color:purple">Narrative</span>\n[Detail the strongest possible counter-argument.]\n' 
  },
  { 
    title: 'Bureau All-Hands', 
    content: 'To whom it may concern,\n\nThis bureau is soooo lame. I am so upset. I want everyone to read this. I am a very important person.\n\n - Anonymous' 
  }
];
```

## Updating Templates

To add, remove, or modify a template:

1.  Open `frontend/src/lib/templates.ts`.
2.  Add or edit an object in the `FILE_TEMPLATES` array with the following structure:
    *   `title`: The name shown in the UI (e.g., 'Weekly Report').
    *   `content`: The initial Markdown content for the file. Use `\n` for newlines.

## UI Integration

Templates are surfaced in the **New File Modal** (`frontend/src/lib/components/NewFileModal.svelte`). When a user selects a template, a new artifact is created with the template's content and opened in the workspace.

## Future Plans

As the project evolves, we plan to:
- Allow agents to contribute new templates dynamically via backend configuration.
- Support user-defined templates stored in IndexedDB.
- Add category grouping for templates (e.g., 'Writing', 'Coding', 'Planning').
