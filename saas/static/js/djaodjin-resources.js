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
    name = name.replace(/[\[]/g, '\\[').replace(/[\]]/g, '\\]');
    var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    var results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
};


const http = {

    apiBase: (typeof DJAOAPP_API_BASE_URL !== 'undefined' ?
        DJAOAPP_API_BASE_URL : '/api'),

    csrfToken: null,

    _isArray: function (obj) {
        return obj instanceof Object && obj.constructor === Array;
    },

    _isFunction: function (func){
        // https://stackoverflow.com/a/7356528/1491475
        return func && {}.toString.call(func) === '[object Function]';
    },

    _isObject: function (obj) {
        // https://stackoverflow.com/a/46663081/1491475
        return obj instanceof Object && obj.constructor === Object;
    },

    _getAuthToken: function() {
        return sessionStorage.getItem('authToken');
    },

    _csrfSafeMethod: function(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    },

    _getCSRFToken: function() {
        var self = this;
        if( !self.csrfToken ) {
            // If the csrfToken is not set, look for a CSRF token in the meta
            // tags, i.e. `<meta name="csrf-token" content="{{csrf_token}}">`.
            var metas = document.getElementsByTagName('meta');
            for( var i = 0; i < metas.length; i++) {
                if (metas[i].getAttribute("name") == "csrf-token") {
                    self.csrfToken = metas[i].getAttribute("content");
                    break;
                }
            }
        }
        return self.csrfToken;
    },

    /** This method generates a GET HTTP request to `url` with a query
        string built of a `queryParams` dictionnary.

        It supports the following prototypes:

        - get(url, successCallback)
        - get(url, queryParams, successCallback)
        - get(url, queryParams, successCallback, failureCallback)
        - get(url, successCallback, failureCallback)

        `queryParams` when it is specified is a dictionnary
        of (key, value) pairs that is converted to an HTTP
        query string.

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    get: function(url, arg, arg2, arg3) {
        var self = this;
        var queryParams, successCallback;
        var failureCallback = self.showErrorMessages;
        if( self._isFunction(arg) ) {
            // We are parsing reqGet(url, successCallback)
            // or reqGet(url, successCallback, errorCallback).
            successCallback = arg;
            if( self._isFunction(arg2) ) {
                // We are parsing reqGet(url, successCallback, errorCallback)
                failureCallback = arg2;
            } else if( arg2 !== undefined ) {
                throw 'arg2 should be a failureCallback function';
            }
        } else if( self._isObject(arg) ) {
            // We are parsing
            // reqGet(url, queryParams, successCallback)
            // or reqGet(url, queryParams, successCallback, errorCallback).
            queryParams = arg;
            if( self._isFunction(arg2) ) {
                // We are parsing reqGet(url, queryParams, successCallback)
                // or reqGet(url, queryParams, successCallback, errorCallback).
                successCallback = arg2;
                if( self._isFunction(arg3) ) {
                    // We are parsing reqGet(url, queryParams, successCallback, errorCallback)
                    failureCallback = arg3;
                } else if( arg3 !== undefined ){
                    throw 'arg3 should be a failureCallback function';
                }
            } else {
                throw 'arg2 should be a successCallback function';
            }
        } else {
            throw 'arg should be a queryParams Object or a successCallback function';
        }
        if(typeof url != 'string') throw 'url should be a string';
        if( !url ) {
            self.showErrorMessages(
                "Attempting GET request for component '" +
                    self.$options.name + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        }

        const resp = fetch(self.apiBase + ul, {
            method: "GET",
            headers: headers,
            data: queryParams,
            credentials: 'include',
            traditional: true,
            cache: false,       // force requested pages not to be cached
        }).then(function(resp) {

            if( !resp.ok ) {
                failureCallback(resp)
            }

            const result = resp.json();
            if( successCallback ) {
                successCallback(result);
            }
        });
    },


    /** This method generates a POST HTTP request to `url` with
        contentType 'application/json'.

        It supports the following prototypes:

        - post(url, data)
        - post(url, data, successCallback)
        - post(url, data, successCallback, failureCallback)
        - post(url, successCallback)
        - post(url, successCallback, failureCallback)

        `data` when it is specified is a dictionnary of (key, value) pairs
        that is passed as a JSON encoded body.

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    post: function(url, arg, arg2, arg3) {
        const self = this;

        var data, successCallback;
        var failureCallback = showErrorMessages;
        if( self._isFunction(arg) ) {
            // We are parsing reqPost(url, successCallback)
            // or reqPost(url, successCallback, errorCallback).
            successCallback = arg;
            if( self._isFunction(arg2) ) {
                // We are parsing reqPost(url, successCallback, errorCallback)
                failureCallback = arg2;
            } else if( arg2 !== undefined ) {
                throw 'arg2 should be a failureCallback function';
            }
        } else if( self._isObject(arg) || self._isArray(arg) ) {
            // We are parsing reqPost(url, data)
            // or reqPost(url, data, successCallback)
            // or reqPost(url, data, successCallback, errorCallback).
            data = arg;
            if( self._isFunction(arg2) ) {
                // We are parsing reqPost(url, data, successCallback)
                // or reqPost(url, data, successCallback, errorCallback).
                successCallback = arg2;
                if( self._isFunction(arg3) ) {
                    // We are parsing reqPost(url, data, successCallback, errorCallback)
                    failureCallback = arg3;
                } else if( arg3 !== undefined ) {
                    throw 'arg3 should be a failureCallback function';
                }
            } else if( arg2 !== undefined ) {
                throw 'arg2 should be a successCallback function';
            }
        } else if( arg !== undefined ) {
            throw 'arg should be a data Object or a successCallback function';
        }
        if(typeof url != 'string') throw 'url should be a string';
        if( !url ) {
            self.showErrorMessages(
                "Attempting POST request for component '" +
                    self.$options.name + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            const csrfToken = self._getCSRFToken();
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        fetch(self.apiBase + url, {
            method: "POST",
            credentials: 'include',
            headers: headers,
            body: JSON.stringify(data),
        }).then(function(resp) {

            if( !resp.ok ) {
                failureCallback(resp)
            }

            const result = resp.json();
            if( successCallback ) {
                successCallback(result);
            }
        });
    }
}

    // attach properties to the exports object to define
    // the exported module properties.
    exports.clearMessages = clearMessages;
    exports.showMessages = showMessages;
    exports.showErrorMessages = showErrorMessages;
    exports.getMetaCSRFToken = getMetaCSRFToken;
    exports.getUrlParameter = getUrlParameter;
    exports.http = http;
}));
