/* Functionality related to the SaaS API.
 */

function showMessages(messages, style) {
    $("#messages").removeClass('hidden');
    var messageBlock = $('<div class="alert alert-block"><button type="button" class="close" data-dismiss="alert">&times;</button></div>');
    $("#messages .row").append(messageBlock);
    if( style ) {
        messageBlock.addClass("alert-" + style);
    }
    for( var i = 0; i < messages.length; ++i ) {
        messageBlock.append('<p>' + messages[i] + '</p>');
    }
    $("html, body").animate({ scrollTop: $("#messages").offset().top - 50 },
        500);
}


function initAjaxCSRFHook(csrf_token) {
    /** Include the csrf_token into the headers to authenticate with the server
        on ajax requests. */
    $(document).ajaxSend(function(event, xhr, settings) {
        function sameOrigin(url) {
            // url could be relative or scheme relative or absolute
            var host = document.location.host; // host + port
            var protocol = document.location.protocol;
            var sr_origin = '//' + host;
            var origin = protocol + sr_origin;
            // Allow absolute or scheme relative URLs to same origin
            return (url == origin ||
                url.slice(0, origin.length + 1) == origin + '/') ||
               (url == sr_origin ||
                url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
        // or any other URL that isn't scheme relative or absolute i.e relative.
               !(/^(\/\/|http:|https:).*/.test(url));
        }
        function safeMethod(method) {
            return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
        }
        if (!safeMethod(settings.type) && sameOrigin(settings.url)) {
            xhr.setRequestHeader("X-CSRFToken", csrf_token);
        }
    });
}


var Plan = function(id, urls) {
    this.urls = urls;
    this.id = id;
}

/** Activate a ``Plan`` by executing an AJAX request to the service.
 */
Plan.prototype.activate = function(is_active, successFunction) {
  var self = this;
  $.ajax({ type: "PATCH",
           url: self.urls.saas_api_plan + self.id + '/activate/',
           data: JSON.stringify({ "is_active": is_active }),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
      success: successFunction,
  });
}


/** Create a ``Plan`` by executing an AJAX request to the service.
 */
Plan.prototype.create = function(organization, successFunction) {
    var self = this;
     $.ajax({ type: "POST",
           url: self.urls.saas_api_plan,
           data: JSON.stringify({"organization": organization,
               "title": "New Plan",
               "description": "Write the description of the plan here.",
               "interval": 4,
               "is_active": 1}),
           datatype: "json",
           contentType: "application/json; charset=utf-8",
           success: successFunction,
           error: function(data) {
               showMessages(["An error occurred while creating the plan ("
                   + data.status + " " + data.statusText
                   + "). Please accept our apologies."], "danger");
           }
  });
}

/** Update fields in a ``Plan`` by executing an AJAX request to the service.
 */
Plan.prototype.update = function(data, successFunction) {
  var self = this;
  $.ajax({ type: "PATCH",
           url: self.urls.saas_api_plan + self.id + '/',
           async: false,
           data: JSON.stringify(data),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
          success: successFunction,
  });
}

Plan.prototype.destroy = function(successFunction) {
  var self = this;
  $.ajax({ type: "DELETE",
           url: self.urls.saas_api_plan + self.id + '/',
           async: false,
           success: successFunction,
  });
}


Plan.prototype.get = function(successFunction) {
  var self = this;
  $.ajax({ type: "GET",
           url: self.urls.saas_api_plan + self.id + '/',
           success: successFunction,
  });
}


var CartItem = function(id, urls) {
    this.item = id;
    this.urls = urls;
};

CartItem.prototype.add = function(successFunction) {
    var self = this;
    $.ajax({ type: "POST", // XXX Might still prefer to do PUT on list.
        url: self.urls.saas_api_cart,
        data: JSON.stringify({ "plan": self.item }),
        datatype: "json",
        contentType: "application/json; charset=utf-8",
        success: successFunction,
    });
}

CartItem.prototype.remove = function(successFunction) {
    var self = this;
    $.ajax({ type: "DELETE",
        url: self.urls.saas_api_cart + self.item + '/',
        success: successFunction,
    });
}


/** Toggle a ``Plan`` from active to inactive and vise-versa
    by executing an AJAX request to the service.
 */
function toggleActivatePlan(button, urls) {
  var pathname_parts = document.location.pathname.split('/')
  var organization = pathname_parts[2]
  var thisPlan = new Plan(pathname_parts[4], urls);
  var is_active = !button.hasClass('activated');
  thisPlan.activate(!button.hasClass('activated'), function(data) {
      if( data['is_active'] ) {
          button.addClass('activated');
          button.text('Deactivate');
      } else {
          button.removeClass('activated');
          button.text('Activate');
      }
  });
}


var Charge = function(charge_id, urls) {
    this.charge_id = charge_id;
    this.urls = urls;
};


Charge.prototype.emailReceipt = function() {
    var self = this;
    event.preventDefault();
    $.ajax({ type: "POST",
           url: self.urls.saas_api_email_charge_receipt,
           datatype: "json",
          contentType: "application/json; charset=utf-8",
        success: function(data) {
            showMessages(["A copy of the receipt was sent to " + data['email'] + "."], "info");
        },
        error: function(data) {
            showMessages(["An error occurred while emailing a copy of the receipt (" + data.status + " " + data.statusText + "). Please accept our apologies."], "danger");
        }
    });
}


Charge.prototype.refund = function(linenum) {
    var self = this;
    event.preventDefault();
    var refundButton = $('[data-linenum="' + linenum + '"]');
    refundButton.attr("disabled", "disabled");
    $.ajax({ type: "POST",
           url: self.urls.saas_api_charge_refund,
           data: JSON.stringify({ "linenums": [linenum] }),
           datatype: "json",
          contentType: "application/json; charset=utf-8",
        success: function(data) {
          refundButton.replaceWith("<em>Refunded</em>");
          showMessages(["The transaction was refunded."], "info");
        },
        error: function(data) {
          var message = data.statusText;
          if( data.responseJSON ) {
              message = data.responseJSON.detail;
          }
          showMessages(["An error occurred while refunding the charge (" + data.status + " - " + message + "). Please accept our apologies."], "danger");
          refundButton.removeAttr("disabled");
        }
    });
}


Charge.prototype.waitForCompletion = function() {
    var self = this;
    $.ajax({ type: "GET",
           url: self.urls.saas_api_charge,
           datatype: "json",
          contentType: "application/json; charset=utf-8",
        success: function(data) {
            if( data['state'] == 'created' ) {
                setTimeout(function() { self.waitForCompletion(); }, 1000);
            } else {
                $('.created').addClass('hidden');
                $('.' + data['state']).removeClass('hidden');
            }
        }
    });
}


/** Update total amount charged on card based on selected subscription charges.
 */
function updateTotalAmount(formNode) {
    var candidates = formNode.find("input:radio");
    var totalAmount = 0;
    for( var i = 0; i < candidates.length; ++i ) {
        var radio = $(candidates[i]);
        if( radio.is(':checked') ) {
            totalAmount += parseInt(radio.val());
        }
    }
    usdTotalAmount = '$' + (totalAmount / 100).toFixed(2);
    $("#total_amount").text(usdTotalAmount);
    if( totalAmount > 0 ) {
        if( !$("#card-use").is(':visible') ) $("#card-use").slideDown();
    } else {
        if( $("#card-use").is(':visible') ) $("#card-use").slideUp();
    }
}


function onSubscribeChargeChange() {
    updateTotalAmount($(this).parents("form"));
}
