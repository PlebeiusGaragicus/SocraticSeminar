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
    content: '---\ntitle: Socratic Seminar Template\nauthor: [Your Name]\ndate: [Date]\ntags: [topic]\n---\n\n# [Title]\n\n## Thesis\n*A clear, arguable statement that your entire document will support.*\n\n---\n\n## Supporting Clause 1 - "[One-line summary]"\n\n### Definitions & Citations\n- `term`: Definition\n- `source`: [Citation](URL)\n\n### Narrative\nWrite your reasoning here. Build your case using the definitions above.\n\n### Refutation\n*Present the strongest version of opposing viewpoints.*\n\n### Reply\nExplain why your original argument still holds.\n\n---\n\n## Conclusion\n*Synthesize your supporting clauses and restate your thesis.*\n' 
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
