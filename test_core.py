import io
import sqlite3
import unittest
import zipfile

from core import connect, hvac_rows, infobox_facts, place_tokens, vet_matches, wiki_link, xlsx_rows


class SourceImportTests(unittest.TestCase):
    def test_spreadsheet_reader_keeps_blank_cells_and_dates_aligned(self):
        xml = b'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
          <sheetData><row r="1"><c r="A1" t="str"><v>Practice Name</v></c></row>
          <row r="2"><c r="A2" t="str"><v>Creekside Animal Hospital</v></c>
          <c r="C2" t="str"><v>Macomb</v></c><c r="D2" t="str"><v>MI</v></c>
          <c r="L2" t="n"><v>46022</v></c></row></sheetData></worksheet>'''
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('xl/worksheets/sheet1.xml', xml)
        row = list(xlsx_rows(buffer.getvalue()))[0]
        self.assertEqual((row[0], row[1], row[2], row[3]),
                         ('Creekside Animal Hospital', '', 'Macomb', 'MI'))
        self.assertEqual(row[11], '2025-12-31')

    def test_csv_reader_handles_comment_header_and_quoted_name(self):
        payload = b'# export caveat\nslug,target,sponsor\na,"Davis Heating, Cooling & Air",Investor\n'
        self.assertEqual(list(hvac_rows(payload))[0]['target'], 'Davis Heating, Cooling & Air')


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(':memory:')
        self.db.executemany('''INSERT INTO vet_practices
            (name,name_key,city,state,investor) VALUES (?,?,?,?,?)''', [
            ('Creekside Animal Hospital', 'creekside animal hospital', 'Macomb', 'MI', 'Unknown'),
            ('Creekside Animal Hospital', 'creekside animal hospital', 'West Lafayette', 'IN', 'Sponsor')
        ])

    def tearDown(self):
        self.db.close()

    def test_location_prevents_same_name_false_positive(self):
        self.assertEqual(len(vet_matches(self.db, 'Creekside Animal Hospital')), 2)
        result = vet_matches(self.db, 'Creekside Animal Hospital', 'Macomb, Michigan')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['investor'], 'Unknown')
        self.assertEqual(vet_matches(self.db, 'Creekside Animal Hospital', 'Texas'), [])

    def test_state_name_and_abbreviation_are_equivalent(self):
        self.assertEqual(place_tokens('Clinton Township, Michigan'), ['clinton', 'township', 'mi'])
        self.assertEqual(place_tokens('Clinton Township, MI'), ['clinton', 'township', 'mi'])


class NationalChainTests(unittest.TestCase):
    def test_nested_infobox_does_not_hide_later_parent(self):
        text = '''{{Infobox company
| name = Jersey Mike's Subs
| areas_served = {{plainlist|
* United States
* Canada
}}
| traded_as = {{NYSE|JMKE}}
| parent = [[Blackstone Inc.|Blackstone]]
}}'''
        facts = infobox_facts(text)
        self.assertEqual(wiki_link(facts['parent']), 'Blackstone Inc.')
        self.assertIn('JMKE', facts['traded_as'])


if __name__ == '__main__':
    unittest.main()
