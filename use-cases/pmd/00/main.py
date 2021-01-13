import sys
sys.path.append("../../../pmd")

from pmd_metadata import PMDMetadata

test = PMDMetadata()
test.process_specification("./info.json")
test.serialize("./out/life-expectancy.trig")

# Then on the command line:
# csvname="example"
# docker run -v $PWD:/workspace -w /workspace -it gsscogs/csv2rdf \
# csv2rdf -t out/$csvname.csv -u out/$csvname.csv-metadata.json -m annotated -o out/$csvname.ttl