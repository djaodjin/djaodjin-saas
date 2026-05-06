/** These are plumbing functions to connect the UI and API backends.
 */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define('djresources', ['exports'], factory);
    } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
        // CommonJS
        factory(exports);
    } else {
        // Browser true globals added to `window`.
        factory(root);
        // If we want to put the exports in a namespace, use the following line
        // instead.
        // factory((root.djresources = {}));
    }
}(typeof self !== 'undefined' ? self : this, function (exports) {


function _isArray(obj) {
    return obj instanceof Object && obj.constructor === Array;
}


function clearMessages(nodeId) {
    "use strict";
    if( nodeId ) {
        let elm = document.getElementById(nodeId + '-messages');
        elm.replaceChildren(); // Removes all children

        // removes decoration on the fields.
        elm = document.querySelector(nodeId + ' .has-error');
        if( elm ) {
            elm.classList.remove('has-error');
        }
        elm = document.querySelector(nodeId + ' .is-invalid');
        if( elm ) {
            elm = elm.classList.remove('is-invalid');
        }
        elm = document.querySelector(nodeId + ' .invalid-feedback');
        if( elm ) {
            elm.innerHTML = "";
        }
    } else {
        let elm = document.getElementById('messages-content');
        elm.replaceChildren(); // Removes all children

        // removes decoration on the fields.
        for( let elm of document.querySelectorAll('.has-error') ) {
            elm.classList.remove('has-error');
        }
        for( let elm of document.querySelectorAll('.is-invalid') ) {
            elm.classList.remove('is-invalid');
        }
        for( let elm of document.querySelectorAll('.invalid-feedback') ) {
            elm.innerHTML = "";
        }
    }
};

function showMessages(messages, style) {
    "use strict";
    if( typeof toastr !== 'undefined'
        && document.getElementById(toastr.options.containerId) ) {
        for( var i = 0; i < messages.length; ++i ) {
            toastr[style](messages[i]);
        }

    } else {
        const messagesElement = document.getElementById('messages-content');
        let blockStyle = "";
        if( style ) {
            if( style === "error" ) {
                style = "danger";
            }
            blockStyle = " alert-" + style;
        }
        let messageBlock = messagesElement.querySelector(
            ".alert" + blockStyle.replace(' ', '.'));
        if( !messageBlock ) {
            const blockText = "<div class=\"alert" + blockStyle
                  + " alert-dismissible fade show\">"
                  + "<button type=\"button\" class=\"btn-close\""
                  + " data-bs-dismiss=\"alert\" aria-label=\"Close\">"
                  + "</button></div>";
            let div = document.createElement('div');
            div.innerHTML = blockText;
            messageBlock = div.firstChild;
        } else {
            messageBlock = messageBlock.cloneNode(true);
            messageBlock.querySelectorAll('div').forEach(child => {
                child.remove();})
        }

        // insert the actual messages
        if( typeof messages === "string" ) {
            messages = [messages];
        }
        for( var i = 0; i < messages.length; ++i ) {
            const msgElm = document.createElement('div');
            msgElm.innerHTML = messages[i];
            messageBlock.appendChild(msgElm);
        }
        messagesElement.appendChild(messageBlock);
        const messageBlockStyle = window.getComputedStyle(messageBlock);

        if( messageBlockStyle.display === 'none' ) {
            messageBlock.style.display = 'block';
        }
    }
    const messagesElm = document.getElementById('messages');
    if( messagesElm ) messagesElm.classList.remove('hidden');
    const bodyElm = document.querySelector('body'); // XXX 'html, body'
    if( bodyElm ) {
        bodyElm.scrollIntoView();
    }
};


/**
 Decorates elements when details exist, otherwise return messages to be shown
 globally.

 This method takes a `resp` argument as passed by `fetch` calls.
 */
function _showErrorMessages(resp) {
    var messages = [];
    var hasContextMessages = false;
    if( typeof resp === "string" ) {
        messages = [resp];
    } else {
        var data = resp.data || resp.responseJSON;
        if( data && typeof data === "object" ) {
            if( _isArray(data) ) {
                for( var idx = 0; idx < data.length; ++idx ) {
                    messages = messages.concat(_showErrorMessages(data[idx]));
                }
            } else {
                for( var key in data ) {
                    if (data.hasOwnProperty(key)) {
                        var message = data[key];
                        if( _isArray(data[key]) ) {
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
                        var help = null;
                        var inputField = document.querySelector(
                            "[name=\"" + key + "\"]");
                        if( inputField ) {
                            inputField.classList.add("is-invalid");
                            const parent = inputField.closest('.form-group');
                            if( parent ) {
                                parent.classList.add("has-error");
                                help = parent.querySelector(
                                    '.invalid-feedback');
                            }
                        }
                        if( help ) {
                            help.textContent = message;
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
            self._isObject(arg) || _isArray(arg) ) {
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
        if( typeof url != 'string' && !_isArray(url) ) {
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

        const baseUrl = self._safeUrl(self.apiBase, args.url);
        const qualifiedUrl = baseUrl +
            (args.data ? ((baseUrl.lastIndexOf('?') > 0 ? '&' : '?') +
                (new URLSearchParams(args.data)).toString()) : '');
        fetch(qualifiedUrl, {
            method: "GET",
            headers: headers,
            credentials: 'include',
            traditional: true,
        }).then(async function(resp) {
            const clonedResp = resp.clone();
            try {
                resp.data = await resp.json();
            } catch(err) {
                // In case of error, we are not dealing with a nice
                // JSON-formatted `ValidationError` here.
                resp.data = await clonedResp.text();
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
    multiple: async function(elem, queryArray, arg, arg2, arg3) {
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

        try {
            const fetchPromises = args.url.map(arg => fetch(
                self._safeUrl(self.apiBase, arg.url), {
                    method: arg.method,
                    headers: headers,
                    body: arg.data ? JSON.stringify(arg.data) : null,
                    credentials: 'include',
                    traditional: true,
                }));
            const resps = await Promise.all(fetchPromises);
            for( const resp of resps ) {
                if( !resp.ok ) {
                    if( args.failureCallback ) {
                        args.failureCallback(...resps);
                    }
                    throw new Error(`HTTP status: ${resp.status}`);
                }
            }
            const jsonPromises = resps.map(resp => resp.json());
            const data = await Promise.all(jsonPromises);
            if( args.successCallback ) {
                args.successCallback(...data);
            }

        } catch( err ) {
            // We have already called `failureCallback` previously.
        }
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
