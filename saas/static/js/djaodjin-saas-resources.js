function showMessages(messages, style) {
    "use strict";
    if( typeof toastr !== 'undefined' ) {
        for( var i = 0; i < messages.length; ++i ) {
            toastr[style](messages[i]);
        }

    } else {
        var messageBlock = "<div class=\"alert alert-block";
        if( style ) {
            if( style === "error" ) {
                style = "danger";
            }
            messageBlock += " alert-" + style;
        }
        messageBlock += "\"><button type=\"button\" class=\"close\" data-dismiss=\"alert\">&times;</button>";

        for( var i = 0; i < messages.length; ++i ) {
            messageBlock += "<div>" + messages[i] + "</div>";
         }
         messageBlock += "</div>";
         $("#messages-content").append(messageBlock);
    }
    $("#messages").removeClass("hidden");
    $("html, body").animate({
        // scrollTop: $("#messages").offset().top - 50
        // avoid weird animation when messages at the top:
        scrollTop: $("body").offset().top
    }, 500);
}


function showErrorMessages(resp) {
    var messages = [];
    if( typeof resp === "string" ) {
        messages = [resp];
    } else {
        messages = ["Error " + resp.status + ": " + resp.statusText];
        if( resp.data && typeof resp.data === "object" ) {
            for( var key in resp.data ) {
                if (resp.data.hasOwnProperty(key)) {
                    var message = resp.data[key];
                    if( typeof resp.data[key] !== 'string' ) {
                        message = "";
                        var sep = "";
                        for( var i = 0; i < resp.data[key].length; ++i ) {
                            var messagePart = resp.data[key][i];
                            if( typeof resp.data[key][i] !== 'string' ) {
                                messagePart = JSON.stringify(resp.data[key][i]);
                            }
                            message += sep + messagePart;
                            sep = ", ";
                        }
                    }
                    messages.push(key + ": " + message);
                    $("#" + key).addClass("has-error");
                }
            }
        } else if( resp.detail ) {
            messages = [resp.detail];
        }
    }
    showMessages(messages, "error");
};


/** Retrieves the csrf-token from a <head> meta tag.

    <meta name="csrf-token" content="{{csrf_token}}">
*/
function getMetaCSRFToken() {
    "use strict";
    var metas = document.getElementsByTagName('meta');
    for( var i = 0; i < metas.length; i++) {
        if (metas[i].getAttribute("name") == "csrf-token") {
            return metas[i].getAttribute("content");
        }
    }
    return "";
}
