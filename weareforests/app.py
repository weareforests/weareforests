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

from twisted.internet import reactor, defer, task
from twisted.python import log

from sparked import application

from starpy import fastagi, manager

from axiom.store import Store

from weareforests import telephony, web

WHITELIST=["5010", "0653638994", "0641322599", "0653639052"]


import logging
lg = logging.getLogger('AMI')
lg.setLevel(logging.DEBUG)


EXTEN_CONFERENCE = '503'
EXTEN_AGI = '502'


class Application (application.Application, web.WebMixIn):


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

        f.login("127.0.0.1", 5038).addCallback(r)

        self.sessions = {}


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


    def getIdleRecordings(self):
        r = list(self.store.query(Recording, Recording.filename == u'weareforests-audio/silent'))
        if r:
            return r
        rec = Recording(store=self.store, filename=u'weareforests-audio/silent')
        return [rec]


    def sessionEnded(self, channel):
        print 'session ended', channel
        del self.sessions[channel]
        self.pingWebSessions()


    def recordingAdded(self, r):
        for session in self.sessions.values():
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
            session.queueAddFirst(filename)
            if session.state.get == 'conference':
                self.transferToAGI(session, 'to_play')



    def pingWebSessions(self):
        """
        Ping all connected web clients with the list of current sessions.
        """
        self.webio.sendAll({'event': "sessions-change", 'sessions': self.sessionsToJSON()})


    def sessionsToJSON(self):
        s = []
        for session in self.sessions.values():
            s.append({'callerId': session.callerId,
                      'state': session.state.get,
                      'timeStarted': session.timeStarted,
                      'channel': session.channel,
                      'queue': session.queue})
        return s



    def transferToConference(self, session):
        session.state.set("to_conference")
        self.pingWebSessions()
        self.admin.redirect(session.channel, 'default', EXTEN_CONFERENCE, '1').addCallback(lambda _: session.agi.finish())


    def transferToAGI(self, session, state):
        session.state.set(state)
        self.admin.redirect(session.channel, 'default', EXTEN_AGI, '1')
        self.pingWebSessions()


    def conferenceJoin(self, admin, e):
        channel = e['channel']
        if channel not in self.sessions:
            print "???", e
            return
        self.sessions[channel].state.set("conference")
        self.pingWebSessions()


    def conferenceLeave(self, admin, e):
        session = self.sessions[e['channel']]
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
