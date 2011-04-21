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
from twisted.web import static, resource, server, resource
from epsilon.extime import Time

from sparked.web.io import listen

import glob
import os
import tempfile
from email.Parser import Parser
import shutil

from weareforests import telephony


class UploadResource(resource.Resource):

    def __init__(self, app):
        self.app = app


    def render_POST(self, request):
        referer = "/"
        body = ""
        for k, vs in request.requestHeaders.getAllRawHeaders():
            for v in vs:
                if k.lower() == "referer":
                    referer = v
                body += k + ": " + v + "\r\n"
        body += "\r\n"
        body += "".join(request.content.readlines())

        p = Parser()
        msg = p.parsestr(body)
        audiopart = None
        for part in msg.walk():
            if part.is_multipart():
                continue
            if part.get_content_type() == "audio/mp3":
                audiopart = part
                break

        if not audiopart:
            request.redirect(referer+"#uploadFailure")
            return "FAIL"

        print audiopart.get_filename()

        payload = audiopart.get_payload()
        fp, fn = tempfile.mkstemp()
        os.write(fp, payload)
        os.close(fp)

        self.app.fileUploaded(fn, audiopart.get_filename())

        request.redirect(referer+"#uploadOK")
        return "OK"





class WebMixIn:

    def started(self):
        print "--------------------------->>>>"
        print self
        root = resource.Resource()
        root.putChild("", static.File(self.path("data").child("web").child("index.html").path))
        root.putChild("lib", static.File(self.path("data").child("web").child("lib").path))
        root.putChild("recordings", static.File(self.recordingsPath.path))
        root.putChild("upload", UploadResource(self))
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
        self.pingWebRecordings(c)
        self.pingWebSessions(c)

        c.events.addObserver("disconnect", lambda : self.webClients.remove(c))
        c.events.addObserver("message", lambda msg: self.handleMessage(msg, c))


    def fileUploaded(self, tmpfile, filename):
        base = filename[:-4] # strip extension
        filename = base
        f = self.recordingsPath.child(base+".mp3")
        i = 0
        while f.exists():
            filename = "%s-%d" % (base, i)
            i += 1
            f = self.recordingsPath.child(filename+".mp3")

        # copy to dest
        shutil.copyfile(tmpfile, f.path)

        # convert to mp3
        os.system("lame --decode \"%s\" - | sox - -t raw -r 8000 -s -2 -c 1 \"%s\"" % (f.path, f.path.replace(".mp3", ".sln")))

        # get the duration
        duration = os.stat(f.path.replace(".mp3", ".sln")).st_size / 16000

        # save it
        rec = telephony.Recording(store=self.store, filename=unicode(filename), created=Time(), caller_id=u"web upload", duration=duration, user_recording=False)

        self.pingWebRecordings()


    def handleMessage(self, msg, c):
        if 'cmd' in msg:
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

            if msg['cmd'] == 'call':
                self.call(msg['nr'])

            if msg['cmd'] == 'deleteRecording':
                r = self.store.getItemByID(int(msg['id']))
                path = r.filenameAsPath(self)
                r.deleteFromStore()
                os.system("rm %s.*" % path)
                self.pingWebRecordings()

            if msg['cmd'] == 'queue':
                r = self.store.getItemByID(int(msg['id']))
                self.queueAll(r.filenameAsAsterisk())


        print c, 'says:', msg



    def pingWebSessions(self, session=None):
        """
        Ping all connected web clients with the list of current sessions.
        """
        if session:
            cb = session.send
        else:
            cb = self.webio.sendAll
        cb({'event': "sessions-change", 'sessions': self.sessionsToJSON()})


    def pingWebRecordings(self, session=None):
        """
        Ping all connected web clients with the list of current recordings.
        """
        if session:
            cb = session.send
        else:
            cb = self.webio.sendAll
        l = self.recordingsToJSON(self.store.query(telephony.Recording, telephony.Recording.user_recording == True, sort=telephony.Recording.created.ascending))
        cb({'event': "user-recordings-change", 'recordings': l})
        l = self.recordingsToJSON(self.store.query(telephony.Recording, telephony.Recording.user_recording == False, sort=telephony.Recording.created.ascending))
        cb({'event': "web-recordings-change", 'recordings': l})


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


    def recordingsToJSON(self, recordings):
        s = []
        def timefmt(sec):
            return "%d:%02d" % (sec // 60, sec % 60)
        for r in recordings:
            if r.user_recording:
                title = r.caller_id
            else:
                title = r.filename
            s.append({'id': r.storeID,
                      'time': r.created.asHumanly(),
                      'title': title,
                      'url': r.filenameAsURL(),
                      'use_in_ending': r.use_in_ending,
                      'duration': timefmt(r.duration)})
        return s
