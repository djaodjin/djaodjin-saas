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
            messageBlock += "<p>" + messages[i] + "</p>";
         }
         messageBlock += "</div>";
         $("#messages").removeClass("hidden");
         $("#messages-content").append(messageBlock);
         $("html, body").animate({
             // scrollTop: $("#messages").offset().top - 50
             // avoid weird animation when messages at the top:
             scrollTop: $("body").offset().top
         }, 500);
    }
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


function Card(urls) {
    "use strict";
    this.urls = urls;
};


Card.prototype = {
    query: function() {
        "use strict";
        var self = this;
        $.get(self.urls.saas_api_card, function(data) {
            $("#last4").text(data.last4);
            $("#exp_date").text(data.exp_date);
        }).fail(function() {
            $("#last4").text("Err");
            $("#exp_date").text("Err");
        });
    }
};


function Plan(id, urls) {
    "use strict";
    this.id = id;
    this.urls = urls;
}


/** Create a ``Plan`` by executing an AJAX request to the service.
 */
Plan.prototype = {
    create: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "POST",
                 url: self.urls.saas_api_plan + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 data: JSON.stringify({
                     "title": "New Plan",
                     "description": "Write the description of the plan here.",
                     "interval": 4,
                     "is_active": 1}),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunction,
                 error: function(data) {
                     showMessages(["An error occurred while creating the plan (" +
                                   data.status + " " + data.statusText +
                                   "). Please accept our apologies."], "error");
                 }
               });
    },

    /** Activate a ``Plan`` by executing an AJAX request to the service.
     */
    activate: function(isActive, successFunction) {
        "use strict";
        var self = this;
        $.ajax({type: "PUT",
                 url: this.urls.saas_api_plan + "/" + self.id + "/activate/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 data: JSON.stringify({ "is_active": isActive }),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunction
               });
    },

    /** Update fields in a ``Plan`` by executing an AJAX request to the service.
     */
    update: function(data, successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "PUT",
                 url: this.urls.saas_api_plan + "/" + self.id + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 async: false,
                 data: JSON.stringify(data),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunction
               });
    },

    destroy: function(successFunction, errorFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "DELETE",
                 url: this.urls.saas_api_plan + "/" + self.id + "/",
                 async: false,
                 success: successFunction,
                 error: errorFunction
               });
    },

    get: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "GET",
                 url: this.urls.saas_api_plan + "/" + self.id + "/",
                 success: successFunction
               });
    }
};


/** Toggle a ``Plan`` from active to inactive and vise-versa
    by executing an AJAX request to the service.
 */
function toggleActivatePlan(button, urls) {
  "use strict";
  var planSlug = button.attr("data-plan");
  var thisPlan = new Plan(planSlug, urls);
  thisPlan.activate(!button.hasClass("activated"), function(data) {
      if( data.is_active ) {
          button.addClass("activated");
          button.text("Deactivate");
      } else {
          button.removeClass("activated");
          button.text("Activate");
      }
  });
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
