from collections import defaultdict

def process_file(fname):
    name_count = 0
    name_chars = defaultdict(int)
    name_tokens = defaultdict(int)
    for open(fname) as infile:
        for name in (infile):
            name = name.strip()
            name_count += 1
            name_chars[len(name)] +=1
            name_tokens[len(name.split(' '))]
    return count name_chars name_tokens

            
