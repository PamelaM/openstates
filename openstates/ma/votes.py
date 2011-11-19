import lxml.etree
import os

from billy.scrape.votes import VoteScraper, Vote
from billy.scrape.utils import pdf_to_lxml
import scrapelib

class MAVoteScraper(VoteScraper):

    state = 'ma'
    roll_call_url_format = 'http://www.mass.gov/legis/journal/RollCallPdfs/%(session)s/%(idx)05d.pdf'

    def scrape(self, chamber, session):
        session = session.replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
        # Loop through the roll call pdfs until #MISSING_STREAK_CUTOFF consecutive urls aren't present
        MISSING_STREAK_CUTOFF = 2
        total_missing = 0
        num_missing_streak = 0
        idx = 1
        while True:
            if not self.scrape_roll_call(chamber, session, idx):
                total_missing += 1
                num_missing_streak += 1
            else:
                num_missing_streak = 0
            
            if num_missing_streak>MISSING_STREAK_CUTOFF:
                break
            
            idx += 1
                

    def scrape_roll_call(self, chamber, session, idx):
        url = self.roll_call_url_format % locals()
        try:
            filename, response = self.urlretrieve(url)
        except scrapelib.HTTPError:
            return False
            
        try:
            xml = pdf_to_lxml(filename)
        finally:
            os.remove(filename)
        
        print lxml.etree.tostring(xml, pretty_print=True)
        return True

    def scrape_chamber_votes(self, chamber, session, url):
        try:
            xml = self.urlopen(url)
        except scrapelib.HTTPError, e:
            if str(e).startswith("404 "):
                return None
                
        doc = lxml.etree.fromstring(xml)

        for vxml in doc.xpath('//vote'):
            legislation = vxml.get('legislation')
            motion = vxml.get('caption')
            timestamp = datetime.datetime.strptime(vxml.get('dateTime'),
                                                   '%Y-%m-%dT%H:%M:%S')

            leg_prefix = legislation.split(' ')[0]
            if leg_prefix in ('SB', 'SR'):
                bill_chamber = 'upper'
            elif leg_prefix in ('HB', 'HR'):
                bill_chamber = 'lower'
            elif leg_prefix in ('', 'EX', 'ELECTION'):
                continue
            else:
                raise Exception('unknown legislation prefix: ' + legislation)
            # skip bills from other chamber
            if bill_chamber != chamber:
                continue

            unknown_count = int(vxml.xpath('totals/@unknown')[0])
            excused_count = int(vxml.xpath('totals/@excused')[0])
            nv_count = int(vxml.xpath('totals/@not-voting')[0])
            no_count = int(vxml.xpath('totals/@nays')[0])
            yes_count = int(vxml.xpath('totals/@yeas')[0])
            other_count = unknown_count + excused_count + nv_count

            vote = Vote(chamber, timestamp, motion,
                        passed=yes_count > no_count, yes_count=yes_count,
                        no_count=no_count, other_count=other_count,
                        session=session, bill_id=legislation,
                        bill_chamber=bill_chamber)
            vote.add_source(url)

            for m in vxml.xpath('member'):
                vote_letter = m.get('vote')
                member = m.get('name')
                if vote_letter == 'Y':
                    vote.yes(member)
                elif vote_letter == 'N':
                    vote.no(member)
                else:
                    vote.other(member)

            self.save_vote(vote)