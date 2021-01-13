import sys
sys.path.append("../../csvw")

from mapping import CSVWMapping

test = CSVWMapping()
test.process_specification("./info.json")
test.write("./out/life-expectancy.csv-metadata.json")

# Then on the command line:
# csvname="example"
# docker run -v $PWD:/workspace -w /workspace -it gsscogs/csv2rdf \
# csv2rdf -t out/$csvname.csv -u out/$csvname.csv-metadata.json -m annotated -o out/$csvname.ttl