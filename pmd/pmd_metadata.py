from rdflib.graph import Dataset as RDFDataset
from rdflib.term import BNode
from pmdcat import DataCube, Dataset, Catalog, CatalogRecord
from namespaces import namespaces
from urllib.parse import urljoin
import json

DEFAULT_BASE_URI = "http://gss-data.org.uk/"

class PMDMetadata():

    def __init__(self, specification=None):
        self.load_specification(specification)

    def load_specification(self, specification):
        if specification:
            self._specification = json.load(open(specification))
        else:
            self._specification = None

    def process_specification(self, specification):
        if self._specification is None:
            self.load_specification(specification)

        spec = self._specification

        dataset_id = spec.get("dataset_id")

        self.quads = RDFDataset()
        self.quads.namespace_manager = namespaces

        self.catalog = Catalog()
        self.catalog.record = CatalogRecord()
        self.dataset = Dataset()
        self.datacube = DataCube()

        self.metadata_graph = urljoin(DEFAULT_BASE_URI, f'graph/{dataset_id}-metadata')

        self.catalog.uri = urljoin(DEFAULT_BASE_URI, 'catalog/datasets')
        self.catalog.set_graph(self.metadata_graph)

        self.catalog.record.uri = urljoin(DEFAULT_BASE_URI, f'data/{dataset_id}-catalog-record')
        self.catalog.record.set_graph(self.metadata_graph)
        self.catalog.record.metadataGraph = self.metadata_graph
        self.catalog.record.primaryTopic = self.dataset

        self.dataset.uri = urljoin(DEFAULT_BASE_URI, f'data/{dataset_id}')
        self.dataset.set_graph(self.metadata_graph)
        self.dataset.graph = urljoin(DEFAULT_BASE_URI, f'graph/{dataset_id}')
        self.dataset.sparqlEndpoint = urljoin(DEFAULT_BASE_URI, '/sparql')
        self.dataset.datasetContents = self.datacube

        self.dataset.title = spec.get("title")
        self.dataset.description = spec.get("description")
        self.dataset.theme = spec.get("theme")
        self.dataset.spatial = spec.get("spatial")
        self.dataset.temporal = spec.get("temporal")
        self.dataset.wasDerivedFrom = spec.get("derived_from")

        self.datacube.uri = urljoin(DEFAULT_BASE_URI, f'data/{dataset_id}#dataset')
        self.datacube.set_graph(self.metadata_graph)

        self.catalog.add_to_dataset(self.quads)

    def serialize(self, filepath, format="trig"):
        self.quads.serialize(filepath, format=format)
