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


function CartItem(options) {
    "use strict";
    this.item = {};
    var restricted = ["plan", "nb_periods", "first_name", "last_name", "email"];
    for(var i = 0; i < restricted.length; ++i ){
        var key = restricted[i];
        if( key in options ) {
            this.item[key] = options[key];
        }
    }
    this.urls = options.urls;
}


CartItem.prototype = {
    add: function(successFunc, errorFunc) {
        "use strict";
        var self = this;
        $.ajax({ type: "POST", // XXX Might still prefer to do PUT on list.
                 url: self.urls.saas_api_cart,
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 data: JSON.stringify(self.item),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunc,
                 error: errorFunc
               });
    },

    remove: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "DELETE",
                 url: self.urls.saas_api_cart + self.item.plan + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 success: successFunction
               });
    }
};
