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

from twisted.internet import reactor
from twisted.web import static, resource, server

from sparked.web.io import listen


class WebMixIn:

    def started(self):
        print "--------------------------->>>>"
        print self
        root = resource.Resource()
        root.putChild("", static.File(self.path("data").child("web").child("index.html").path))
        root.putChild("js", static.File(self.path("data").child("web").child("js").path))
        root.putChild("recordings", static.File(self.path("db").child("audio").path))
        site = server.Site(root)
        self.webio = listen(site)
        reactor.listenTCP(8880, site)

        self.webio.events.addObserver("connection", self.newClient)
        self.webClients = set()


    def newClient(self, c):
        self.webClients.add(c)

        # send initial state frame
        c.send({'event': "state-change", 'state': self.state.get})
        c.send({'event': "userecordings-change", 'value': self.useRecordingsInEnding})
        c.send({'event': 'sessions-change', 'sessions': self.sessionsToJSON()})
        c.send({'event': 'recordings-change', 'recordings': self.recordingsToJSON()})

        c.events.addObserver("disconnect", lambda : self.webClients.remove(c))
        c.events.addObserver("message", lambda msg: self.handleMessage(msg, c))


    def handleMessage(self, msg, c):
        if 'cmd' in msg:
            if msg['cmd'] == 'queue':
                self.queueAll(msg['filename'])
                self.pingWebSessions()

            if msg['cmd'] == 'toggleLive':
                session = self.sessions[msg['channel']]
                session.isLivePhone = not session.isLivePhone
                if session.isLivePhone and session.state.get != "conference":
                    self.transferToConference(session)
                    return

                if session.isLivePhone:
                    action = 'ConferenceUnmute'
                else:
                    action = 'ConferenceMute'
                self.admin.sendMessage({'action': action, 'Conference': 'weareforests', 'User': session.conferenceUserId})
                self.pingWebSessions()

            if msg['cmd'] == 'toggleUseInEnding':
                r = self.store.getItemByID(int(msg['id']))
                r.use_in_ending = not r.use_in_ending
                self.pingWebRecordings()

            if msg['cmd'] == 'doEnding':
                self.state.set('ending')

            if msg['cmd'] == 'doRestart':
                self.state.set('start')

            if msg['cmd'] == 'appUseRecordingsInEnding':
                self.useRecordingsInEnding = msg['value']
                self.webio.sendAll({'event': "userecordings-change", 'value': self.useRecordingsInEnding})

        print c, 'says:', msg



