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
            r'^[\s]*([a-zA-Z][\w]*)[\s]*\:[\s]*([\w\s\/\(\)\-]+)[\s]*',
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

        return eemAttr
