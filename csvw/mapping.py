import json
import re
import logging
import warnings
from typing import Dict, List, Set, Union, Text, TextIO, NewType, Any, Optional
from pathlib import Path
from io import TextIOBase
from unidecode import unidecode
from uritemplate import variables
from dsd import DimensionComponent, DimensionProperty, MeasureComponent, MeasureProperty, AttributeComponent, \
    AttributeProperty, Component, Resource, DataSet, DSD
from table import Column, Table, TableSchema, ForeignKey
from namespaces import prefix_map, URI
from skos import ConceptScheme

# This ignores measure-dimensions which need special treatment.
# This doesn't include failures when attributes are missing. No real checking going on here yet. 
# Should be defensive once we decide on spec requirements.

# One map per csv, or one map for multiple csvs?

DEFAULT_BASE_URI = "http://gss-data.org.uk/data/gss_data/"

def pathify(label):
    """
      Converts a label into kebab-case. "Column Name" -> "column-name".
    """
    return re.sub(r'-$', '',
                  re.sub(r'-+', '-',
                         re.sub(r'[^\w/]|_', '-', unidecode(label).lower())))

def namify(column_header: str):
    """
      Converts a label into snake_case. "Column Name" -> "column_name".
    """
    return pathify(column_header).replace('-', '_')

def classify(column_header: str):
    """
      Converts a label into UpperCamelCase. "Column Name" -> "ColumnName".
    """
    return ''.join(part.capitalize() for part in pathify(column_header).split('-'))

