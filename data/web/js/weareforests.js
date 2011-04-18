(function()
{
    function refreshSessions (sessions)
    {
        var tb = $("#sessions tbody");
        tb.children().remove();
        $(sessions).each(function (i, v) {
                             var liveEl;
                             if (v.state == 'conference')
                             {
                                 liveEl = $("<span>")
                                     .append($("<input>")
                                             .attr("type", "checkbox")
                                             .attr("checked", v.isLive ? "checked": "")
                                             .click(function() { 
                                                        IO.send({'cmd': 'toggleLive', 'channel': v.channel});
                                                    }))
                                     .append("can speak");
                             }
                             else
                             {
                                 liveEl = '&nbsp;';
                             }
                             $("<tr>")
                                 .append($("<td>").text(v.callerId))
                                 .append($("<td>").text(v.timeStarted))
                                 .append($("<td>").text(v.state + ((v.state == "play" || v.state == "ending") ? " (" + (v.queue.length+1) + ")" : "")))
                                 .append($("<td>").append(liveEl))
                                 .appendTo(tb);
                         });
    }


    function refreshRecordings (recordings)
    {
        var tb = $("#recordings tbody");
        tb.children().remove();
        $(recordings).each(function (i, v) {
                             $("<tr>")
                                   .append($("<td>").text(v.callerId))
                                   .append($("<td>").text(v.time))
                                   .append($("<td>").text(v.duration))
                                   .append($("<td>")
                                           .append($("<button>").text("Preview").click(function(){$("#audio").attr("src", v.url).get(0).play();}))
                                           .append($("<input>")
                                                   .attr("type", "checkbox")
                                                   .attr("checked", v.use_in_ending ? "checked": "")
                                                   .click(function() { 
                                                              IO.send({'cmd': 'toggleUseInEnding', 'id': v.id});
                                                          })
                                                  )
                                           .append("use in ending")
                                          )
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
        case "recordings-change":
            refreshRecordings(msg.recordings);
            break;
        case "state-change":
            $("#state").text(msg.state);
            var btn = {'normal': {text: "go to ending", cmd: 'doEnding'},
                       'ending': {text: "restart", cmd: 'doRestart'}};
            $("#state").append($("<button>")
                               .text(btn[msg.state].text)
                               .click(function() {
                                          if (confirm('Are you sure?')) {
                                              IO.send({'cmd': btn[msg.state].cmd});
                                          }}));
            break;
        case "userecordings-change":
            var id = "#use-recordings-" + (msg.value ? 'ending' : 'default');
            $(id).attr("checked", true);
            break;
        }
    });

    $(document).ready(function() 
    {
        $("input[name=use-recordings]").click(function() 
                                              {
                                                  IO.send({'cmd': 'appUseRecordingsInEnding', 'value': $(this).attr("id") == 'use-recordings-ending'});
                                              });
    });

})();