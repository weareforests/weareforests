(function()
{
    function refreshSessions (sessions)
    {
        var tb = $("#sessions tbody");
        tb.children().remove();
        $(sessions).each(function (i, v) {
                             var liveEl;
                             if (v.state == 'conference' || !v.isLive)
                             {
                                 liveEl = $("<span>")
                                     .append($("<button>").text("Hangup").click(function(){IO.send({'cmd': 'hangup', 'channel': v.channel});}))
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


    function refreshRecordings (recordings, id)
    {
        var play = function(url)
        {
            $("#audio").attr("src", url).get(0).play();
        };
        var tb = $("#" + id + " tbody");
        tb.children().remove();
        $(recordings).each(function (i, v) {
                             $("<tr>")
                                   .append($("<td>").append($("<a>").attr("href", v.url).text(v.title).click(function(e){e.preventDefault();play(v.url);})))
                                   .append($("<td>").text(v.time))
                                   .append($("<td>").text(v.duration))
                                   .append($("<td>")
                                           .append($("<button>").text("Push").click(function(){IO.send({'cmd': 'queue', 'id': v.id});}))
                                           .append($("<button>").text("Del").click(function(){if (confirm('Are you sure you want to delete '+v.title+'?')){IO.send({'cmd': 'deleteRecording', 'id': v.id});}}))
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
        case "message":
            $.gritter.add({text:msg.text, title: msg.title, time:2000});
            break;

        case "sessions-change":
            refreshSessions(msg.sessions);
            break;
        case "web-recordings-change":
            refreshRecordings(msg.recordings, "web-recordings");
            break;
        case "user-recordings-change":
            refreshRecordings(msg.recordings, "user-recordings");
            break;
        case "state-change":
            $("#state").text(msg.state);
            var btn = {'normal': {text: "go to ending", cmd: 'doEnding'},
                       'ending': {text: "restart", cmd: 'doRestart'}};
            $("#state-change")
                .text(btn[msg.state].text)
                .unbind("click")
                .click(function() {
                           if (confirm('Are you sure?')) {
                               IO.send({'cmd': btn[msg.state].cmd});
                           }});
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

        $("#callForm").submit(function(e) {
                                  e.preventDefault();
                                  IO.send({'cmd': 'placeCalls', 'nrs': $("#telephone").val()});
                              });

        $("#upload").change(function() { $(this.form).submit(); });

        $.extend($.gritter.options, {
			         fade_in_speed: 300,
			         fade_out_speed: 300,
			         time: 1500
                 });
    });

})();