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
    content: '# Thesis: [Title]\n\n**Abstract:** [Brief summary of the position]\n\n## 📜 Supporting Clause: [Clause Title]\n\n### 📝 Definitions and supporting evidence:\n\n`[Term]:` [Definition]\n\n**Source:** [Citation]\n\n---\n\n### 💬 Narrative\n[Explain the reasoning behind this clause.]\n\n## 🗣️ Argument: [Core Position]\n\n### 📝 Definitions and supporting evidence:\n\n`[Term]:` [Definition]\n\n---\n\n### 💬 Narrative\n[Synthesize the supporting clauses into the main argument.]\n\n## 🗣️ Refutation to: [Core Position] | Argument: [Counter-Argument]\n\n### 📝 Definitions and supporting evidence:\n\n`[Term]:` [Definition]\n\n---\n\n### 💬 Narrative\n[Detail the strongest possible counter-argument.]\n' 
  },
  { 
    title: 'Bureau All-Hands', 
    content: 'To whom it may concern,\n\nThis bureau is soooo lame. I am so upset. I want everyone to read this. I am a very important person.\n\n - Anonymous' 
  }
];

