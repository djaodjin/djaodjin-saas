function showMessages(messages, style) {
    "use strict";
    var messageBlock = "<div class=\"alert alert-block";
    if( style ) {
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
                                   "). Please accept our apologies."], "danger");
                 }
               });
    },

    /** Activate a ``Plan`` by executing an AJAX request to the service.
     */
    activate: function(isActive, successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "PATCH",
                 url: this.urls.saas_api_plan + "/" + self.id + "/activate/",
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
        $.ajax({ type: "PATCH",
                 url: this.urls.saas_api_plan + "/" + self.id + "/",
                 async: false,
                 data: JSON.stringify(data),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunction
               });
    },

    destroy: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "DELETE",
                 url: this.urls.saas_api_plan + "/" + self.id + "/",
                 async: false,
                 success: successFunction
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
                 success: successFunction
               });
    }
};


function Charge(chargeId, urls) {
    "use strict";
    this.chargeId = chargeId;
    this.urls = urls;
}


Charge.prototype = {

    emailReceipt: function() {
        "use strict";
        var self = this;
        $.ajax({ type: "POST",
                 url: self.urls.saas_api_email_charge_receipt,
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     showMessages(["A copy of the receipt was sent to " + data.email + "."], "info");
                 },
                 error: function(data) {
                     showMessages(["An error occurred while emailing a copy of the receipt (" + data.status + " " + data.statusText + "). Please accept our apologies."], "danger");
                 }
               });
    },

    refund: function(event, linenum, refundedAmount, refundButton) {
        "use strict";
        var self = this;
        event.preventDefault();
        refundButton.attr("disabled", "disabled");
        $.ajax({ type: "POST",
                 url: self.urls.saas_api_charge_refund,
                 data: JSON.stringify({"lines":
                     [{"num": linenum, "refunded_amount": refundedAmount}]}),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     var message = "Amount refunded.";
                     if( data.responseJSON ) {
                         message = data.responseJSON.detail;
                     }
                     showMessages([message], "info");
                     refundButton.replaceWith("<em>Refunded</em>");
                 },
                 error: function(data) {
                     var message = data.statusText;
                     if( data.responseJSON ) {
                         message = data.responseJSON.detail;
                     }
                     showMessages([
                        "An error occurred while refunding the charge (" + data.status + " - " + 
                        message + "). Please accept our apologies."], "danger");
                     refundButton.removeAttr("disabled");
                 }
               });
    },

    waitForCompletion: function() {
        "use strict";
        var self = this;
        $.ajax({ type: "GET",
                 url: self.urls.saas_api_charge,
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     if( data.state == "created" ) {
                         setTimeout(function() { self.waitForCompletion(); }, 1000);
                     } else {
                         $(".created").addClass("hidden");
                         $("." + data.state).removeClass("hidden");
                     }
                 }
               });
    }
};
