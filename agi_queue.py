import hashlib
import random
import time

from twisted.internet import reactor, defer, task
from starpy import fastagi
from twisted.python import log

from epsilon.extime import Time
from datetime import timedelta

from axiom.item import Item
from axiom.store import Store
from axiom.attributes import text, timestamp, integer


class Recording (Item):
    """
    A certain recording.
    """

    created = timestamp() 
    caller_id = text()
    filename = text()
    duration = integer() # in frames


from sparked import application


class Application (application.Application):


    def started(self):

        # database handling
        print self.path("db").path
        self.store = Store(self.path("db").child("storage").path)
        p = self.path("db").child("audio")
        if not p.exists(): p.createDirectory()

        # start AGI service
        f = fastagi.FastAGIFactory(self.connected)
        reactor.listenTCP( 4573, f, 50, '127.0.0.1')

        self.sessions = set()


    def connected(self, agi):
        self.sessions.add(CallerSession(self, agi))


    def getIdleRecordings(self):
        r = list(self.store.query(Recording, Recording.filename == u'audio/silent'))
        if r:
            return r
        rec = Recording(store=self.store, filename=u'audio/silent')
        return [rec]

    def sessionEnded(self, session):
        print 'session ended', session
        self.sessions.remove(session)



class CallerSession (object):
    digit = ord("1")

    def __init__(self, app, agi):
        self.app = app
        self.agi = agi
        self.listened = []
        self.callerId = unicode(self.agi.variables['agi_callerid'])
        self.state = application.StateMachine(self, verbose=1)
        self.state.set("intro")


    def enter_intro(self):
        """
        Play the intro
        """
        print "Playing intro"
        d = self.agi.streamFile("audio/intro", chr(self.digit), 0)
        def audioDone(r):
            digit, offset = r
            if digit == self.digit:
                self.state.set("recording")
            else:
                self.state.set("play")
        d.addCallback(audioDone)
        d.addErrback(self.catchHangup)


    def enter_play(self, recording=None, offset=0):
        """
        A recording has finished or a previous sample has finished;
        choose a new recording to play.
        """
        # look up the next recording
        if not recording:
            current = self.lookupNextRecording()
        else:
            current = recording

        print "Playing recording: %s from %s, offset %d" % (current.filename, current.created, offset)
        d = self.agi.streamFile(str(current.filename), chr(self.digit), offset)
        def audioDone(r):
            self.listened.append(current.storeID)
            digit, offset = r
            if digit == self.digit:
                self.state.set("recording", current, offset)
            else:
                self.state.set("play")
        d.addCallback(audioDone)
        d.addErrback(self.catchHangup)
        

    def lookupNextRecording(self):
        timePoint = Time() - timedelta(minutes=15)
        for r in self.app.store.query(Recording, Recording.created >= timePoint, sort=Recording.created.descending):
            if r.storeID in self.listened:
                continue
            return r
        return random.choice(self.app.getIdleRecordings())


    def enter_recording(self, currentlyPlaying=None, offset=0):
        """
        User has pressed '1' to start the recording.
        """
        start = Time()
        filename = "audio/%s" % hashlib.sha1(str(time.time())).hexdigest()
        d = self.agi.recordFile(filename, "gsm", chr(self.digit))

        def save(r):
            digit, type, duration = r
            rec = Recording(store=self.app.store, filename=unicode(filename), created=start, caller_id=self.callerId, duration=duration)
            print "saved!"
            # resume play where we stopped
            self.state.set("play", currentlyPlaying, offset)
        d.addCallback(save)
        d.addErrback(self.catchHangup)


    def catchHangup(self, f):
        print "***", f
        self.app.sessionEnded(self)
