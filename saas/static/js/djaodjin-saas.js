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


/** Create a ``Plan`` by executing an AJAX request to the service.
 */
function createPlanAPI(organization, success) {
  $.ajax({ type: "POST",
           url: '/api/plans/',
           data: JSON.stringify({"organization": organization,
               "title": "New Plan",
               "description": "Write the description of the plan here.",
               "interval": 4,
               "is_active": 1}),
           datatype: "json",
           contentType: "application/json; charset=utf-8",
           success: success,
           error: function(data) {
               showMessages(["An error occurred while emailing a copy of the receipt (" + data.status + " " + data.statusText + "). Please accept our apologies."], "danger");
           }
  });
}

/** Update fields in a ``Plan`` by executing an AJAX request to the service.
 */
function updatePlanAPI(plan, data, success) {
  $.ajax({ type: "PATCH",
           url: '/api/plans/' + plan + '/',
           async: false,
           data: JSON.stringify(data),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
          success: success,
  });
}

function deletePlanAPI(plan, success) {
  $.ajax({ type: "DELETE",
           url: '/api/plans/' + plan + '/',
           async: false,
          success: success,
  });
}


function getPlanAPI(plan, success) {
  $.ajax({ type: "GET",
         async:false,
         url: '/api/plans/' + plan + '/',
         success: success,
  });
}


function toggleCartItem(event) {
  var self = $(this);
  event.preventDefault();
  if( self.text() == "Remove from Cart" ) {
      $.ajax({ type: "DELETE",
          url: '/api/cart/' + self.attr("id") + '/',
/*
          data: JSON.stringify({ "plan": self.attr("id") }),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
*/
          success: function(data) {
              self.text("Add to Cart");
          }
      });
  } else {
      $.ajax({ type: "POST", // XXX Might still prefer to do PUT on list.
          url: '/api/cart/',
          data: JSON.stringify({ "plan": self.attr("id") }),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
          success: function(data) {
              self.text("Remove from Cart");
          }
      });
  }
}


/** Toggle a ``Plan`` from active to inactive and vise-versa
    by executing an AJAX request to the service.
 */
function toggleActivatePlan(event) {
  var self = $(this);
  event.preventDefault();
  pathname_parts = document.location.pathname.split('/')
  organization = pathname_parts[2]
  plan = pathname_parts[4]
  is_active = !self.hasClass('activated');
  $.ajax({ type: "PATCH",
           url: '/api/plans/' + plan + '/activate/',
           data: JSON.stringify({ "is_active": is_active }),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
      success: function(data) {
         if( data['is_active'] ) {
             self.addClass('activated');
             self.text('Deactivate')
         } else {
             self.removeClass('activated');
             self.text('Activate')
         }
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
