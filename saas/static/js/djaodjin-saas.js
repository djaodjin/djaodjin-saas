/* Functionality related to the SaaS API.
 */


/** Update fields in a ``Plan`` by executing an AJAX request on the backend.
 */
function updatePlanAPI(plan, title, description, success) {
  $.ajax({ type: "PATCH",
           url: '/api/plans/' + plan + '/',
           data: JSON.stringify({ "title": title, "description": description }),
          datatype: "json",
          contentType: "application/json; charset=utf-8",
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
      $.ajax({ type: "POST", // XXX PUT?
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
    by executing an AJAX request on the backend.
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


function waitForChargeCompleted(charge) {
  $.get('/api/charges/' + charge + '/',
      {dataType: "json",
      success: function(data) {
          if( data['state'] == '' ) {
             self.addClass('activated');
             self.text('Deactivate')
          } else {
             setTimeout("waitForChargeCompleted(" + charge + ");", 1000);
          }
      }
  });
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
