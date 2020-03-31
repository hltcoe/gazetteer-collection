"""
Writes names and optionally aliases for each wikidata qid for each
language of interest in the list qids for scale class type.  Gets them
in groups of size batch until on files or we've processed
max_batches batches.

USAGE: python get_ent_names.py --ids Q5 -type PER -batchsize 40000 --batches 3 --nosubtypes

"""

import argparse as ap
import subprocess
from timeit import default_timer as timer
from SPARQLWrapper import SPARQLWrapper, JSON


def get_args():
    """Get command line arguments"""
    pargs = ap.ArgumentParser(description=DESCRIPTION, epilog=USAGE_EXAMPLE)
    pargs.add_argument('-ids', '--ids', nargs='+', required=True, \
                       help='Wikidata IDs for concepts, e.g., Q1248784')
    pargs.add_argument('-langs', '--langs', nargs='+', default=['en', 'ru', 'zh'],\
                    help='2 letter language codes (e.g., en ru')
    pargs.add_argument('-type', '--type', help='scale type (e.g., ORG)')
    pargs.add_argument('-batchsize', '--batchsize', nargs='?', type=int, \
                    default=50000, help='number in each batch')
    pargs.add_argument('-batches', '--batches', type=int, default=10, \
                    help='maximum number of batch to get')
    pargs.add_argument('-nosubtypes', '--nosubtypes', \
                    action='store_true', help='immediate type only')
    pargs.add_argument('-nonames', '--nonames',\
                    action='store_true', help='do not get names')
    pargs.add_argument('-concepts', '--concepts', \
                    action='store_true', help='get subclasses, no instances')
    pargs.add_argument('-noaliases', '--noaliases',\
                    action='store_true', help='do not get aliases')
    pargs.add_argument('-nowiki', '--norequirewiki', 
                    action='store_true', help='do not require the entity to have a wikipedia page in the language')
    pargs.add_argument('-c', '--country', nargs="?", default=False, help='required country QID')

    return pargs.parse_args()

DESCRIPTION = "writes names and optionally aliases for each wikidata qid for \
each language of interest in the list qids for scale class type.  Gets them \
in groups of size batch until on files or we've processed max_batches batches."

USAGE_EXAMPLE = "  Example: python get_ent_names.py --ids Q5 -type PER \
-batchsize 40000 --batches 3 --nosubtypes"

# maps two-letter language code (zh) to a three-letter code (cmn)
LANG3 = {'en':'eng', 'ru':'rus', 'zh':'cmn'}

# maps Wikidata name/alias relation to short form
REL2NAME = {'rdfs:label':'name', 'skos:altLabel':'alias'}

# user agent for http request (required by wikidata query service)
USER_AGENT = "Gazbot/1.0 (Tim Finin)"

# queries are designed to be efficient so that we can retrieve as many hits as possible with the public server

# query parameters available
# REL: 'rdfs:label' for names  or 'skos:altLabel' for alias
# SUB: check subclasses?
# WIKI: If True, require that the entity has a wikipedia page
# CTY: code for an associated country
# LANG: 2-letter code for the language

QUERY_GENERAL_TERMS = """SELECT DISTINCT ?n {{wd:{CLASS} ^wdt:P279+ ?x. ?x {REL} ?n FILTER(lang(?n) = "{LANG}")}} OFFSET {OFF} LIMIT {LIM}"""

QUERY_TEMPLATE_NOSUB_NOWIKI_CTY = """SELECT DISTINCT ?n {{wd:{CLASS} ^wdt:P31 ?x. ?x wdt:P17 wd:{CTY}; {REL} ?n FILTER(lang(?n) = "{LANG}")}} OFFSET {OFF} LIMIT {LIM}"""
QUERY_TEMPLATE_NOSUB_WIKI_CTY = """SELECT ?n {{ wd:{CLASS} ^wdt:P31 ?x; wdt:P17 wd:{CTY}.  ?name {REL} ?n. FILTER(lang(?n) = "{LANG}") ?wiki schema:about ?name; schema:isPartOf <https://{LANG}.wikipedia.org/>.}} OFFSET {OFF} LIMIT {LIM}"""
QUERY_TEMPLATE_SUB_NOWIKI_CTY = """SELECT DISTINCT ?n {{wd:{CLASS} ^wdt:P279*/^wdt:P31 ?x. ?x wdt:P17 wd:{CTY}; {REL} ?n FILTER(lang(?n) = "{LANG}")}} OFFSET {OFF} LIMIT {LIM}"""
QUERY_TEMPLATE_SUB_WIKI_CTY = """SELECT ?n {{ wd:{CLASS} ^wdt:P279*/^wdt:P31 ?x. ?x wdt:P17 wd:{CTY}; {REL} ?n. FILTER(lang(?n) = "{LANG}") ?wiki schema:about ?name; schema:isPartOf <https://{LANG}.wikipedia.org/>.}} OFFSET {OFF} LIMIT {LIM}"""

QUERY_TEMPLATE_NOSUB_NOWIKI_NOCTY =  """SELECT DISTINCT ?n {{wd:{CLASS} ^wdt:P31/{REL} ?n FILTER(lang(?n) = "{LANG}")}} OFFSET {OFF} LIMIT {LIM}"""
QUERY_TEMPLATE_NOSUB_WIKI_NOCTY = """SELECT ?n {{ wd:{CLASS} ^wdt:P31 ?name.  ?name {REL} ?n. FILTER(lang(?n) =  "{LANG}") ?wiki schema:about ?name; schema:isPartOf <https://{LANG}.wikipedia.org/>.}} OFFSET {OFF} LIMIT {LIM}"""
QUERY_TEMPLATE_SUB_NOWIKI_NOCTY = """SELECT DISTINCT ?n {{wd:{CLASS} ^wdt:P279*/^wdt:P31/{REL} ?n FILTER(lang(?n) = "{LANG}")}} OFFSET {OFF} LIMIT {LIM}"""
QUERY_TEMPLATE_SUB_WIKI_NOCTY = """SELECT ?n {{ wd:{CLASS} ^wdt:P279*/^wdt:P31 ?name.  ?name {REL} ?n. FILTER(lang(?n) =  "{LANG}") ?wiki schema:about ?name; schema:isPartOf <https://{LANG}.wikipedia.org/>.}} OFFSET {OFF} LIMIT {LIM}"""

