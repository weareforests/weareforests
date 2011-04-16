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
        site = server.Site(root)
        self.webio = listen(site)
        reactor.listenTCP(8880, site)

        self.webio.events.addObserver("connection", self.newClient)
        self.webClients = set()


    def newClient(self, c):
        self.webClients.add(c)
        c.send({'event': 'sessions-change', 'sessions': self.sessionsToJSON()})
        c.events.addObserver("disconnect", lambda : self.webClients.remove(c))
        c.events.addObserver("message", lambda msg: self.handleMessage(msg, c))


    def handleMessage(self, msg, c):
        print c, 'says:', msg



