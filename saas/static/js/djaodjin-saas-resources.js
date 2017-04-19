/** These are plumbing functions to connect the UI and API backends.
 */

function showMessages(messages, style) {
    "use strict";
    if( typeof toastr !== 'undefined'
        && $(toastr.options.containerId).length > 0 ) {
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
        var data = resp.data || resp.responseJSON || null;
        if( data && typeof data === "object" ) {
            if( data.detail ) {
                messages = ["Error: " + data.detail];
            } else {
                for( var key in data ) {
                    if (data.hasOwnProperty(key)) {
                        var message = data[key];
                        if( $.isArray(data[key]) ) {
                            message = "";
                            var sep = "";
                            for( var i = 0; i < data[key].length; ++i ) {
                                var messagePart = data[key][i];
                                if( typeof data[key][i] !== 'string' ) {
                                    messagePart = JSON.stringify(data[key][i]);
                                }
                                message += sep + messagePart;
                                sep = ", ";
                            }
                        }
                        messages.push(key + ": " + message);
                        $("[name=\"" + key + "\"]").addClass("has-error");
                    }
                }
            }
        } else if( resp.detail ) {
            messages = ["Error: " + resp.detail];
        }
    }
    if( messages.length === 0 ) {
        messages = ["Error " + resp.status + ": " + resp.statusText];
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
