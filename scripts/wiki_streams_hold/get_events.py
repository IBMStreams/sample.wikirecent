import json
from sseclient import SSEClient as EventSource
def get_events():
    """fetch rgetecent changes from wikievents site using SSE"""
    for change in EventSource('https://stream.wikimedia.org/v2/stream/recentchange'):
        if len(change.data):
            try:
                obj = json.loads(change.data)
            except json.JSONDecodeError as err:
                print("JSON l1 error:", err, "Invalid JSON:", change.data)
            except json.decoder.JSONDecodeError as err:
                print("JSON l2 error:", err, "Invalid JSON:", change.data)
            else:
                yield(obj)


class sum_aggregation():
    def __init__(self, sum_map={'new_len': 'newSum', 'old_len': 'oldSum', 'delta_len': 'deltaSum'}):
        """
        Summation of column(s) over a window's tuples.
        Args::
            sum_map :  specfify tuple columns to be summed and the result field.
            tuples : at run time, list of tuples will flow in. Sum each fields
        """
        self.sum_map = sum_map

    def __call__(self, tuples) -> dict:
        """
        Args:
            tuples : list of tuples constituting a window, over all the tuples sum using the sum_map key/value
                     to specify the input and result field.
        Returns:
            dictionary of fields summations over tuples

        """
        summaries = dict()
        for summary_field, result_field in self.sum_map.items():
            summation = sum([ele[summary_field] for ele in tuples])
            summaries.update({result_field: summation})
        return (summaries)

import collections
class tally_fields(object):
    def __init__(self, top_count=3, fields=['user', 'wiki', 'title']):
        """
        Tally fields of a list of tuples.
        Args::
            fields :  fields of tuples that are to be tallied
        """
        self.fields = fields
        self.top_count = top_count
    def __call__(self, tuples)->dict:
        """
        Args::
            tuples : list of tuples tallying to perform.
        return::
            dict of tallies
        """
        tallies = dict()
        for field in self.fields:
            stage = [tuple[field] for tuple in tuples if tuple[field] is not None]
            tallies[field] = collections.Counter(stage).most_common(self.top_count)
        return tallies


class wiki_lang():
    """
    Augment the tuple to include language wiki event.

    Mapping is loaded at build time and utilized at runtime.
    """

    def __init__(self, fname="wikimap.csv"):
        self.wiki_map = dict()
        with open(fname, mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                self.wiki_map[row['dbname']] = row

    def __call__(self, tuple):
        """using 'wiki' field to look pages code, langauge and native
        Args:
            tuple: tuple (dict) with a 'wiki' fields
        Returns:'
            input tuple with  'code', 'language, 'native' fields added to the input tuple.
        """
        if tuple['wiki'] in self.wiki_map:
            key = tuple['wiki']
            tuple['code'] = self.wiki_map[key]['code']
            tuple['language'] = self.wiki_map[key]['in_english']
            tuple['native'] = self.wiki_map[key]['name_language']
        else:
            tuple['code'] = tuple['language'] = tuple['native'] = None
        return tuple