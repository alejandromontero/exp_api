import re


'''
EEM parser to Python dictorionary.
Does not matter the attributes.
'''


class eemParser(object):
    @staticmethod
    def parse(doc):
        eemAttr = {}
        pattern = re.compile(
            r'([a-zA-Z][\w]*)[\s]*\:[\s]*([\w\s\/\(\)\-]+)[\s]*[\n]',
            re.M)
        entries = pattern.findall(doc)
        for entry in entries:
            eemAttr[entry[0]] = entry[1]

        # Parse entries with lists
        pattern = re.compile(
                r'^[\s]*([a-z][a-z0-9_]*)[\s]*[\:][\s]*(\[.*\])[\s]*',
                re.M)
        entries = pattern.findall(doc)
        for entry in entries:
            eemAttr[entry[0]] = []
            pattern2 = re.compile(
                    r'([\w]*[\']*[\w]*[\']*)\,',
                    re.M)
            pattern3 = re.compile(
                    r'([\w]*[\']*[\w]*[\']*)\]',
                    re.M)
            entries2 = pattern2.findall(entry[1])
            entries3 = pattern3.findall(entry[1])
            for entry2 in entries2:
                eemAttr[entry[0]].append(entry2)
            for entry3 in entries3:
                eemAttr[entry[0]].append(entry3)

        # Mac address special case
        pattern = re.compile(
                r'^(mac_address)[\s]*\:[\s]*(([a-fA-F0-9]{2}[:|\-]?){6})',
                re.M)
        entries = pattern.findall(doc)
        for entry in entries:
            eemAttr[entry[0]] = entry[1]

        # Downstream ports special case (artificial list)
        if re.search(r'downstream_ports', doc):
            pattern = re.compile(
                    r'(downstream_port_id)[\s]*\:[\s]*([0-9]+)[\n][\s]*([\w]*)[\s]*\:[\s](up)[\n][\s]*([\w]*)[\s]*\:[\s]*(([a-fA-F0-9]{2}[:|\-]?){6})',
                    re.M)
            entries = pattern.findall(doc)
            if entries:
                eemAttr["downstream_port"] = {}
                entry = entries[0]  # There should only be one port up
                for x in range(0, len(entry) - 1, 2):
                    eemAttr["downstream_port"][entry[x + 0]] = entry[x + 1]
            else:
                eemAttr["downstream_port"] = "All down"
        return eemAttr
