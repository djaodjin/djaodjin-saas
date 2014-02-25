/* Functionality related to the SaaS API for Carts.
 */

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
