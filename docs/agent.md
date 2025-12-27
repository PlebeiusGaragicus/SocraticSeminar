# SocraticSeminar

A structured framework for argumentation using Markdown and Python-like schemas. Transform complex ideas into clear, defensible arguments.

## Overview

SocraticSeminar provides a template for constructing rigorous arguments—whether you're writing a thesis, proposing a new methodology, documenting a design decision, or teaching critical thinking.

**Core files:**
- [SocraticSeminar.md](./SocraticSeminar.md) — The template with schema reference
- [CodingAgents.md](./CodingAgents.md) — A complete example on AI and software development

## Structure

Every SocraticSeminar follows this hierarchy:

```
Title + Thesis
├── Supporting Clause 1
│   ├── Definitions & Citations (your "imports")
│   ├── Narrative (your argument)
│   ├── Refutation (strongest counter-argument)
│   └── Reply (your response)
├── Supporting Clause 2...
├── Supporting Clause N...
├── Conclusion
└── Meta-Refutation (optional, for debates)
```

## Who Is This For?

| Audience | Use Case |
|----------|----------|
| **Students** | Learn argumentation, logical thinking, and rhetoric through structured writing |
| **Educators** | Teach essay construction and critical analysis with a clear framework |
| **Researchers** | Document hypotheses, methodologies, and findings with built-in counter-argument handling |
| **Product Teams** | Capture design decisions, trade-offs, and rejected alternatives |
| **Developers** | Build agentic chat applications that guide users through structured reasoning |

## Key Principles

1. **Define before you argue** — All terms, sources, and evidence go in Definitions sections before use in Narrative
2. **Steel-man, don't straw-man** — Present the strongest version of opposing views in Refutations
3. **Reply without new evidence** — Responses to refutations use only previously-defined material
4. **Synthesize, don't summarize** — Conclusions should advance the argument, not repeat it

## Getting Started

1. Copy `SocraticSeminar.md` as your starting template
2. Replace the title and thesis with your central claim
3. Add supporting clauses (typically 2-5) with definitions, narrative, and refutations
4. Write your conclusion synthesizing the arguments
5. Review using the Quick Start Checklist at the bottom of the template

## Example Topics

The framework works for any arguable position:

- **Academic**: "Remote learning is more effective than in-person for adult learners"
- **Technical**: "Microservices architecture is overused in early-stage startups"
- **Business**: "Subscription pricing outperforms one-time purchases for B2B SaaS"
- **Personal**: "A four-day workweek improves both productivity and wellbeing"

## For Developers

The Python schema in `SocraticSeminar.md` can be used to:

- Parse and validate seminar documents
- Build interactive writing assistants
- Create debate/discussion applications
- Generate structured prompts for LLMs

```python
from socratic_seminar import SocraticSeminar, Clause, Reference

seminar = SocraticSeminar(
    title="My Argument",
    thesis="A clear, arguable claim...",
    clauses=[...],
    conclusion="..."
)
```

## Contributing

Contributions welcome! Areas of interest:

- Additional example seminars on diverse topics
- Parser implementations (Python, TypeScript, etc.)
- Web-based seminar builder tools
- Integration with AI writing assistants

## License

MIT
