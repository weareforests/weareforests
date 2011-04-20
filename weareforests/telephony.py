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

import hashlib
import random
import time

from epsilon.extime import Time
from datetime import timedelta

from twisted.internet import reactor

from axiom.item import Item
from axiom.attributes import text, timestamp, integer, boolean, AND

from sparked import application

from weareforests.pqueue import PriorityQueue


class Recording (Item):
    """
    A certain recording.
    """

    created = timestamp() 
    caller_id = text()
    filename = text()
    duration = integer() # in frames
    use_in_ending = boolean()
    user_recording = boolean()


    def filenameAsPath(self, app):
        """
        Return absolute filename without extension
        """
        return app.path("db").child("recordings").child(self.filename).path


    def filenameAsURL(self):
        """
        Return filename as MP3 url
        """
        return "/recordings/" + self.filename + ".mp3"


    def filenameAsAsterisk(self):
        return "weareforests-recordings/%s" % self.filename


    @staticmethod
    def userRecordingFilename(app):
        """
        Generate a new filename for a user recording.
        """
        base = "user-%d" % time.time()
        fn = base
        f = app.path("db").child("recordings").child(fn)
        i = 1
        while f.exists():
            fn = base+("-%d"%i)
            f = app.path("db").child("recordings").child(fn)
            i += 1
        return fn



class CallerSession (object):
    digit = ord("1")

    app = None
    agi = None
    queue = None

    # info
    channel = None
    callerId = None
    timeStarted = None

    # conference user id
    conferenceUserId = None
    isLivePhone = False

    # state machine
    state = None


    def __init__(self, app, agi):
        self.app = app
        self.agi = agi
        self.queue = PriorityQueue()
        print self.agi.variables
        self.callerId = unicode(self.agi.variables['agi_callerid'])
        self.channel = self.agi.variables['agi_channel']
        self.timeStarted = time.time()
        print "New session from", self.callerId
        self.state = application.StateMachine(self, verbose=1)
        self.state.set("start")


    def reEntry(self, agi):
        self.agi = agi
        if self.state.get == 'to_recording':
            self.setStateAfterSample("recording", "weareforests-audio/record")
        if self.state.get == 'to_play':
            self.state.set('play')
        if self.state.get == 'to_start':
            self.state.set('start')
        if self.state.get == 'to_admin':
            self.setStateAfterSample("admin", "digits/0")
        if self.state.get == 'to_ending':
            self.queue = PriorityQueue()
            for f in [r.filenameAsAsterisk() for r in self.app.store.query(Recording, Recording.use_in_ending == True, sort=Recording.created.descending)]:
                self.queueAdd(f)
            self.state.set('ending')


    def enter_ending(self):
        if self.queue.isEmpty():
            self.state.set("ended")
            self.app.pingWebSessions()
            return
        item = self.queue.pop()
        self.app.pingWebSessions()
        self.setStateAfterSample("ending", item)


    def enter_ended(self):
        self.setStateAfterSample("ended", "weareforests-audio/silent")


    def queueAdd(self, r):
        self.queue.append(10, r)


    def queueAddFirst(self, r):
        self.queue.append(5, r)


    def enter_start(self):
        timePoint = Time() - timedelta(minutes=15)

        if self.app.baseOpts['debug']:
            self.queueAdd("weareforests-audio/silent")
        else:
            self.queueAdd("weareforests-audio/intro")
            for f in [r.filenameAsAsterisk() for r in self.app.store.query(Recording, AND(Recording.created >= timePoint, Recording.use_in_ending == False), sort=Recording.created.ascending)]:
                self.queueAdd(f)
        self.state.set("play")


    def enter_play(self, recording=None, offset=0):
        """
        A recording has finished or a previous sample has finished;
        choose a new recording to play.
        """
        self.app.pingWebSessions()

        # look up the next recording
        if not recording:
            if self.queue.isEmpty():
                # if no recording, transfer to conference
                self.app.transferToConference(self)
            else:
                current = self.queue.pop()
        else:
            current = recording

        print "Playing recording: %s, offset %d" % (current, offset)
        d = self.agi.streamFile(str(current), chr(self.digit)+"0", offset)
        def audioDone(r):
            digit, offset = r
            if digit == self.digit:
                self.setStateAfterSample("recording", "weareforests-audio/record", current, offset)
            elif digit == ord("0"):
                if self.app.isAdmin(self):
                    self.setStateAfterSample("admin", "digits/0")
                else:
                    print "not authorized to enter admin mode from " + self.callerId
                    # just play the same
                    self.state.set("play", current)
            else:
                self.state.set("play")
        d.addCallback(audioDone)
        d.addErrback(self.catchHangup)


    def enter_recording(self, currentlyPlaying=None, offset=0):
        """
        User has pressed '1' to start the recording.
        """
        self.app.pingWebSessions()

        start = Time()
        filename = Recording.userRecordingFilename(self.app)
        d = self.agi.recordFile("weareforests-recordings/" + filename, "gsm", chr(self.digit), 45)

        def save(r):
            digit, tpe, duration = r
            rec = Recording(store=self.app.store, filename=unicode(filename), created=start, caller_id=self.callerId, duration=duration, user_recording=True)
            print "saved!"
            if tpe == 'hangup':
                print "user hung up during recording."
                self.app.sessionEnded(self.channel)

            # add it to everybody's queue
            self.app.recordingAdded(rec)
            # resume play where we stopped
            self.setStateAfterSample("play", "weareforests-audio/listen", currentlyPlaying, offset)

        d.addCallback(save)
        d.addErrback(self.catchHangup)


    def setStateAfterSample(self, state, sample, *args):
        d = self.agi.streamFile(str(sample), "", 0)
        def audioDone(r):
            print "audio done"
            self.state.set(state, *args)
        d.addCallback(audioDone)
        d.addErrback(self.catchHangup)


    def enter_admin(self):
        self.app.pingWebSessions()
        d = self.agi.getOption("weareforests-audio/silent", "0123456789#")

        def handle(r):
            digit, endpos = r
            print digit
            if digit == "0":
                self.setStateAfterSample("play", "weareforests-audio/listen")
                return
            filename = "weareforests-audio/%s" % digit
            print "queueing to all: %s" % filename
            self.app.queueAll(filename)
            d = self.agi.sayDigits(digit)
            d.addCallback(lambda _: self.state.set("admin"))
        d.addCallback(handle)
        d.addErrback(self.catchHangup)


    def catchHangup(self, f):
        self.agi.finish()
        if self.state.get[:3] == 'to_':
            return

        print "***", f
        self.app.sessionEnded(self.channel)
