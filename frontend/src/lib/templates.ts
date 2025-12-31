/**
 * Pre-defined templates for creating new artifacts.
 */
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

