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

from starpy import fastagi

from axiom.store import Store

from weareforests import telephony, web

WHITELIST=["5010", "0653638994", "0641322599", "0653639052"]




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

        self.sessions = set()


    def connected(self, agi):
        self.sessions.add(telephony.CallerSession(self, agi))
        self.pingWebSessions()


    def getIdleRecordings(self):
        r = list(self.store.query(Recording, Recording.filename == u'weareforests-audio/silent'))
        if r:
            return r
        rec = Recording(store=self.store, filename=u'weareforests-audio/silent')
        return [rec]


    def sessionEnded(self, session):
        print 'session ended', session
        self.sessions.remove(session)
        self.pingWebSessions()


    def recordingAdded(self, r):
        for session in self.sessions:
            session.queueAdd(r.filename)

    def isAdmin(self, callerId):
        print "Admin request:", callerId
        if str(callerId) in WHITELIST:
            return True
        return False


    def queueAll(self, filename):
        for session in self.sessions:
            session.queueAddFirst(filename)



    def pingWebSessions(self):
        """
        Ping all connected web clients with the list of current sessions.
        """
        self.webio.sendAll({'event': "sessions-change", 'sessions': self.sessionsToJSON()})


    def sessionsToJSON(self):
        s = []
        for session in self.sessions:
            s.append({'callerId': session.callerId,
                      'state': session.state.get,
                      'timeStarted': session.timeStarted})
        return s
