/** These are plumbing functions to connect the UI and API backends.
 */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define(['exports', 'jQuery'], factory);
    } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
        // CommonJS
        factory(exports, require('jQuery'));
    } else {
        // Browser true globals added to `window`.
        factory(root, root.jQuery);
        // If we want to put the exports in a namespace, use the following line
        // instead.
        // factory((root.djResources = {}), root.jQuery);
    }
}(typeof self !== 'undefined' ? self : this, function (exports, jQuery) {


function clearMessages() {
    "use strict";
    jQuery("#messages-content").empty();
};

function showMessages(messages, style) {
    "use strict";
    if( typeof toastr !== 'undefined'
        && jQuery(toastr.options.containerId).length > 0 ) {
        for( var i = 0; i < messages.length; ++i ) {
            toastr[style](messages[i]);
        }

    } else {
        var messagesElement = jQuery("#messages-content");
        var blockStyle = "";
        if( style ) {
            if( style === "error" ) {
                style = "danger";
            }
            blockStyle = " alert-" + style;
        }
        var messageBlock = messagesElement.find(
            ".alert" + blockStyle.replace(' ', '.'));
        if( messageBlock.length === 0 ) {
            const blockText = "<div class=\"alert" + blockStyle
                  + " alert-dismissible fade show\">"
                  + "<button type=\"button\" class=\"btn-close\""
                  + " data-bs-dismiss=\"alert\" aria-label=\"Close\">"
                  + "</button></div>";
            var div = document.createElement('div');
            div.innerHTML = blockText;
            messageBlock = jQuery(div.firstChild);
        } else {
            messageBlock = jQuery(messageBlock[0].cloneNode(true));
            messageBlock.find('div').remove();
        }

        // insert the actual messages
        if( typeof messages === "string" ) {
            messages = [messages];
        }
        for( var i = 0; i < messages.length; ++i ) {
            messageBlock.append("<div>" + messages[i] + "</div>");
        }
        if( messageBlock.css('display') === 'none' ) {
            messageBlock.css('display', 'block');
        }
        messagesElement.append(messageBlock);
    }
    jQuery("#messages").removeClass("hidden");
    jQuery("html, body").animate({
        // scrollTop: jQuery("#messages").offset().top - 50
        // avoid weird animation when messages at the top:
        scrollTop: jQuery("body").offset().top
    }, 500);
};


/**
 Decorates elements when details exist, otherwise return messages to be shown
 globally.

 This method takes a `resp` argument as passed by jQuery ajax calls.
 */
function _showErrorMessages(resp) {
    var messages = [];
    if( typeof resp === "string" ) {
        messages = [resp];
    } else {
        var data = resp.data || resp.responseJSON;
        if( data && typeof data === "object" ) {
            if( data.detail ) {
                messages = [data.detail];
            } else if( $.isArray(data) ) {
                for( var idx = 0; idx < data.length; ++idx ) {
                    messages = messages.concat(_showErrorMessages(data[idx]));
                }
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
                        } else if( data[key].hasOwnProperty('detail') ) {
                            message = data[key].detail;
                        }
                        var inputField = jQuery("[name=\"" + key + "\"]");
                        var parent = inputField.parents('.form-group');
                        inputField.addClass("is-invalid");
                        parent.addClass("has-error");
                        var help = parent.find('.invalid-feedback');
                        if( help.length > 0 ) {
                            help.text(message);
                        } else {
                            messages.push(key + ": " + message);
                        }
                    }
                }
            }
        } else if( resp.detail ) {
            messages = [resp.detail];
        }
    }
    return messages;
};


function showErrorMessages(resp) {
    if( resp.status >= 500 && resp.status < 600 ) {
        msg = "Err " + resp.status + ": " + resp.statusText;
        if( _showErrorMessagesProviderNotified ) {
            msg += "<br />" + _showErrorMessagesProviderNotified;
        }
        messages = [msg];
    } else {
        var messages = _showErrorMessages(resp);
        if( messages.length === 0 ) {
            messages = ["Err " + resp.status + ": " + resp.statusText];
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
};

/** Retrieves an URL query argument.

    Example:

        window.location = getUrlParameter('next');
*/
function getUrlParameter(name) {
    name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
    var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    var results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
};

    // attach properties to the exports object to define
    // the exported module properties.
    exports.clearMessages = clearMessages;
    exports.showMessages = showMessages;
    exports.showErrorMessages = showErrorMessages;
    exports.getMetaCSRFToken = getMetaCSRFToken;
    exports.getUrlParameter = getUrlParameter;
}));
