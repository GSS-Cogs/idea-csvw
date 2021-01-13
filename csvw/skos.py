from typing import NamedTuple, Union, List, Optional
from dsd import Resource
from namespaces import URI


class ConceptScheme(NamedTuple):
    at_id: URI
    at_type: Union[URI, List[URI]] = "skos:ConceptScheme"
    rdfs_label: Optional[str] = None
    rdfs_comment: Optional[str] = None

class Concept(NamedTuple):
    at_id: URI
    at_type: Union[URI, List[URI]] = "skos:Concept"
    rdfs_label: Optional[str] = None
    rdfs_comment: Optional[str] = None