QUERIES = {
    (True,True,True):QUERY_TEMPLATE_SUB_WIKI_CTY,
    (True,True,False):QUERY_TEMPLATE_SUB_WIKI_NOCTY,
    (True,False,True):QUERY_TEMPLATE_SUB_NOWIKI_CTY,
    (True,False,False):QUERY_TEMPLATE_SUB_NOWIKI_NOCTY,
    (False,True,True):QUERY_TEMPLATE_NOSUB_WIKI_CTY,
    (False,True,False):QUERY_TEMPLATE_NOSUB_WIKI_NOCTY,
    (False,False,True):QUERY_TEMPLATE_NOSUB_NOWIKI_CTY,
    (False,False,False):QUERY_TEMPLATE_NOSUB_NOWIKI_NOCTY  }


DEFAULT_ENDPOINT = "https://query.wikidata.org/sparql"

def ask_wikidata(query, form=JSON, endpoint=DEFAULT_ENDPOINT):
    """Send query to endpoint, get results as json and return
       corresponding dict.  If an error occurs return -1 if we did not
        get a response and -2 if the conversion to a dict fails 
    """
    sparql = SPARQLWrapper(endpoint, agent=USER_AGENT)
    sparql.setQuery(query)
    sparql.setReturnFormat(form)
    # get query result
    try:
        result = sparql.query()
    except Exception as ex:
        print('  Query failed', ex)
        return -2
    # convert it
    try:
        return  result.convert()
    except Exception as ex:
        print('  Bad json', ex)
        return -1

def get_instance_names(wdclass, out, lang, rel, offset, limit, nosubtypes, require_wiki, country):
    """ returns a count of the number found or -1 or -2 for errors """
    key = (not(nosubtypes), require_wiki, not(not(country)))
    q = QUERIES[key]
    query = q.format(CLASS=wdclass, REL=rel, LANG=lang, OFF=offset, LIM=limit, CTY=country)
    count = 0
    data = ask_wikidata(query, form=JSON)
    if data in [-2, -1]:
        return data
    for result in data['results']['bindings']:
        count += 1
        out.write(result['n']['value'])
        out.write('\n')
    return count

def get_concept_names(wdclass, out, lang, rel, offset, limit):
    """ returns a count of the number found or -1 or -2 for errors
        We recognize a concept by the test that it is not an instance
        of a another item unless that item is a first-order metaclass.
    """
    q = QUERY_GENERAL_TERMS
    query = q.format(CLASS=wdclass, REL=rel, LANG=lang, OFF=offset, LIM=limit)
    count = 0
    data = ask_wikidata(query, form=JSON)
    if data in [-2, -1]:
        return data
    for result in data['results']['bindings']:
        count += 1
        out.write(result['n']['value'])
        out.write('\n')
    return count


def get_names_langs(qids, s_type, langs, batch_size=50000, max_batches=20, nosubtypes=True, concepts=False, nonames=False, noaliases=False, require_wiki=True, country=None):
    """ writes names and optionally aliases for each wikidata qid for
    each language of interest in the list qids for scale class s_type.
    Gets them in groups of size batch_size until on files or we've
    processed max_batches batches. """
    # qids can like Q5:human or just Q5, ignoring any that don't begin with a Q
    qids = [id.partition(':') for id in qids if id.startswith('Q')]
    rels = []
    if not nonames:
        rels.append('rdfs:label')
    if not noaliases:
        rels.append('skos:altLabel')
    for lang in langs:
        for rel in rels:
            file_name = "{}-{}-{}-wd.txt".format(LANG3[lang], s_type, REL2NAME[rel])
            with open(file_name, 'w', encoding="UTF-8") as out:
                for qid, _, qname in qids:
                    for i in range(max_batches):
                        try:
                            print('Getting batch {} for {} ({}) in language {} using {}'.format(i+1, qid, qname, lang, rel))
                            starttime = timer()
                            if concepts:
                                number_found = get_concept_names(qid, out, lang, rel, i*batch_size, batch_size)
                            else:
                                number_found = get_instance_names(qid, out, lang, rel, i*batch_size, batch_size, nosubtypes, require_wiki, country)
                            print('  Found', number_found, 'in', timer()-starttime, 'sec.')
                            if number_found == -2:
                                print(" hard failure, bailing")
                                break
                            elif number_found == -1:
                                print("  soft failure, bailing")
                                break
                            elif number_found < batch_size:
                                print("  no more results after this")
                                break
                        except Exception as ex:
                            print('  Failed:', i, timer()-starttime)
                            print(' ', ex)
                            break
            print('Sorting and removing duplicates')
            try:
                subprocess.run(["sort", "-u", "-o", file_name, file_name], check=True)
            except Exception as ex:
                print(  'sorting failed:', ex)
                

def main(args):
    """ if invoked from command line """
    get_names_langs(args.ids, args.type, args.langs, args.batchsize, args.batches, args.nosubtypes, args.concepts, args.nonames, args.noaliases, not(args.norequirewiki), args.country)

if __name__ == '__main__':
    main(get_args())




