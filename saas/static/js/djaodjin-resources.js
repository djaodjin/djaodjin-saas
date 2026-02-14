/** These are plumbing functions to connect the UI and API backends.
 */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define('djaodjinResources', ['exports', 'jQuery'], factory);
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

    // removes decoration on the fields.
    jQuery(".form-group.has-error").removeClass("has-error");
    jQuery(".is-invalid").removeClass("is-invalid");
    jQuery(".invalid-feedback").text("");
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
    var hasContextMessages = false;
    if( typeof resp === "string" ) {
        messages = [resp];
    } else {
        var data = resp.data || resp.responseJSON;
        if( data && typeof data === "object" ) {
            if( jQuery.isArray(data) ) {
                for( var idx = 0; idx < data.length; ++idx ) {
                    messages = messages.concat(_showErrorMessages(data[idx]));
                }
            } else {
                for( var key in data ) {
                    if (data.hasOwnProperty(key)) {
                        var message = data[key];
                        if( jQuery.isArray(data[key]) ) {
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
                            hasContextMessages = true;
                        } else {
                            if( key === 'detail' ) {
                                messages.push(message);
                            } else {
                                messages.push(key + ": " + message);
                            }
                        }
                    }
                }
            }
        } else if( resp.detail ) {
            messages = [resp.detail];
        }
    }
    if( messages.length === 0 ) {
        if( hasContextMessages ) {
            if( typeof _showErrorMessagesOnFields !== 'undefined' &&
                _showErrorMessagesOnFields ) {
                messages = [_showErrorMessagesOnFields];
            }
        } else {
            messages = ["Err " + resp.status + ": " + resp.statusText];
        }
    }
    return messages;
};


function showErrorMessages(resp) {
    var messages = [];
    if( resp.status >= 500 && resp.status < 600 ) {
        msg = "Err " + resp.status + ": " + resp.statusText;
        if( typeof _showErrorMessagesProviderNotified !== 'undefined' &&
            _showErrorMessagesProviderNotified ) {
            msg += "<br />" + _showErrorMessagesProviderNotified;
        }
        messages = [msg];
    } else {
        messages = _showErrorMessages(resp);
    }
    if( messages.length > 0 ) {
        showMessages(messages, "error");
    }
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
    let urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
};


