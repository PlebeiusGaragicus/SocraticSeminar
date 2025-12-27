---
title: SocraticSeminar Template
author: [Your Name]
date: [Date]
version: 1.0
tags: [topic, category]
---

# [Title] - "A concise, memorable statement of your position"

## Thesis

*A clear, arguable statement that your entire document will support. This is your central claim—everything below serves to prove or defend it.*

> Example: "The Socratic method remains the most effective pedagogical approach for developing critical thinking skills in the digital age."

---

## Supporting Clause 1 - "[One-line summary of this argument]"

### Definitions & Citations

Define key terms, provide context, and cite sources. Think of this as your "imports"—you establish these here so you can reference them in your narrative.

| Label | Type | Description |
|-------|------|-------------|
| `term` | Definition | Explanation of the term as used in your argument |
| `source` | Citation | URL, book reference, or academic citation |
| `media` | Evidence | Link to image, video, or document: `[description](./path)` |

**Format examples:**

- `Socratic Method`: A form of cooperative argumentative dialogue that stimulates critical thinking through asking and answering questions. Originated with Socrates (470–399 BCE).

- `Source: Plato's Dialogues`: Primary source documenting Socratic questioning. [Link](https://example.com)

- `Figure 1: Bloom's Taxonomy`: Visual hierarchy of cognitive skills. [View diagram](./blooms_taxonomy.png)

### Narrative

*Your argument for this clause. Build your case using the definitions and citations above. Be specific, logical, and persuasive.*

Write your reasoning here. Reference your defined terms and evidence naturally within your prose. Each paragraph should advance your argument toward supporting the thesis.

### Refutation - "[State the counter-argument honestly]"

*Present the strongest version of opposing viewpoints. Steel-man, don't straw-man.*

#### Definitions & Citations

- Additional evidence or context needed to fairly represent the counter-argument
- You may NOT redefine terms from above—propose new definitions with justification if needed

#### Narrative

> "Quote the opposing view or summarize it faithfully."

Present the counter-argument's logic. Why might a reasonable person disagree with your clause?

### Reply

*Your response to the refutation. Address the counter-argument directly without introducing new evidence (all citations belong in Definitions sections).*

Explain why your original argument still holds despite the refutation. Acknowledge valid points while demonstrating why they don't undermine your thesis.

---

## Supporting Clause 2 - "[One-line summary]"

### Definitions & Citations

*As needed, or leave empty if building on previously defined terms.*

### Narrative

*Your argument for this clause.*

### Refutation - "[Counter-argument, if any]"

#### Definitions & Citations

*Additional context for the refutation.*

#### Narrative

*The opposing view.*

### Reply

*Your response.*

---

## Supporting Clause N - "[Continue as needed]"

*Repeat the clause structure for each major supporting argument. Most seminars have 2-5 supporting clauses.*

---

## Conclusion

*Synthesize your supporting clauses. Restate your thesis in light of the arguments made. What should the reader take away?*

---

## Meta-Refutation (Optional)

*If presenting in a debate format, this section contains the opposing side's complete counter-seminar—a full SocraticSeminar structure arguing against your thesis.*

---

# Schema Reference

```python
from typing import List, Optional, Union
from dataclasses import dataclass
from enum import Enum

class ReferenceType(Enum):
    DEFINITION = "definition"    # Term or concept explanation
    CITATION = "citation"        # Academic or web source
    MEDIA = "media"              # Image, video, audio, document


@dataclass
class Reference:
    """A single piece of supporting material for an argument."""
    label: str                              # Identifier used in narrative (e.g., "Socratic Method")
    ref_type: ReferenceType                 # Type of reference
    content: str                            # Description, URL, or explanation
    media_path: Optional[str] = None        # Path to local file if applicable


@dataclass
class Refutation:
    """A counter-argument with the author's reply."""
    claim: str                              # One-line statement of the counter-argument
    references: List[Reference]             # Supporting material for the refutation
    narrative: str                          # The counter-argument's reasoning
    reply: str                              # Author's response to the refutation


@dataclass 
class Clause:
    """A single supporting argument for the thesis."""
    summary: str                            # One-line description of this argument
    references: List[Reference]             # Definitions, citations, and media
    narrative: str                          # The argument itself
    refutations: List[Refutation] = None    # Counter-arguments and replies


@dataclass
class SocraticSeminar:
    """A complete structured argument."""
    title: str                              # Document title
    thesis: str                             # Central claim
    clauses: List[Clause]                   # Supporting arguments
    conclusion: str                         # Synthesis and takeaway
    meta_refutation: Optional['SocraticSeminar'] = None  # Opposing seminar (for debates)
    
    # Metadata
    author: str = ""
    date: str = ""
    version: str = "1.0"
    tags: List[str] = None
```

---

# Quick Start Checklist

- [ ] **Thesis**: Is it clear, arguable, and specific?
- [ ] **Clauses**: Does each one directly support the thesis?
- [ ] **Definitions**: Are all key terms defined before use?
- [ ] **Citations**: Is evidence properly sourced?
- [ ] **Refutations**: Have you addressed the strongest counter-arguments?
- [ ] **Replies**: Do your replies strengthen rather than merely dismiss?
- [ ] **Conclusion**: Does it synthesize, not just summarize?