class CSVWMapping():
    def __init__(self, specification=None):
        self.load_specification(specification)
        self._map: Dict[str, Any] = {}
        # Attributes used in buidling the map:
        self._column_names: List[str] = []
        self._columns: Dict[str, Column] = {}
        self._components: List[Component] = []
        self._keys: List[str] = []
        # Not implemented here for a moment:
        self._foreign_keys: Optional[List[ForeignKey]] = []
        self._external_tables: List[Table] = []

    def load_specification(self, specification):
        if specification:
            self._specification = json.load(open(specification))
        else:
            self._specification = None
        
    # Here we can enforce schema validation - ideally with json schema?
    def is_specification_valid(self):
        pass
    
    def process_specification(self, specification):

        if self._specification is None:
            self.load_specification(specification)

        spec = self._specification

        if spec.get("dataset_id"):
            base_uri = f"{DEFAULT_BASE_URI}{spec.get('dataset_id')}"
        else:
            base_uri = f"{DEFAULT_BASE_URI}{pathify(spec.get('title'))}"


        def prepend_base_uri(function, base_uri=spec.get("dataset_uri", base_uri)):
            def wrapper(name=None):
                uri = f"{base_uri}{function(name)}"
                return(uri)
            return wrapper

        @prepend_base_uri
        def make_local_dimension_uri(name):
            uri = f"#dimension/{pathify(name)}"
            return(uri)

        @prepend_base_uri
        def make_local_measure_uri(name):
            uri = f"#measure/{pathify(name)}"
            return(uri)

        @prepend_base_uri
        def make_local_component_uri(name):
            uri = f"#component/{pathify(name)}"
            return(uri)

        @prepend_base_uri
        def make_local_concept_uri(name):
            uri = f"#concept/{pathify(name)}/{{{namify(name)}}}"
            return(uri)

        @prepend_base_uri
        def make_local_concept_scheme_uri(name):
            uri = f"#scheme/{pathify(name)}"
            return(uri)

        @prepend_base_uri
        def make_local_class_uri(name):
            uri = f"#class/{classify(name)}"
            return(uri)
        
        @prepend_base_uri
        def make_dataset_contents_uri(name=None):
            uri = f"#dataset"
            return(uri)

        @prepend_base_uri
        def make_dataset_definition_uri(name=None):
            uri = f"#structure"
            return(uri)

        @prepend_base_uri
        def make_tables_uri(name=None):
            uri = f"#tables"
            return(uri)
        
        @prepend_base_uri
        def make_observation_uri(keys):
            uri = "/" + "/".join([f"{{{key}}}" for key in keys])
            return(uri)
        
        self._components = []
        self._columns = {}
        self._column_names = [x["name"] for x in spec["columns"]]
        self._keys = [namify(x["name"]) for x in spec["columns"] if x["component_type"] == "dimension"]

        for column in spec["columns"]:
            self._columns[column["name"]] = Column(
                name=namify(column["name"]),
                titles=[column["title"]],
                datatype=column.get("datatype"),
                suppressOutput=column.get("suppress_output"),
                virtual=column.get("virtual"),
                required=column.get("required"),
                propertyUrl=column.get("component_uri"),
                valueUrl=column.get("value_uri")
            )

            # DIMENSIONS -----------------------------------------------------------------------------------------------

            if column["component_type"] == "dimension":
                if column.get("preset"):
                    pass

                # If component_uri is specified, use that - failing that, coin a dimension URI
                dimension_uri = column.get("component_uri", make_local_dimension_uri(column.get('name')))

                #CODELISTS ---------------------------------------------------------------------------------------------

                # If codelist_filename and codelist_uri not specified, no codelist
                # If codelist_uri is specified, use that
                # If codelist_filepath is True but codelist_uri is unspecified, create a default
                # If codelist_filepath and codelist_uri are specified just use both
                if not column.get("codelist_filename") and not column.get("codelist_uri"):
                    codelist_uri = None
                    # When no codelist, we set the dimension's range to rdfs:Resource
                    # TODO we need to be careful setting such a wide range if a parent property is set
                    dimension_range = 'https://www.w3.org/2000/01/rdf-schema#Resource'
                elif column.get("codelist_uri"):
                    codelist_uri = column.get("codelist_uri")
                elif column.get("codelist_filename"):
                    codelist_uri = make_local_concept_scheme_uri(column.get('name'))

                if column.get("codelist_uri") or column.get("codelist_filename"):
                    # When there is a codelist, we set the dimension's range to skos:Concept
                    dimension_range = 'http://www.w3.org/2004/02/skos/core#Concept'
                
                if column.get("codelist_filename"):
                    if not column.get("value_uri"):
                        value_uri = make_local_concept_uri(column.get('name'))

                    self._external_tables.append(
                        {
                            "@context": "http://www.w3.org/ns/csvw",
                            "@id": codelist_uri,
                            "url": column["codelist_filename"],
                            "dcterms:title": column.get("codelist_title"),
                            "dcterms:description": column.get("codelist_description"),
                            "tableSchema": {
                                # I make strong assumptions here about the format of the local codelist csv. These 
                                # should be loosened.
                                "columns": [
                                    {
                                        "titles": "Label",
                                        "name": "label",
                                        "datatype": "string",
                                        "required": True,
                                        "propertyUrl": "rdfs:label"
                                    },
                                    {
                                        "titles": "Notation",
                                        "name": "notation",
                                        "datatype": {
                                            "base": "string",
                                            "format": "^-?[\\w\\.\\/\\+]+(-[\\w\\.\\/\\+]+)*$"
                                        },
                                        "required": True,
                                        "propertyUrl": "skos:notation"
                                    },
                                    {
                                        "titles": "Parent Notation",
                                        "name": "parent_notation",
                                        "datatype": {
                                            "base": "string",
                                            "format": "^(-?[\\w\\.\\/\\+]+(-[\\w\\.\\/\\+]+)*|)$"
                                        },
                                        "required": False,
                                        "propertyUrl": "skos:broader",
                                        "valueUrl": re.sub("{.*?}", "{parent_notation}", value_uri)
                                    },
                                    {
                                        "titles": "Sort Priority",
                                        "name": "sort",
                                        "datatype": "integer",
                                        "required": False,
                                        "propertyUrl": "http://www.w3.org/ns/ui#sortPriority"
                                    },
                                    {
                                        "titles": "Description",
                                        "name": "description",
                                        "datatype": "string",
                                        "required": False,
                                        "propertyUrl": "rdfs:comment"
                                    },
                                    {
                                        "virtual": True,
                                        "propertyUrl": "rdf:type",
                                        "valueUrl": "skos:Concept"
                                    },
                                    {
                                        "virtual": True,
                                        "propertyUrl": "skos:inScheme",
                                        "valueUrl": codelist_uri
                                    }
                                ],
                                "primaryKey": [
                                    "notation",
                                    "parent_notation"
                                ],
                                "aboutUrl": re.sub("{.*?}", "{notation}", value_uri)
                            },
                            "prov:hadDerivation": {
                                "@id": codelist_uri,
                                "@type": "skos:ConceptScheme"
                            }
                        }
                    )

                #-------------------------------------------------------------------------------------------------------

                self._components.append(
                    DimensionComponent(
                        at_id=URI(make_local_component_uri(column.get('name'))),
                        qb_componentProperty=Resource(
                            at_id=URI(dimension_uri)),
                        qb_dimension=DimensionProperty(
                            at_id=URI(dimension_uri),
                            qb_codeList=ConceptScheme(
                                at_id=URI(codelist_uri),
                                rdfs_label=column.get("codelist_title"),
                                rdfs_comment=column.get("codelist_description"),
                            ) if codelist_uri else None,
                            # Note that the current implementation sets the range to #class/Name
                            # make_local_class_uri(column.get('name')) coins a URI in that form
                            rdfs_range=Resource(
                                at_id=URI(dimension_range)
                            ),
                            rdfs_label=column.get("title"),
                            rdfs_comment=column.get("description"),
                            rdfs_subPropertyOf=URI(column.get("parent_uri")),
                            rdfs_isDefinedBy=URI(column.get("defined_by"))
                        )
                    )
                )

                # If component_uri is not specified then use the coined default dimension URI
                if not column.get("component_uri"):
                    self._columns[column["name"]] = self._columns[column["name"]]._replace(propertyUrl=URI(dimension_uri))
                # If a value_uri is not set then default behaviour is to treat each cell entry as a typed literal,
                # but if a default codelist is created, then default URIs should be created for each cell entry also
                # and if a codelist_uri is specified then value_uri must be set.
                # We make an assumption that if a codelist_uri is specified, a value_uri will be also.
                if not column.get("value_uri") and column.get('codelist_uri'):
                    raise ValueError(f"{column['name']} has a codelist_uri specified but no value_uri specified.")
                if not column.get("value_uri") and (column.get('codelist_filename') and not column.get('codelist_uri')):
                    value_uri = make_local_concept_uri(column.get('name'))
                    self._columns[column["name"]] = self._columns[column["name"]]._replace(valueUrl=URI(value_uri))

            # MEASURES -------------------------------------------------------------------------------------------------

            elif column["component_type"] == "measure":
                # If component_uri is specified, use that - failing that, coin a measure URI
                measure_uri = column.get("component_uri", make_local_measure_uri(column.get('name')))

                self._components.extend([
                    DimensionComponent(
                        at_id=URI(make_local_component_uri("measure-type")),
                        qb_componentProperty=Resource(at_id=URI("http://purl.org/linked-data/cube#measureType")),
                        qb_dimension=DimensionProperty(
                            at_id=URI("http://purl.org/linked-data/cube#measureType"),
                            rdfs_range=Resource(at_id=URI("http://purl.org/linked-data/cube#MeasureProperty"))
                        )
                    ),
                    MeasureComponent(
                        at_id=URI(make_local_component_uri(column.get('name'))),
                        qb_componentProperty=Resource(at_id=URI(measure_uri)),
                        qb_measure=MeasureProperty(
                            at_id=URI(measure_uri),
                            # Range of the measure is an xsd datatype - default is xsd:decimal
                            rdfs_range=Resource(
                                at_id=URI(f"http://www.w3.org/2001/XMLSchema#{column.get('datatype', 'decimal')}")
                            ),
                            # Added in additional rdfs stuff which would have been defined in ref_common previously
                            rdfs_label=column.get("title"),
                            rdfs_comment=column.get("description"),
                            rdfs_subPropertyOf=URI(column.get("parent_uri")),
                            rdfs_isDefinedBy=URI(column.get("defined_by"))
                        )
                    )
                ])

                # If component_uri is not specified then use the coined default measure URI
                if not column.get("component_uri"):
                    self._columns[column["name"]] = self._columns[column["name"]]._replace(propertyUrl=URI(measure_uri))
                if not column.get("datatype"):
                    self._columns[column["name"]] = self._columns[column["name"]]._replace(
                        datatype=URI('http://www.w3.org/2001/XMLSchema#decimal')
                    )

                self._columns["virtual_measure"] = Column(
                    name="virtual_measure",
                    virtual=True,
                    propertyUrl=URI("http://purl.org/linked-data/cube#measureType"),
                    valueUrl=URI(measure_uri)
                )
                # If units are specified add as an attribute
                if column.get("units_uri"):
                    self._components.append(   
                        AttributeComponent(
                            at_id=URI(make_local_component_uri("unit")),
                            qb_componentProperty=Resource(
                                at_id=URI("http://purl.org/linked-data/sdmx/2009/attribute#unitMeasure")
                            ),
                            qb_attribute=AttributeProperty(
                                at_id=URI("http://purl.org/linked-data/sdmx/2009/attribute#unitMeasure")
                            )
                        )
                    )
                    self._columns["virtual_unit"] = Column(
                        name="virtual_unit",
                        virtual=True,
                        propertyUrl=URI("http://purl.org/linked-data/sdmx/2009/attribute#unitMeasure"),
                        valueUrl=URI(column.get("units_uri"))
                    )

            # ATTRIBUTES -----------------------------------------------------------------------------------------------

            elif column["component_type"] == "attribute":
                self._components.append(
                    AttributeComponent(
                        at_id=URI(make_local_component_uri(column.get('name'))),
                        qb_componentProperty=Resource(at_id=URI(column.get("component_uri"))),
                        qb_attribute=AttributeProperty(
                            at_id=URI(column.get("component_uri")),
                            rdfs_range=Resource(
                                at_id=URI("http://www.w3.org/2000/01/rdf-schema#Class")
                            )
                        )
                    )
                )
                self._columns[column["name"]] = self._columns[column["name"]]._replace(
                    propertyUrl=URI(column.get("component_uri")),
                    valueUrl=URI(column.get("value_uri"))
                )
        
        # VIRTUAL COLUMNS ----------------------------------------------------------------------------------------------

        self._columns["virtual_dataset"] = Column(
            name="virtual_dataset",
            virtual=True,
            propertyUrl=URI("http://purl.org/linked-data/cube#dataSet"),
            valueUrl=URI(make_dataset_contents_uri())
        )
        self._columns["virtual_type"] = Column(
            name="virtual_type",
            virtual=True,
            propertyUrl=URI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
            valueUrl=URI("http://purl.org/linked-data/cube#Observation")
        )

        table_uri = URI(self._specification["csv_filename"])
        # if self._metadata_filename is not None:
        #     table_uri = URI(self._csv_filename.relative_to(self._metadata_filename.parent))

        # Additional changes could be made here to include dataset metadata such as the dataset title/description.

        # It is a requirement that virtual columns are at the end of the metadata file, so we reorder.
        columns = list(self._columns.values())
        columns.sort(key=lambda x: x.virtual is True)

        main_table = Table(
            url=table_uri,
            tableSchema=TableSchema(
                columns=columns,
                primaryKey=self._keys,
                aboutUrl=URI(make_observation_uri(self._keys)),
                foreignKeys=self._foreign_keys
            )
        )

        self._validate()

        self._map = {
            "@context": ["http://www.w3.org/ns/csvw", {"@language": "en"}],
            "tables": [main_table] + self._external_tables,
            "@id": make_tables_uri(),
            "prov:hadDerivation": DataSet(
                at_id=make_dataset_contents_uri(),
                dcterms_title=spec.get("title"),
                dcterms_description=spec.get("description"),
                dcterms_publisher=spec.get("publisher"),
                dcterms_issued=spec.get("published"),
                dcterms_modified=spec.get("modified"),
                dcat_landingPage=spec.get("landing_page"),
                qb_structure=DSD(
                    at_id=make_dataset_definition_uri(),
                    qb_component=self._components
                )
            )
        }

    def _validate(self):
        # Check variable names are consistent
        declared_names = set([col.name for col in self._columns.values()])
        used_names: Set[str] = set()
        for name_set in (
            variables(uri)
            for column in self._columns.values()
            for uri in [column.propertyUrl, column.valueUrl]
            if uri is not None
        ):
            used_names.update(name_set)
        if not declared_names.issuperset(used_names):
            logging.error(f"Unmatched variable names: {used_names.difference(declared_names)}")
        # Check used prefixes
        used_prefixes = set(
            t.split(':')[0]
            for column in self._columns.values()
            for t in [column.propertyUrl, column.valueUrl]
            if t is not None and not t.startswith('http') and ':' in t
        )
        if not set(prefix_map.keys()).issuperset(used_prefixes):
            logging.error(f"Unknown prefixes used: {used_prefixes.difference(prefix_map.keys())}")

    def _as_plain_object(self):

        def fix_prefix(key: str):
            for prefix, replace in {
                    'at_': '@', 'qb_': 'qb:', 'rdfs_': 'rdfs:', 'dcterms_': 'dcterms:', 'dcat_': 'dcat:'
                }.items():
                if key.startswith(prefix):
                    return replace + key[len(prefix):]
            return key

        def unpack(o):
            if isinstance(o, tuple):
                try:
                    return {fix_prefix(k): unpack(v) for (k, v) in dict(o._asdict()).items() if v is not None}
                except AttributeError:
                    return o
            elif isinstance(o, dict):
                return {k: unpack(v) for (k, v) in o.items()}
            elif isinstance(o, Path):
                return str(o)
            elif isinstance(o, list):
                return [unpack(i) for i in o]
            else:
                return o

        return(unpack(self._map))

    def write(self, out: Union[URI, TextIO]):
        if not isinstance(out, TextIOBase):
            # self._metadata_filename = out
            stream = open(out, "w", encoding="utf-8")
        else:
            stream = out
        plain_obj = self._as_plain_object()
        logging.debug(json.dumps(plain_obj, indent=2))
        json.dump(plain_obj, stream, indent=2)

