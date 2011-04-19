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
from sparked import application

from starpy import fastagi, manager

from axiom.store import Store

from weareforests import telephony, web


WHITELIST=["5010", "0653638994", "0641322599", "0653639052"]

EXTEN_CONFERENCE = '503'
EXTEN_AGI = '502'


class Application (application.Application, web.WebMixIn):

    useRecordingsInEnding = False


    def started(self):

        # database handling
        print self.path("db").path
        self.store = Store(self.path("db").child("storage").path)
        p = self.path("db").child("audio")
        if not p.exists(): p.createDirectory()

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
            self.admin.registerEvent("OriginateResponse", self.originateResponse)
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
            # new recording
            session = telephony.CallerSession(self, agi)
            self.sessions[session.channel] = session
        else:
            # re-entry from conference
            self.sessions[channel].reEntry(agi)
        self.pingWebSessions()


    def sessionEnded(self, channel):
        print 'session ended', channel
        del self.sessions[channel]
        self.pingWebSessions()


    def recordingAdded(self, r):
        self.convertToMP3(r)
        r.use_in_ending = self.useRecordingsInEnding
        self.pingWebRecordings()
        if self.useRecordingsInEnding:
            # do not directly play back
            return

        for session in self.sessions.values():
            if session.isLivePhone:
                continue
            session.queueAdd(r.filename)
            if session.state.get == 'conference':
                self.transferToAGI(session, 'to_play')


    def isAdmin(self, session):
        print "Admin request:", session.callerId
        if str(session.callerId) in WHITELIST:
            return True
        return False


    def queueAll(self, filename):
        for session in self.sessions.values():
            if session.isLivePhone:
                continue
            session.queueAddFirst(filename)
            if session.state.get == 'conference':
                self.transferToAGI(session, 'to_play')
        self.pingWebSessions()


    def pingWebSessions(self):
        """
        Ping all connected web clients with the list of current sessions.
        """
        self.webio.sendAll({'event': "sessions-change", 'sessions': self.sessionsToJSON()})


    def pingWebRecordings(self):
        """
        Ping all connected web clients with the list of current recordings.
        """
        self.webio.sendAll({'event': "recordings-change", 'recordings': self.recordingsToJSON()})


    def sessionsToJSON(self):
        s = []
        for session in self.sessions.values():
            s.append({'callerId': session.callerId,
                      'state': session.state.get,
                      'timeStarted': Time.fromPOSIXTimestamp(session.timeStarted).asHumanly(),
                      'channel': session.channel,
                      'isLive': session.isLivePhone,
                      'queue': list(session.queue)})
        return s


    def recordingsToJSON(self):
        s = []
        def timefmt(sec):
            return "%d:%02d" % (sec // 60, sec % 60)
        for r in self.store.query(telephony.Recording, sort=telephony.Recording.created.ascending):
            s.append({'id': r.storeID,
                      'time': r.created.asHumanly(),
                      'callerId': r.caller_id,
                      'url': r.filenameAsURL() + ".mp3",
                      'use_in_ending': r.use_in_ending,
                      'duration': timefmt(r.duration/8000)})
        return s


    def redirect(self, session, exten):
        d = self.admin.redirect(session.channel, 'default', exten, '1')
        def logAndDisconnect(f):
            print "*** TRANSFER FAILURE"
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
        print "%s left the conference" % e['channel']
        if session.state.get[:3] == 'to_':
            return
        # hangup
        del self.sessions[e['channel']]
        self.pingWebSessions()


    def conferenceDTMF(self, admin, e):
        print "DTMF", e
        session = self.sessions[e['channel']]
        if e['key'] == '1':
            # trigger recording from conference
            self.transferToAGI(session, 'to_recording')
        if e['key'] == '0' and self.isAdmin(session):
            # trigger recording from conference
            self.transferToAGI(session, 'to_admin')


    def convertToMP3(self, recording):
        fn = recording.filenameAsPath(self)
        os.system("sox -t gsm -r 8000 -c 1 %s.gsm -r 44100 -t raw - | lame -r -m m -s 44.1 - %s.mp3 &" % (fn, fn))


    def call(self, nr):
        mapping = {'+31': '31207173677',
                   '+36': '3617009942'}

        addr = "SIP/0%s@%s" % (nr[3:], mapping[nr[:3]])
        print "Calling:", addr
        d = self.admin.originate("SIP/0641322599@31207173677", "to-external", "1", 1, timeout=30, callerid=nr, async=False)
        d.addCallback(log.msg)


    def originateResponse(self, admin, e):
        print "**********************"
        print e
        print "**********************"

