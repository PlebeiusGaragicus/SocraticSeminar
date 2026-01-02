```python
from typing import Union, List, Optional
from pathlib import Path
from pydantic import HttpUrl
from langchain.schema import AIMessage, HumanMessage
from datetime import datetime

class Analysis:
    """This is AI-generated inference or analysis of the media"""

    prompt: HumanMessage
    """The prompt that was provided to the AI"""

    model: str
    """The model that was used to generate the analysis"""

    reply: AIMessage
    """The reply from the AI"""

class Bibliography:
    """Standardized metadata for generating citations (APA, MLA, etc.)"""
    
    author: Optional[str] = None
    """e.g., 'Karpathy, A.' or 'Stanford HAI'"""
    
    title: Optional[str] = None
    """The title of the article, post, or page"""
    
    published_date: Optional[datetime] = None
    """When the content was originally published"""
    
    publisher: Optional[str] = None
    """e.g., 'X', 'Medium', 'Nature'"""
    
    resource_type: Optional[str] = None
    """e.g., 'Post', 'Article', 'Dataset'"""

class Media:
    """This is a single file (photo, video, csv, etc)"""

    path: Path
    """The path to the media file"""

    ai_analysis: Optional[List[Analysis]] = None
    """This is AI-generated inference or analysis of the media"""

    bibliography: Optional[Bibliography] = None
    """Metadata for citation purposes"""

class WebResource:
    """This is a single web resource (photo, video, etc) and/or URL"""

    scrape: Media
    """The scrape of the web resource"""

    source_url: HttpUrl
    """The URL of the web resource"""

    timestamp: datetime
    """The timestamp of the web resource"""

    snapshot: Path
    """The PDF snapshot of the web resource taken at the time of the scrape"""

    ai_analysis: Optional[List[Analysis]] = None
    """
    This is AI-generated inference or analysis of the media.
    It may provide, for example, cleaned audio, a transcript of human dialogue, an analysis of a video which determines the make and model of a vehicle and or a summary of a podcast
    We may have multiple analysis, each with their own prompt
    """

    bibliography: Optional[Bibliography] = None
    """Metadata for citation purposes"""

class Highlight:
    """This is essentially a quote from a source (ebook, web article, etc)"""

    source: Union[Media, WebResource]

    quote: str #TODO; consider using cfiRange or some object to provide location data


class Definition:
    term: str

    media: List[Union[Media, WebResource]]
    """A list of media files (photo, video, etc) and/or list of URLs. Perhaps these would be kept in the same 'folder' together."""

    definition: str


class Clause:
    """This is a single-encapsulted "argument" or attempted statement of fact to establish our logic, block by block"""

    title: str

    definitions: Optional[List[Union[Definition, Highlight]]] = None
    """
    - our supporting evidence and 'grounding' that establishes meaning, common terms and provides point-of-view
    - it's also where we can `point to something` and quote it - like a book or article highlight
    """

    narrative: str
    """the body of an argument which pulls from earlier-defined fact"""

    refutation: Optional[List[Union[str, Clause, 'SocraticSeminar']]] = None
    """
    - we may have a list of refutations, kept and replied to in order to establish our past thoughts on the issue, old ways of thinking, past contraversies, etc.
    - These can be included to further context to stregnthen our argument.
    - just like how individual Clauses may have a "counter" - if debating on-stage, this would be our interloquitor's counter content and message
    """



class SocraticSeminar:
    """This `Seminar` object defines a cogent argument or `position paper` from an author.  It is the self-contained material for one side in a debate"""

    title: str

    abstract: Optional[str] = None

    supporting_clauses: Optional[List[Clause]] = None

    argument: Clause

    refutations: Optional[List[Union[str, Clause, 'SocraticSeminar']]] = None
```