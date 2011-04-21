# We Are Forests
# http://weareforests.com/
#
# a project by Duncan Speakman and Emilie Grenier
# -----------------------------------------------
#
# supported by Nederlands Instituut voor de Mediakunst - http://www.nimk.nl/
#
# Source code (c) 2011 Arjan Scherpenisse <arjan@scherpenisse.net>
# This code is released under the MIT license. See LICENSE for details.

import os

from twisted.internet import reactor, defer, task
from twisted.python import log
from epsilon.extime import Time
from datetime import timedelta

from sparked import application

from starpy import fastagi, manager

from axiom.store import Store
from axiom.attributes import AND

from weareforests import telephony, web
from weareforests.telephony import Recording


EXTEN_AGI_DIALOUT = '501'
EXTEN_AGI = '502'
EXTEN_CONFERENCE = '503'


class Application (application.Application, web.WebMixIn):

    useRecordingsInEnding = False


    def started(self):

        # database handling
        self.store = Store(self.path("db").child("storage").path)

        # the recordings path
        self.recordingsPath = self.path("db").child("recordings")
        if not self.recordingsPath.exists(): self.recordingsPath.createDirectory()

        # start AGI service
        f = fastagi.FastAGIFactory(self.connected)
        reactor.listenTCP( 4573, f, 50, '127.0.0.1')

        # start web server
        web.WebMixIn.started(self)

        f = manager.AMIFactory('admin', 'admin')
        def r(proto):
            self.admin = proto
            self.admin.registerEvent("ConferenceDTMF", self.conferenceDTMF)
            self.admin.registerEvent("ConferenceJoin", self.conferenceJoin)
            self.admin.registerEvent("ConferenceLeave", self.conferenceLeave)
        f.login("127.0.0.1", 5038).addCallback(r)

        self.sessions = {}


    def enter_start(self):
        self.state.set("normal")
        for session in self.sessions.values():
            session.state.set("to_start")
            self.redirect(session, EXTEN_AGI)


    def enter_normal(self):
        self.webio.sendAll({'event': "state-change", 'state': 'normal'})


    def enter_ending(self):
        self.webio.sendAll({'event': "state-change", 'state': 'ending'})
        # transfer all sessions to the ending AGI
        for session in self.sessions.values():
            session.state.set("to_ending")
            self.redirect(session, EXTEN_AGI)


    def connected(self, agi):
        channel = agi.variables['agi_channel']
        if channel not in self.sessions:
            # new session
            session = telephony.CallerSession(self, agi)
            self.webio.sendAll({'event': 'message', 'title': 'New caller', 'text': 'Caller id: %s' % session.callerId})
            self.sessions[session.channel] = session
        else:
            # re-entry from conference
            self.sessions[channel].reEntry(agi)
        self.pingWebSessions()


    def sessionEnded(self, channel):
        print 'session ended', channel
        self.webio.sendAll({'event': 'message', 'title': 'Caller disconnected', 'text': 'Caller id: %s' % self.sessions[channel].callerId})
        del self.sessions[channel]
        self.pingWebSessions()


    def getInitialQueue(self):
        timePoint = Time() - timedelta(minutes=15)
        print 11
        try:
            q = [r.filenameAsAsterisk() for r in self.store.query(Recording, AND(Recording.created >= timePoint, Recording.use_in_ending == False), sort=Recording.created.ascending)]
        except:
            log.err()
        print 2
        intro = self.getRecordingByName("intro")
        if intro:
            q.insert(0, intro.filenameAsAsterisk())
        print q
        return q


    def getRecordingByName(self, name):
        r = list(self.store.query(Recording, Recording.filename == unicode(name)))
        if r:
            return r[0]
        return None


    def recordingAdded(self, session, r):
        self.convertToMP3(r)
        r.use_in_ending = self.useRecordingsInEnding

        self.webio.sendAll({'event': 'message', 'title': 'New recording', 'text': 'From: %s' % session.callerId})

        self.pingWebRecordings()
        if self.useRecordingsInEnding:
            # do not directly play back
            return

        for session in self.sessions.values():
            if session.isLivePhone:
                continue
            session.queueAdd(r.filenameAsAsterisk())
            if session.state.get == 'conference':
                self.transferToAGI(session, 'to_play')


    def queueAll(self, filename):
        num = 0
        for session in self.sessions.values():
            if session.isLivePhone:
                continue
            session.queueAddFirst(filename)
            num += 1
            if session.state.get == 'conference':
                self.transferToAGI(session, 'to_play')

        if not num:
            self.webio.sendAll({'event': 'message', 'title': 'Warning', 'text': 'No listeners to push the recording to.'})

        self.pingWebSessions()


    def redirect(self, session, exten):
        d = self.admin.redirect(session.channel, 'default', exten, '1')
        def logAndDisconnect(f):
            print "*** TRANSFER FAILURE"
            self.sessionEnded(session.channel)
            log.err(f)
        d.addErrback(logAndDisconnect)
        d.addCallback(lambda _: self.pingWebSessions())


    def transferToConference(self, session):
        session.state.set("to_conference")
        self.redirect(session, EXTEN_CONFERENCE)


    def transferToAGI(self, session, state):
        session.state.set(state)
        self.redirect(session, EXTEN_AGI)


    def conferenceJoin(self, admin, e):
        channel = e['channel']
        if channel not in self.sessions:
            print "???", e
            return
        print "%s joined the conference" % channel
        session = self.sessions[channel]
        session.state.set("conference")
        session.conferenceUserId = e['member']

        if not session.isLivePhone:
            self.admin.sendMessage({'action': 'ConferenceMute', 'Conference': 'weareforests', 'User': e['member']})
        else:
            self.admin.sendMessage({'action': 'ConferenceUnmute', 'Conference': 'weareforests', 'User': e['member']})
        self.pingWebSessions()


    def conferenceLeave(self, admin, e):
        session = self.sessions[e['channel']]
        if session.state.get != "conference":
            print "Transfered from conference to AGI:", e['channel']
            return
        # hangup
        print "%s left the conference" % e['channel']
        del self.sessions[e['channel']]
        self.pingWebSessions()


    def conferenceDTMF(self, admin, e):
        print "DTMF", e
        session = self.sessions[e['channel']]
        if e['key'] == '1':
            # trigger recording from conference
            self.transferToAGI(session, 'to_recording')


    def convertToMP3(self, recording):
        fn = recording.filenameAsPath(self)
        os.system("sox -t gsm -r 8000 -c 1 %s.gsm -r 44100 -t raw - | lame -r -m m -s 44.1 - %s.mp3 &" % (fn, fn))


    def placeCalls(self, nrs):
        for nr in nrs:
            dial = self.phoneNrToDialString(nr)
            self.admin.originate(dial, "default", EXTEN_AGI_DIALOUT, "1", timeout=30, callerid=nr, async=1).addCallback(log.msg)


    def phoneNrToDialString(self, nr):
        return "SIP/" + nr + "@3617009942"
        #return "SIP/5010"

