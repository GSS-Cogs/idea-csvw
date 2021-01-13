A dimension has entries like "Cardiff", "Newport", "Merthyr Tydfil".

No codelist.

A codelist but;
- No concept scheme URI specified.
- No value URI is specified.
- The user has a .csv for the codelist containing columns "Notation, Label, Description, Parent"

A codelist but;
- A concept scheme URI is specified.
- A value URI is specified.
- The user has a .csv for the codelist containing columns "Notation, Label, Description, Parent"

A codelist but;
- A concept scheme URI is specified.
- A value URI is specified.
- The user does not have a csv of the codelist (they are using external reference data).



```json
        {
            "title": "Region",            
            "name": "region",             
            "component_type": "dimension",
            "component_uri": "x",
            "value_uri": "x",
            "datatype": "string",

            "codelist_uri": "reference.data.gov.uk/concept-scheme/something",
            "codelist_filename": "something.csv",
        }
```

codelist: some.csv
codelist_uri not specified or specified - if not specified and filename is, then default.
