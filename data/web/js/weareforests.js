(function()
{
    function refreshSessions (sessions)
    {
        var tb = $("#sessions tbody");
        tb.children().remove();
        $(sessions).each(function (i, v) {
                             var t = (new Date(v.timeStarted*1000));
                             $("<tr>")
                                 .append($("<td>").text(v.callerId))
                                 .append($("<td>").text(t.toLocaleTimeString()))
                                 .append($("<td>").text(v.state))
                                 .appendTo(tb);
                         });
    }

    // The dispatcher
    IO.recv(function (msg)
    {
        console.log(msg);

        switch (msg.event)
        {
        case "sessions-change":
            refreshSessions(msg.sessions);
            break;
        }
    });


})();