const djApi = {

    apiBase: '',
    defaultCSRFToken: null,

    _csrfSafeMethod: function(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    },

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

    _getCSRFToken: function(elem) {
        var self = this;
        if( elem ) {
            // Look first for an input node in the HTML page, i.e.
            // <input type="hidden" name="csrfmiddlewaretoken"
            //     value="{{csrf_token}}">
            var crsfNode = elem.querySelector("[name='csrfmiddlewaretoken']");
            if( crsfNode ) {
                return crsfNode.value;
            }
        }
        // If the csrfToken is not set, look for a CSRF token in the meta
        // tags, i.e. `<meta name="csrf-token" content="{{csrf_token}}">`.
        var metas = document.getElementsByTagName('meta');
        for( var i = 0; i < metas.length; i++) {
            if (metas[i].getAttribute("name") == "csrf-token") {
                return metas[i].getAttribute("content");
            }
        }
        return self.defaultCSRFToken;
    },

    __parseCallArguments: function(args, arg, arg2, arg3) {
        var self = this;
        if( self._isFunction(arg) ) {
            // We are dealing with either:
            // - http(elem, url, success)
            // - http(elem, url, success, fail)
            // - http(url, success)
            // - http(url, success, fail)
            args['successCallback'] = arg;
            if( self._isFunction(arg2) ) {
                // We are dealing with either:
                // - http(elem, url, success, fail)
                // - http(url, success, fail)
                args['failureCallback'] = arg2;
            }
        } else if( arg instanceof FormData ||
            self._isObject(arg) || self._isArray(arg) ) {
            // We are dealing with either:
            // - http(elem, url, data)
            // - http(elem, url, data, success)
            // - http(elem, url, data, success, fail)
            // - http(url, data)
            // - http(url, data, success)
            // - http(url, data, success, fail)
            args['data'] = arg;
            if( self._isFunction(arg2) ) {
                // - http(elem, url, data, success)
                // - http(elem, url, data, success, fail)
                // - http(url, data, success)
                // - http(url, data, success, fail)
                args['successCallback'] = arg2;
                if( self._isFunction(arg3) ) {
                    // We are dealing with either:
                    // - http(elem, url, data, success, fail)
                    // - http(url, data, success, fail)
                    args['failureCallback'] = arg3;
                }
            }
        }
        return args;
    },

    _parseCallArguments: function(elem, url, arg, arg2, arg3) {
        var self = this;
        var args = {
            elem: null, url: null, data: null,
            successCallback: null, failureCallback: showErrorMessages
        };
        if( typeof elem == 'string' ) {
            // We are dealing with either:
            // - http(url)
            // - http(url, data)
            // - http(url, data, success)
            // - http(url, data, success, fail)
            args['url'] = elem;
            return self.__parseCallArguments(args, url, arg, arg2);
        }
        // We are dealing with either:
        // - http(elem, url)
        // - http(elem, url, data)
        // - http(elem, url, data, success)
        // - http(elem, url, data, success, fail)
        args['elem'] = elem;
        if( typeof url != 'string' && !self._isArray(url) ) {
            throw '`url` should be a string or an array of ajax queries';
        }
        args['url'] = url;
        return self.__parseCallArguments(args, arg, arg2, arg3);
    },

    _safeUrl: function(base, path) {
        if( !path ) return base;
        if( typeof path === 'string' && (
            path.startsWith('http') || (
                base.length > 0 && path.startsWith(base))) ) return path;

        const parts = base ? [base].concat(
            ( typeof path === 'string' ) ? [path] : path) :
              (( typeof path === 'string' ) ? [path] : path);
        var cleanParts = [];
        var start, end;
        for( var idx = 0; idx < parts.length; ++idx ) {
            const part = parts[idx];
            for( start = 0; start < part.length; ++start ) {
                if( part[start] !== '/') {
                    break;
                }
            }
            for( end = part.length - 1; end >= 0; --end ) {
                if( part[end] !== '/') {
                    break;
                }
            }
            if( start < end ) {
                cleanParts.push(part.slice(start, end + 1));
            } else {
                cleanParts.push(part);
            }
        }

        var cleanUrl = cleanParts[0];
        for( idx = 1; idx < cleanParts.length; ++idx ) {
            cleanUrl += '/' + cleanParts[idx];
        }
        // We need to keep the '/' suffix when dealing
        // with djaodjin-rules API calls.
        if( path.endsWith('/') ) cleanUrl += '/';

        if( !cleanUrl.startsWith('http') && !cleanUrl.startsWith('/') ) {
            cleanUrl = '/' + cleanUrl
        }

        return cleanUrl;
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
    get: function(elem, url, arg, arg2, arg3) {
        var self = this;
        const args = self._parseCallArguments(elem, url, arg, arg2, arg3);
        if( !args.url ) {
            showErrorMessages(
                "Attempting GET request for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        }

        const qualifiedUrl = self._safeUrl(self.apiBase, args.url) + (
            args.data ? '?' + (new URLSearchParams(args.data)).toString() : '');
        fetch(qualifiedUrl, {
            method: "GET",
            headers: headers,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
            }
            if( !resp.ok ) {
                args.failureCallback(resp)
            } else if( args.successCallback ) {
                args.successCallback(resp.data, resp.statusText, resp);
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
    post: function(elem, url, arg, arg2, arg3) {
        const self = this;
        const args = self._parseCallArguments(elem, url, arg, arg2, arg3);
        if( !args.url ) {
            showErrorMessages(
                "Attempting POST request for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            const csrfToken = self._getCSRFToken(args.elem);
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        fetch(self._safeUrl(self.apiBase, args.url), {
            method: "POST",
            headers: headers,
            body: args.data ? JSON.stringify(args.data) : null,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
            }
            if( !resp.ok ) {
                args.failureCallback(resp)
            } else if( args.successCallback ) {
                args.successCallback(resp.data, resp.statusText, resp);
            }
        });
    },

    /** This method generates a POST HTTP request to `url` with
        data encoded as multipart/form-data.

        It supports the following prototypes:

        - reqPOSTBlob(url, data)
        - reqPOSTBlob(url, data, successCallback)
        - reqPOSTBlob(url, data, successCallback, failureCallback)

        `data` is a `FormData` that holds a binary blob.

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    postBlob: function(elem, url, form, arg2, arg3) {
        const self = this;
        const args = self._parseCallArguments(elem, url, form, arg2, arg3);
        if( !url ) {
            showErrorMessages(
                "Attempting POST request for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
//            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            const csrfToken = self._getCSRFToken(args.elem);
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        fetch(self._safeUrl(self.apiBase, args.url), {
            method: "POST",
            headers: headers,
            contentType: false,
            processData: false,
            body: args.data,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
            }
            if( !resp.ok ) {
                args.failureCallback(resp)
            } else if( args.successCallback ) {
                args.successCallback(resp.data, resp.statusText, resp);
            }
        });
    },

    /** This method generates a PUT HTTP request to `url` with
        contentType 'application/json'.

        It supports the following prototypes:

        - reqPUT(url, data)
        - reqPUT(url, data, successCallback)
        - reqPUT(url, data, successCallback, failureCallback)
        - reqPUT(url, successCallback)
        - reqPUT(url, successCallback, failureCallback)

        `data` when it is specified is a dictionnary of (key, value) pairs
        that is passed as a JSON encoded body.

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    put: function(elem, url, arg, arg2, arg3){
        const self = this;
        const args = self._parseCallArguments(elem, url, arg, arg2, arg3);
        if( !args.url ) {
            showErrorMessages(
                "Attempting PUT request for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            const csrfToken = self._getCSRFToken(args.elem);
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        fetch(self._safeUrl(self.apiBase, args.url), {
            method: "PUT",
            headers: headers,
            body: args.data ? JSON.stringify(args.data) : null,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
            }
            if( !resp.ok ) {
                args.failureCallback(resp)
            } else if( args.successCallback ) {
                args.successCallback(resp.data, resp.statusText, resp);
            }
        });
    },

    /** This method generates a PATCH HTTP request to `url` with
        contentType 'application/json'.

        It supports the following prototypes:

        - reqPATCH(url, data)
        - reqPATCH(url, data, successCallback)
        - reqPATCH(url, data, successCallback, failureCallback)
        - reqPATCH(url, successCallback)
        - reqPATCH(url, successCallback, failureCallback)

        `data` when it is specified is a dictionnary of (key, value) pairs
        that is passed as a JSON encoded body.

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    patch: function(elem, url, arg, arg2, arg3) {
        const self = this;
        const args = self._parseCallArguments(elem, url, arg, arg2, arg3);
        if( !args.url ) {
            showErrorMessages(
                "Attempting PATCH request for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            const csrfToken = self._getCSRFToken(args.elem);
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        fetch(self._safeUrl(self.apiBase, args.url), {
            method: "PATCH",
            headers: headers,
            body: args.data ? JSON.stringify(args.data) : null,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
            }
            if( !resp.ok ) {
                args.failureCallback(resp)
            } else if( args.successCallback ) {
                args.successCallback(resp.data, resp.statusText, resp);
            }
        });
    },

    /** This method generates a DELETE HTTP request to `url` with a query
        string built of a `queryParams` dictionnary.

        It supports the following prototypes:

        - reqDELETE(url)
        - reqDELETE(url, successCallback)
        - reqDELETE(url, successCallback, failureCallback)

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    delete: function(elem, url, arg, arg2) {
        const self = this;
        const args = self._parseCallArguments(elem, url, arg, arg2);
        if( !args.url ) {
            showErrorMessages(
                "Attempting DELETE request for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            const csrfToken = self._getCSRFToken(args.elem);
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        fetch(self._safeUrl(self.apiBase, args.url), {
            method: "DELETE",
            headers: headers,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
            }
            if( !resp.ok ) {
                args.failureCallback(resp)
            } else if( args.successCallback ) {
                args.successCallback(resp.data, resp.statusText, resp);
            }
        });
    },

    /** This method generates multiple queries, and execute
        success/failure callbacks when all have completed.

        It supports the following prototypes:

        - reqMultiple(queryArray)
        - reqMultiple(queryArray, successCallback)
        - reqMultiple(queryArray, successCallback, failureCallback)

        `successCallback` and `failureCallback` must be Javascript
        functions (i.e. instance of type `Function`).
    */
    multiple: function(elem, queryArray, arg, arg2, arg3) {
        const self = this;
        const args = self._parseCallArguments(
            elem, queryArray, arg, arg2, arg3);
        if( !args.url ) {
            showErrorMessages(
                "Attempting multiple requests for component '" +
                    args.elem + "' but no url was set.");
        }

        let headers = {
            "Content-Type": "application/json",
        };
        const authToken = self._getAuthToken();
        const csrfToken = self._getCSRFToken(args.elem);
        if( authToken ) {
            headers['Authorization'] = "Bearer " + authToken;
        } else {
            if( csrfToken ) {
                headers['X-CSRFToken'] = csrfToken;
            }
        }

        var ajaxCalls = [];
        for(var idx = 0; idx < args.url.length; ++idx ) {
            ajaxCalls.push(jQuery.ajax({
                method: args.url[idx].method,
                url: self._safeUrl(self.apiBase, args.url[idx].url),
                data: JSON.stringify(args.url[idx].data),
                beforeSend: function(xhr, settings) {
                    if( authToken ) {
                        xhr.setRequestHeader(
                            "Authorization", "Bearer " + authToken);
                    } else {
                        if( !self._csrfSafeMethod(settings.type) ) {
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
                contentType: 'application/json',
            }));
        }
        jQuery.when.apply(jQuery, ajaxCalls).done(args.successCallback).fail(
            args.failureCallback);
    }

};

    // attach properties to the exports object to define
    // the exported module properties.
    exports.clearMessages = clearMessages;
    exports.showMessages = showMessages;
    exports.showErrorMessages = showErrorMessages;
    exports.getMetaCSRFToken = getMetaCSRFToken;
    exports.getUrlParameter = getUrlParameter;
    exports.djApi = djApi;
}));
