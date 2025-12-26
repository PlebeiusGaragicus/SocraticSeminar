---
title: SocraticSeminar Outline
what goes here?
---


# Title - "This is our title"

## Thesis:

This is where I write things

## Supporting Clause - "one-liner statement

### Background, definitions, citations:

 - List URLS like in a bibliography.  Also, we can put commentary.  These are more like "end notes" instead of being a simple listed bibliography.

 - `Something`: we can give background or define terms here.  Whatever we want.  This is like our "import" statment in code - we can then "use" these down below when we make our argument

 - `American Civil War`: a brief description of this event, perhaps start/end dates can go here.

 - `photo: political comic of Abraham Lincoln`: We can also place links here to embed media of all kinds. [Abraham Lincoln political comic](./comic1.png)

### Narrative:

This is our argument.

Reference media from above, as needed.  Since we've "imported" it into our argument, we can reference it here.

### Refutation: "The usage of AI agents is harmful, to mental health, memory and cognition - esp. for children"

#### Background, definitions, citations:

 - as needed, we can provide further evidence.

 - what we can't do is re-define the above.  Our argument can propose a NEW definition or alteration, but we can't just "over write" it here and make an argument off of it.  We'll need to provide evidence (or point to something), then we can narrate about it below

#### Narrative

> we can quote from the above and reply, as needed.

We can also just talk and make new arguments.


### Reply

This section is our "reply to the refutation."  This section can be used to allow us to list common counter arguments in our "Refutations" section, but then provide logic to redirect our consideration for it.  We don't list evidence here, as all so-called "citations" 


---

## Supporting Clause - "We can have as many supporting clauses as we need"

### Background, definitions, citations:

as needed, or empty

### Narrative:

Text goes here

### Refutation:

... if any

### Reply

... if refuted

---

REPEAT...

---

```py
class Definition:
    # what's a more general word than "term" we can use?  For a collection of photos this could be "political photos of the era", for example
    term: str

    # not sure what datatype - this can be a list of files (photo, video, etc) and/or list of URLs. Perhaps these would be kept in the same "folder"
    media: [file or url]

    # A `Definition` is like a footnote or endnote, and this would be the content or author's remark
    narrative: str


# This is a single-encapsulted "argument" or attempted statement of fact to establish our logic, block by block
class Clause:
    definitions: [Definition]
    narrative: str

    # we may have a list of refutations, kept and replied to in order to establish our past thoughts on the issue, old ways of thinking, past contraversies, etc.  These can be included to further context to stregnthen our argument.
    refutation: [Refutation]


# extends argument, but needs a "reply" by the author
class Refutation(Clause):
    # this is written by the author of the thesis in order to "respond to it"
    reply: str


class SocraticSeminar:
    # Abstract
    Thesis: str

    Supporting_Arguments: [Clause]

    Narrative: str

    # just like how individual Clauses may be refuted, our entire Seminar may also have a "counter" - if debating on-stage, this would be our interloquitor's content and message
    Refutations: [SocraticSeminar]
```