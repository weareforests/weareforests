(function()
{
    function refreshSessions (sessions)
    {
        var tb = $("#sessions tbody");
        tb.children().remove();
        $(sessions).each(function (i, v) {
                             var t = (new Date(v.timeStarted*1000));

                             var liveEl;
                             if (!v.isLive)
                             {
                                 liveEl = $("<a>").attr("href", "javascript:;").click(function(){IO.send({'cmd': 'setlive', 'channel': v.channel})}).text("set live");
                             }
                             else
                             {
                                 liveEl = $("<a>").attr("href", "javascript:;").click(function(){IO.send({'cmd': 'unsetlive', 'channel': v.channel})}).text("unset live");
                             }
                             $("<tr>")
                                 .append($("<td>").text(v.callerId))
                                 .append($("<td>").text(t.toLocaleTimeString()))
                                 .append($("<td>").text(v.state + (v.state == "play" ? " (" + (v.queue.length+1) + ")" : "")))
                                 .append($("<td>").append(v.state == "conference" ? liveEl : "&nbsp;"))
                                 .appendTo(tb);
                         });
    }

    // The dispatcher
    IO.recv(function (msg)
    {
        //console.log(msg);

        switch (msg.event)
        {
        case "sessions-change":
            refreshSessions(msg.sessions);
            break;
        }
    });


})();