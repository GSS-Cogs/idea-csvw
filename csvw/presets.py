
# Year

Column(
    name=namify(column.get("name")),
    titles=[column.get("title")],
    datatype=column.get("datatype"),
    propertyUrl="http://purl.org/linked-data/sdmx/2009/dimension#refPeriod",
    valueUrl="http://reference.data.gov.uk/id/year/{{{namify(column.get('name'))}}}"
)
