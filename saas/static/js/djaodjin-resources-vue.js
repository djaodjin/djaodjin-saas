/* Generic mixins for Vue.js */

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


const DESC_SORT_PRE = '-';


/** Displays notification messages to the user

     requires `jQuery`, _showErrorMessagesProviderNotified
     optional toastr
 */
var messagesMixin = {
    data: function() {
        return {
            messagesElement: '#messages-content',
            scrollToTopOnMessages: true,
        }
    },
    methods: {
        _isArray: function (obj) {
            return obj instanceof Object && obj.constructor === Array;
        },
        /**
           Decorates elements when details exist, otherwise return messages
           to be shown globally.

           This method takes a `resp` argument as passed by jQuery ajax calls.
        */
        _showErrorMessages: function (resp) {
            var vm = this;
            var messages = [];
            if( typeof resp === "string" ) {
                messages = [resp];
            } else {
                var data = resp.data || resp.responseJSON;
                if( data && typeof data === "object" ) {
                    if( data.detail ) {
                        messages = [data.detail];
                    } else if( vm._isArray(data) ) {
                        for( var idx = 0; idx < data.length; ++idx ) {
                            messages = messages.concat(vm._showErrorMessages(data[idx]));
                        }
                    } else {
                        for( var key in data ) {
                            if (data.hasOwnProperty(key)) {
                                var message = data[key];
                                if( vm._isArray(data[key]) ) {
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
                                messages.push(key + ": " + message);
                                var inputField = jQuery("[name=\"" + key + "\"]");
                                var parent = inputField.parents('.form-group');
                                inputField.addClass("is-invalid");
                                parent.addClass("has-error");
                                var help = parent.find('.invalid-feedback');
                                if( help.length > 0 ) { help.text(message); }
                            }
                        }
                    }
                } else if( resp.detail ) {
                    messages = [resp.detail];
                }
            }
            return messages;
        },
        clearMessages: function() {
            var vm = this;
            vm.getMessagesElement().empty();
        },
        getMessagesElement: function() {
            return jQuery(this.messagesElement);
        },
        showMessages: function (messages, style) {
            var vm = this;
            var messagesElement = vm.getMessagesElement();
            if( typeof toastr !== 'undefined'
                && $(toastr.options.containerId).length > 0 ) {
                for( var i = 0; i < messages.length; ++i ) {
                    toastr[style](messages[i]);
                }
            } else {
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
            var messagesContainer = messagesElement.parent();
            if( messagesContainer && messagesContainer.hasClass("hidden") ) {
                messagesContainer.removeClass("hidden");
            }
            if( vm.scrollToTopOnMessages ) {
                jQuery("html, body").animate({
                    // scrollTop: $("#messages").offset().top - 50
                    // avoid weird animation when messages at the top:
                    scrollTop: jQuery("body").offset().top
                }, 500);
            }
        },
        showErrorMessages: function (resp) {
            var vm = this;
            if( resp.status >= 500 && resp.status < 600 ) {
                msg = "Err " + resp.status + ": " + resp.statusText;
                if( _showErrorMessagesProviderNotified ) {
                    msg += "<br />" + _showErrorMessagesProviderNotified;
                }
                messages = [msg];
            } else {
                var messages = vm._showErrorMessages(resp);
                if( messages.length === 0 ) {
                    messages = ["Err " + resp.status + ": " + resp.statusText];
                }
            }
            vm.showMessages(messages, "error");
        },
    }
};


/** compute outdated based on `params`.

    `params = {start_at, ends_at}` must exist in either the `props` or `data`
    of the component.

    A subclass of this mixin must define either the function `autoReload`
    or `reload` in order to make updates as a user is typing in input fields
    or when a button is pressed respectively.
 */
var paramsMixin = {
    data: function(){
        var data = {
            lastGetParams: {},
        }
        return data;
    },
    methods: {
        asDateInputField: function(dateISOString) {
            const dateValue = moment(dateISOString);
            return dateValue.isValid() ? dateValue.format("YYYY-MM-DD") : null;
        },
        asDateISOString: function(dateInputField) {
            const dateValue = moment(dateInputField, "YYYY-MM-DD");
            return dateValue.isValid() ? dateValue.toISOString() : null;
        },
        autoReload: function() {
        },
        reload: function() {
        },
        getParams: function(excludes){
            var vm = this;
            var params = {};
            for( var key in vm.params ) {
                if( vm.params.hasOwnProperty(key) && vm.params[key] ) {
                    if( excludes && key in excludes ) continue;
                    params[key] = vm.params[key];
                }
            }
            return params;
        },
        getQueryString: function(excludes){
            var vm = this;
            var sep = "";
            var result = "";
            var params = vm.getParams(excludes);
            for( var key in params ) {
                if( params.hasOwnProperty(key) ) {
                    result += sep + key + '=' + encodeURIComponent(
                        params[key].toString());
                    sep = "&";
                }
            }
            if( result ) {
                result = '?' + result;
            }
            return result;
        },
    },
    computed: {
        _start_at: {
            get: function() {
                return this.asDateInputField(this.params.start_at);
            },
            set: function(newVal) {
                if( newVal ) {
                    // The setter might be call with `newVal === null`
                    // when the date is incorrect (ex: 09/31/2022).
                    this.$set(this.params, 'start_at',
                        this.asDateISOString(newVal));
                    if( this.outdated ) this.debouncedAutoReload();
                }
            }
        },
        _ends_at: {
            get: function() {
                // form field input="date" will expect ends_at as a String
                // but will literally cut the hour part regardless of timezone.
                // We don't want an empty list as a result.
                // If we use moment `endOfDay` we get 23:59:59 so we
                // add a full day instead. It seemed clever to run the following
                // code but that prevented entering the year part in the input
                // field (as oppossed to use the widget).
                //
                // const dateValue = moment(this.params.ends_at).add(1,'days');
                // return dateValue.isValid() ? dateValue.format("YYYY-MM-DD") : null;
                return this.asDateInputField(this.params.ends_at);
            },
            set: function(newVal) {
                if( newVal ) {
                    // The setter might be call with `newVal === null`
                    // when the date is incorrect (ex: 09/31/2022).
                    this.$set(this.params, 'ends_at',
                        this.asDateISOString(newVal));
                    if( this.outdated ) this.debouncedAutoReload();
                }
            }
        },
        outdated: function() {
            var vm = this;
            const params = vm.getParams();
            for( var key in vm.lastGetParams ) {
                if( vm.lastGetParams.hasOwnProperty(key) ) {
                    if( vm.lastGetParams[key] !== params[key] ) {
                        return true;
                    }
                }
            }
            for( var key in params ) {
                if( params.hasOwnProperty(key) ) {
                    if( params[key] !== vm.lastGetParams[key] ) {
                        return true;
                    }
                }
            }
            return false;
        }
    },
    created: function () {
        // _.debounce is a function provided by lodash to limit how
        // often a particularly expensive operation can be run.
        if( typeof _ != 'undefined' && typeof _.debounce != 'undefined' ) {
            this.debouncedAutoReload = _.debounce(this.autoReload, 500);
        } else {
            this.debouncedAutoReload = this.autoReload;
        }
    }
};


/** A wrapper around jQuery ajax functions that adds authentication
    parameters as necessary.

    requires `jQuery`
*/
var httpRequestMixin = {
    mixins: [
        messagesMixin,
        paramsMixin
    ],
// XXX conflitcs when params defined as props
//    data: function() {
//        return {
//            params: {}
//        }
//    },
    // basically a wrapper around jQuery ajax functions
    methods: {

        _isFunction: function (func){
            // https://stackoverflow.com/a/7356528/1491475
            return func && {}.toString.call(func) === '[object Function]';
        },

        _isObject: function (obj) {
            // https://stackoverflow.com/a/46663081/1491475
            return obj instanceof Object && obj.constructor === Object;
        },

        _getAuthToken: function() {
            return null; // XXX NotYetImplemented
        },

        _csrfSafeMethod: function(method) {
            // these HTTP methods do not require CSRF protection
            return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
        },

        _getCSRFToken: function() {
            var vm = this;
            // Look first for an input node in the HTML page, i.e.
            // <input type="hidden" name="csrfmiddlewaretoken"
            //     value="{{csrf_token}}">
            var crsfNode = vm.$el.querySelector("[name='csrfmiddlewaretoken']");
            if( crsfNode ) {
                return crsfNode.value;
            }
            // Then look for a CSRF token in the meta tags, i.e.
            // <meta name="csrf-token" content="{{csrf_token}}">
            var metas = document.getElementsByTagName('meta');
            for( var i = 0; i < metas.length; i++) {
                if (metas[i].getAttribute("name") == "csrf-token") {
                    return metas[i].getAttribute("content");
                }
            }
            return "";
        },

        _safeUrl: function(base, path) {
            if( !path ) return base;

            const parts = [base].concat(
                ( typeof path === 'string' ) ? [path] : path);
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
            return cleanUrl.startsWith('http') ? cleanUrl[0] : '/' + cleanUrl;
        },

        /** This method generates a GET HTTP request to `url` with a query
            string built of a `queryParams` dictionnary.

            It supports the following prototypes:

            - reqGet(url, successCallback)
            - reqGet(url, queryParams, successCallback)
            - reqGet(url, queryParams, successCallback, failureCallback)
            - reqGet(url, successCallback, failureCallback)

            `queryParams` when it is specified is a dictionnary
            of (key, value) pairs that is converted to an HTTP
            query string.

            `successCallback` and `failureCallback` must be Javascript
            functions (i.e. instance of type `Function`).
        */
        reqGet: function(url, arg, arg2, arg3){
            var vm = this;
            var queryParams, successCallback;
            var failureCallback = vm.showErrorMessages;
            if(typeof url != 'string') throw 'url should be a string';
            if(vm._isFunction(arg)){
                // We are parsing reqGet(url, successCallback)
                // or reqGet(url, successCallback, errorCallback).
                successCallback = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqGet(url, successCallback, errorCallback)
                    failureCallback = arg2;
                } else if( arg2 !== undefined ) {
                    throw 'arg2 should be a failureCallback function';
                }
            } else if(vm._isObject(arg)){
                // We are parsing
                // reqGet(url, queryParams, successCallback)
                // or reqGet(url, queryParams, successCallback, errorCallback).
                queryParams = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqGet(url, queryParams, successCallback)
                    // or reqGet(url, queryParams, successCallback, errorCallback).
                    successCallback = arg2;
                    if(vm._isFunction(arg3)){
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
            if( !url ) {
                vm.showErrorMessages(
                    "Attempting GET request for component '" +
                    vm.$options.name + "' but no url was set.");
            }
            return jQuery.ajax({
                method: 'GET',
                url: url,
                beforeSend: function(xhr, settings) {
                    var authToken = vm._getAuthToken();
                    if( authToken ) {
                        xhr.setRequestHeader("Authorization",
                            "Bearer " + authToken);
                    } else {
                        if( !vm._csrfSafeMethod(settings.type) ) {
                            var csrfToken = vm._getCSRFToken();
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
                data: queryParams,
                traditional: true,
                cache: false,       // force requested pages not to be cached
           }).done(successCallback).fail(failureCallback);
        },

        /** This method generates a POST HTTP request to `url` with
            contentType 'application/json'.

            It supports the following prototypes:

            - reqPOST(url, data)
            - reqPOST(url, data, successCallback)
            - reqPOST(url, data, successCallback, failureCallback)
            - reqPOST(url, successCallback)
            - reqPOST(url, successCallback, failureCallback)

            `data` when it is specified is a dictionnary of (key, value) pairs
            that is passed as a JSON encoded body.

            `successCallback` and `failureCallback` must be Javascript
            functions (i.e. instance of type `Function`).
        */
        reqPost: function(url, arg, arg2, arg3){
            var vm = this;
            var data, successCallback;
            var failureCallback = vm.showErrorMessages;
            if(typeof url != 'string') throw 'url should be a string';
            if(vm._isFunction(arg)){
                // We are parsing reqPost(url, successCallback)
                // or reqPost(url, successCallback, errorCallback).
                successCallback = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqPost(url, successCallback, errorCallback)
                    failureCallback = arg2;
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a failureCallback function';
                }
            } else if( vm._isObject(arg) || vm._isArray(arg) ) {
                // We are parsing reqPost(url, data)
                // or reqPost(url, data, successCallback)
                // or reqPost(url, data, successCallback, errorCallback).
                data = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqPost(url, data, successCallback)
                    // or reqPost(url, data, successCallback, errorCallback).
                    successCallback = arg2;
                    if(vm._isFunction(arg3)){
                        // We are parsing reqPost(url, data, successCallback, errorCallback)
                        failureCallback = arg3;
                    } else if (arg3 !== undefined){
                        throw 'arg3 should be a failureCallback function';
                    }
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a successCallback function';
                }
            } else if (arg !== undefined){
                throw 'arg should be a data Object or a successCallback function';
            }
            if( !url ) {
                vm.showErrorMessages(
                    "Attempting POST request for component '" +
                    vm.$options.name + "' but no url was set.");
            }
            return jQuery.ajax({
                method: 'POST',
                url: url,
                beforeSend: function(xhr, settings) {
                    var authToken = vm._getAuthToken();
                    if( authToken ) {
                        xhr.setRequestHeader("Authorization",
                            "Bearer " + authToken);
                    } else {
                        if( !vm._csrfSafeMethod(settings.type) ) {
                            var csrfToken = vm._getCSRFToken();
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
                contentType: 'application/json',
                data: JSON.stringify(data),
            }).done(successCallback).fail(failureCallback);
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
        reqPostBlob: function(url, form, arg2, arg3) {
            var vm = this;
            var successCallback;
            var failureCallback = vm.showErrorMessages;
            if(typeof url != 'string') throw 'url should be a string';
            if(vm._isFunction(arg2)){
                // We are parsing reqPostBlob(url, successCallback)
                // or reqPostBlob(url, successCallback, errorCallback).
                successCallback = arg2;
                if(vm._isFunction(arg3)){
                    // We are parsing
                    // reqPostBlob(url, successCallback, errorCallback)
                    failureCallback = arg3;
                } else if( arg3 !== undefined ) {
                    throw 'arg3 should be a failureCallback function';
                }
            } else if( arg2 !== undefined ) {
                throw 'arg2 should be successCallback function';
            }
            if( !url ) {
                vm.showErrorMessages(
                    "Attempting POST request for component '" +
                    vm.$options.name + "' but no url was set.");
            }
            return jQuery.ajax({
                method: 'POST',
                url: url,
                beforeSend: function(xhr, settings) {
                    var authToken = vm._getAuthToken();
                    if( authToken ) {
                        xhr.setRequestHeader("Authorization",
                            "Bearer " + authToken);
                    } else {
                        if( !vm._csrfSafeMethod(settings.type) ) {
                            var csrfToken = vm._getCSRFToken();
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
                contentType: false,
                processData: false,
                data: form,
            }).done(successCallback).fail(failureCallback);
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
        reqPut: function(url, arg, arg2, arg3){
            var vm = this;
            var data, successCallback;
            var failureCallback = vm.showErrorMessages;
            if(typeof url != 'string') throw 'url should be a string';
            if(vm._isFunction(arg)){
                // We are parsing reqPut(url, successCallback)
                // or reqPut(url, successCallback, errorCallback).
                successCallback = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqPut(url, successCallback, errorCallback)
                    failureCallback = arg2;
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a failureCallback function';
                }
            } else if(vm._isObject(arg)){
                // We are parsing reqPut(url, data)
                // or reqPut(url, data, successCallback)
                // or reqPut(url, data, successCallback, errorCallback).
                data = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqPut(url, data, successCallback)
                    // or reqPut(url, data, successCallback, errorCallback).
                    successCallback = arg2;
                    if(vm._isFunction(arg3)){
                        // We are parsing reqPut(url, data, successCallback, errorCallback)
                        failureCallback = arg3;
                    } else if (arg3 !== undefined){
                        throw 'arg3 should be a failureCallback function';
                    }
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a successCallback function';
                }
            } else if (arg !== undefined){
                throw 'arg should be a data Object or a successCallback function';
            }
            if( !url ) {
                vm.showErrorMessages(
                    "Attempting PUT request for component '" +
                    vm.$options.name + "' but no url was set.");
            }
            return jQuery.ajax({
                method: 'PUT',
                url: url,
                beforeSend: function(xhr, settings) {
                    var authToken = vm._getAuthToken();
                    if( authToken ) {
                        xhr.setRequestHeader("Authorization",
                            "Bearer " + authToken);
                    } else {
                        if( !vm._csrfSafeMethod(settings.type) ) {
                            var csrfToken = vm._getCSRFToken();
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
                contentType: 'application/json',
                data: JSON.stringify(data),
            }).done(successCallback).fail(failureCallback);
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
        reqPatch: function(url, arg, arg2, arg3){
            var vm = this;
            var data, successCallback;
            var failureCallback = vm.showErrorMessages;
            if(typeof url != 'string') throw 'url should be a string';
            if(vm._isFunction(arg)){
                // We are parsing reqPatch(url, successCallback)
                // or reqPatch(url, successCallback, errorCallback).
                successCallback = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqPatch(url, successCallback, errorCallback)
                    failureCallback = arg2;
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a failureCallback function';
                }
            } else if(vm._isObject(arg)){
                // We are parsing reqPatch(url, data)
                // or reqPatch(url, data, successCallback)
                // or reqPatch(url, data, successCallback, errorCallback).
                data = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqPatch(url, data, successCallback)
                    // or reqPatch(url, data, successCallback, errorCallback).
                    successCallback = arg2;
                    if(vm._isFunction(arg3)){
                        // We are parsing reqPatch(url, data, successCallback, errorCallback)
                        failureCallback = arg3;
                    } else if (arg3 !== undefined){
                        throw 'arg3 should be a failureCallback function';
                    }
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a successCallback function';
                }
            } else if (arg !== undefined){
                throw 'arg should be a data Object or a successCallback function';
            }
            if( !url ) {
                vm.showErrorMessages(
                    "Attempting PATCH request for component '" +
                    vm.$options.name + "' but no url was set.");
            }
            return jQuery.ajax({
                method: 'PATCH',
                url: url,
                beforeSend: function(xhr, settings) {
                    var authToken = vm._getAuthToken();
                    if( authToken ) {
                        xhr.setRequestHeader("Authorization",
                            "Bearer " + authToken);
                    } else {
                        if( !vm._csrfSafeMethod(settings.type) ) {
                            var csrfToken = vm._getCSRFToken();
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
                contentType: 'application/json',
                data: JSON.stringify(data),
            }).done(successCallback).fail(failureCallback);
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
        reqDelete: function(url, arg, arg2){
            var vm = this;
            var successCallback;
            var failureCallback = vm.showErrorMessages;
            if(typeof url != 'string') throw 'url should be a string';
            if(vm._isFunction(arg)){
                // We are parsing reqDelete(url, successCallback)
                // or reqDelete(url, successCallback, errorCallback).
                successCallback = arg;
                if(vm._isFunction(arg2)){
                    // We are parsing reqDelete(url, successCallback, errorCallback)
                    failureCallback = arg2;
                } else if (arg2 !== undefined){
                    throw 'arg2 should be a failureCallback function';
                }
            } else if (arg !== undefined){
                throw 'arg should be a successCallback function';
            }
            if( !url ) {
                vm.showErrorMessages(
                    "Attempting PATCH request for component '" +
                    vm.$options.name + "' but no url was set.");
            }
            return jQuery.ajax({
                method: 'DELETE',
                url: url,
                beforeSend: function(xhr, settings) {
                    var authToken = vm._getAuthToken();
                    if( authToken ) {
                        xhr.setRequestHeader("Authorization",
                            "Bearer " + authToken);
                    } else {
                        if( !vm._csrfSafeMethod(settings.type) ) {
                            var csrfToken = vm._getCSRFToken();
                            if( csrfToken ) {
                                xhr.setRequestHeader("X-CSRFToken", csrfToken);
                            }
                        }
                    }
                },
            }).done(successCallback).fail(failureCallback);
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
        reqMultiple: function(queryArray, successCallback, failureCallback) {
            var vm = this;
            var ajaxCalls = [];
            if( !successCallback ) {
                successCallback = function() {};
            }
            if( !failureCallback ) {
                failureCallback = vm.showErrorMessages;
            }
            for(var idx = 0; idx < queryArray.length; ++idx ) {
                ajaxCalls.push($.ajax({
                    method: queryArray[idx].method,
                    url: queryArray[idx].url,
                    data: JSON.stringify(queryArray[idx].data),
                    beforeSend: function(xhr, settings) {
                        var authToken = vm._getAuthToken();
                        if( authToken ) {
                            xhr.setRequestHeader("Authorization",
                                                 "Bearer " + authToken);
                        } else {
                            if( !vm._csrfSafeMethod(settings.type) ) {
                                var csrfToken = vm._getCSRFToken();
                                if( csrfToken ) {
                                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                                }
                            }
                        }
                    },
                    contentType: 'application/json',
                }));
            }
            jQuery.when.apply(jQuery, ajaxCalls).done(successCallback).fail(
                failureCallback);
        },
    }
}


var itemMixin = {
    mixins: [
        httpRequestMixin
    ],
    data: function() {
        return {
            item: {},
            itemLoaded: false,
        }
    },
    methods: {
        get: function(){
            var vm = this;
            if( !vm.url ) {
                vm.showErrorMessages(
                    "API endpoint to fetch an item for component '" +
                    vm.$options.name + "' is not configured.");
                return;
            }
            var cb = vm[vm.getCb];
            if( !cb ) {
                cb = function(res){
                    vm.item = res
                    vm.itemLoaded = true;
                }
            }
            vm.reqGet(vm.url, cb);
        },
        validateForm: function(){
            var vm = this;
            var isEmpty = true;
            var fields = jQuery(vm.$el).find('[name]').not(
                '[name="csrfmiddlewaretoken"]');
            for( var fieldIdx = 0; fieldIdx < fields.length; ++fieldIdx ) {
                var field = jQuery(fields[fieldIdx]);
                var fieldName = field.attr('name');
                var fieldValue = field.attr('type') === 'checkbox' ?
                    field.prop('checked') : field.val();
                if( vm.formFields[fieldName] !== fieldValue ) {
                    vm.formFields[fieldName] = fieldValue;
                }
                if( vm.formFields[fieldName] ) {
                    // We have at least one piece of information
                    // about the plan already available.
                    isEmpty = false;
                }
            }
            return !isEmpty;
        },
    },
}


var paginationMixin = {
    data: function(){
        return {
            params: {
                page: 1,
            },
            mergeResults: false,
            itemsPerPage: this.$itemsPerPage,
            ellipsisThreshold: 4,
            preReload: ['resetPage'],
            getCompleteCb: 'getCompleted',
            getBeforeCb: 'resetPage',
        }
    },
    methods: {
        resetPage: function(){
            var vm = this;
            vm.params.page = 1;
        },
        getCompleted: function(){
            var vm = this;
            vm.mergeResults = false;
        },
        handleScroll: function(evt) {
            var vm = this;
            let element = this.$el;
            if( element.getBoundingClientRect().bottom < window.innerHeight ) {
                let menubar = vm.$el.querySelector('[role="pagination"]');
                if( menubar) {
                    var style = window.getComputedStyle(menubar);
                    if( style.display == 'none' ) {
                        // We are not displaying the pagination menubar,
                        // so let's scroll!
                        vm.paginationHandler();
                    }
                }
            }
        },
        paginationHandler: function($state){
            var vm = this;
            if( !vm.itemsLoaded || vm.mergeResults ) {
                // this handler is triggered on initial get() too.
                return;
            }
            var nxt = vm.params.page + 1;
            if(nxt <= vm.pageCount){
                vm.$set(vm.params, 'page', nxt);
                vm.mergeResults = true;
                vm.get();
            }
        },
        // For pagination buttons
        onClick: function(pageNumber) {
            var vm = this;
            vm.$set(vm.params, 'page', pageNumber);
            vm.get();
        }
    },
    computed: {
        totalItems: function(){
            return this.items.count
        },
        pageCount: function(){
            // We use `max` here in case the API returns more elements
            // than specified in `itemsPerPage`.
            var nbFullPages = Math.ceil(this.totalItems / Math.max(
                this.items.results.length, this.itemsPerPage));
            if( nbFullPages * Math.max(this.items.results.length,
                this.itemsPerPage) < this.totalItems ) {
                ++nbFullPages;
            }
            return nbFullPages;
        },
        minDirectPageLink: function() {
            var vm = this;
            var halfEllipsisThreshold = Math.ceil(vm.ellipsisThreshold / 2);
            if( halfEllipsisThreshold * 2 == vm.ellipsisThreshold ) {
                --halfEllipsisThreshold;
            }
            var minDPL = Math.max(
                1, vm.params.page - halfEllipsisThreshold);
            var maxDPL = Math.min(
                vm.params.page + halfEllipsisThreshold, vm.pageCount);
            return ( maxDPL == vm.pageCount ) ? Math.max(
                vm.pageCount - vm.ellipsisThreshold + 1, 1) : minDPL;
        },
        maxDirectPageLink: function() {
            var vm = this;
            var halfEllipsisThreshold = Math.ceil(vm.ellipsisThreshold / 2);
            if( halfEllipsisThreshold * 2 == vm.ellipsisThreshold ) {
                --halfEllipsisThreshold;
            }
            var minDPL = Math.max(
                1, vm.params.page - halfEllipsisThreshold);
            var maxDPL = Math.min(
                vm.params.page + halfEllipsisThreshold, vm.pageCount);
            return ( minDPL == 1 ) ? Math.min(
                vm.ellipsisThreshold, vm.pageCount) : maxDPL;
        },
        directPageLinks: function() {
            var vm = this;
            var pages = [];
            for( var idx = vm.minDirectPageLink;
                 idx <= vm.maxDirectPageLink; ++idx ){
                pages.push(idx);
            }
            return pages;
        },
    },
    mounted: function() {
        var vm = this;
        window.addEventListener("scroll", vm.handleScroll);
    },
    unmounted: function () {
        window.removeEventListener("scroll", vm.handleScroll);
    }
}


var sortableMixin = {
    data: function(){
        var defaultDir = this.$sortDirection || 'desc';
        var dir = (defaultDir === 'desc') ? DESC_SORT_PRE : '';
        var o = this.$sortByField || 'created_at';
        return {
            params: {
                o: dir + o,
            },
            mixinSortCb: 'get'
        }
    },
    methods: {
        sortDir: function(field){
            return this.sortFields[field]
        },
        sortRemoveField: function(field){
            var vm = this;
            var fields = vm.sortFields;
            delete fields[field];
            vm.$set(vm.params, 'o', vm.fieldsToStr(fields));
        },
        sortRemove: function(){
            var vm = this;
            vm.$set(vm.params, 'o', '');
        },
        sortSet: function(field, dir) {
            var vm = this;
            var fields = vm.sortFields;
            var oldDir = fields[field];
            if(!oldDir || (oldDir && oldDir !== dir)){
                if(!(dir === 'asc' || dir === 'desc')){
                    // if no dir was specified - reverse
                    dir = oldDir === 'asc' ? 'desc' : 'asc';
                }
                fields[field] = dir;
                var o = vm.fieldsToStr(fields);
                vm.$set(vm.params, 'o', o);
                if(vm[vm.mixinSortCb]){
                    vm[vm.mixinSortCb]();
                }
            }
        },
        sortBy: function(field){
            var vm = this;
            var oldDir = vm.sortDir(field);
            vm.$set(vm.params, 'o', '');
            vm.sortSet(field, oldDir === 'asc' ? 'desc' : 'asc');
        },
        fieldsToStr: function(fields){
            var res = [];
            Object.keys(fields).forEach(function(key){
                var dir = fields[key];
                var field = '';
                if(dir === 'desc'){
                    field = DESC_SORT_PRE + key;
                } else {
                    field = key;
                }
                res.push(field);
            });
            return res.join(',');
        },
        sortIcon: function(fieldName){
            var res = 'fa fa-sort';
            var dir = this.sortDir(fieldName);
            if(dir){
                res += ('-' + dir);
            }
            return res;
        }
    },
    computed: {
        sortFields: function(){
            var vm = this;
            var res = {};
            if(vm.params.o){
                var fields = (typeof vm.params.o === 'string') ?
                    vm.params.o.split(',') : vm.params.o;
                fields.forEach(function(e){
                    if(!e) return;
                    if(e[0] === DESC_SORT_PRE){
                        res[e.substring(1)] = 'desc';
                    } else {
                        res[e] = 'asc';
                    }
                });
            }
            return res;
        },
    },
}


var itemListMixin = {
    mixins: [
        httpRequestMixin,
        paginationMixin,
        sortableMixin
    ],
    data: function(){
        return this.getInitData();
    },
    methods: {
        getInitData: function(){
            var data = {
                url: null,
                params: {
                    // The following dates will be stored as `String` objects
                    // as oppossed to `moment` or `Date` objects because this
                    // is how form fields input="date" will update them.
                    start_at: null,
                    ends_at: null,
                    // The timezone for both start_at and ends_at.
                    timezone: 'local',
                    q: '',
                },
                itemsLoaded: false,
                items: {
                    results: [],
                    count: 0
                },
                mergeResults: false,
                getCb: null,
                getCompleteCb: null,
                getBeforeCb: null,
            }
            if( this.$dateRange ) {
                if( this.$dateRange.start_at ) {
                    data.params['start_at'] = this.$dateRange.start_at;
                }
                if( this.$dateRange.ends_at ) {
                    data.params['ends_at'] = this.$dateRange.ends_at;
                }
                if( this.$dateRange.timezone ) {
                    data.params['timezone'] = this.$dateRange.timezone;
                }
            }
            return data;
        },
        get: function(){
            var vm = this;
            if( !vm.url ) {
                vm.showErrorMessages(
                    "API endpoint to fetch items for component '" +
                    vm.$options.name + "' is not configured.");
                return;
            }
            if(!vm.mergeResults){
                vm.itemsLoaded = false;
            }
            var cb = null;
            if(vm[vm.getCb]){
                cb = function(res){
                    vm[vm.getCb](res);

                    if(vm[vm.getCompleteCb]){
                        vm[vm.getCompleteCb]();
                    }
                }
            } else {
                cb = function(res){
                    if(vm.mergeResults){
                        res.results = vm.items.results.concat(res.results);
                    }
                    vm.items = res;
                    vm.itemsLoaded = true;

                    if( res.detail ) {
                        vm.showMessages([res.detail], "warning");
                    }

                    if(vm[vm.getCompleteCb]){
                        vm[vm.getCompleteCb]();
                    }
                }
            }
            if(vm[vm.getBeforeCb]){
                vm[vm.getBeforeCb]();
            }
            vm.fetch(cb);
        },
        fetch: function(cb) {
            let vm = this;
            vm.lastGetParams = vm.getParams();
            vm.reqGet(vm.url, vm.lastGetParams, cb);
        },
        reload: function() {
            let vm = this;
            for( let idx = 0; idx < vm.preReload.length; ++ idx ) {
                vm[vm.preReload[idx]]();
            }
            vm.get();
        },
    },
};


var typeAheadMixin = {
    mixins: [
        httpRequestMixin
    ],
    data: function data() {
        return {
            url: null,
            items: [],
            current: -1,
            loading: false,
            minChars: 4,
            query: '',
            queryParamName: 'q',
            selectFirst: false,
        };
    },
    methods: {
        activeClass: function activeClass(index) {
            return this.current === index ? " active" : "";
        },

        cancel: function() {},

        clear: function() {
            this.items = [];
            this.current = -1;
            this.loading = false;
        },

        down: function() {
            var vm = this;
            if( vm.current < vm.items.length - 1 ) {
                vm.current++;
            } else {
                vm.current = -1;
            }
        },

        hit: function() {
            var vm = this;
            if (vm.current !== -1) {
                vm.onHit(vm.items[vm.current]);
            }
        },

        onHit: function onHit() {
            console.warn('You need to implement the `onHit` method', this);
        },

        reset: function() {
            var vm = this;
            vm.clear();
            vm.query = '';
        },

        setActive: function(index) {
            var vm = this;
            vm.current = index;
        },

        up: function() {
            var vm = this;
            if (vm.current > 0) {
                vm.current--;
            } else if (vm.current === -1) {
                vm.current = vm.items.length - 1;
            } else {
                vm.current = -1;
            }
        },
        search: function() {
            this.update();
        },
        update: function() {
            var vm = this;
            vm.cancel();
            if (!vm.query) {
                return vm.reset();
            }
            if( vm.minChars && vm.query.length < vm.minChars ) {
                return;
            }
            vm.loading = true;
            var params = {};
            params[vm.queryParamName] = vm.query;
            vm.reqGet(vm.url, params,
            function (resp) {
                if (resp && vm.query) {
                    var data = resp.results;
                    data = vm.prepareResponseData ? vm.prepareResponseData(data) : data;
                    vm.items = vm.limit ? data.slice(0, vm.limit) : data;
                    vm.current = -1;
                    vm.loading = false;
                    if (vm.selectFirst) {
                        vm.down();
                    }
                }
            }, function() {
                // on failure we just do nothing. - i.e. we don't want a bunch
                // of error messages to pop up.
            });
        },
    },
    computed: {
        hasItems: function hasItems() {
            return this.items.length > 0;
        },
        isEmpty: function isEmpty() {
            return !this.query;
        },
        isDirty: function isDirty() {
            return !!this.query;
        }
    },
    mounted: function(){
        if( this.$el.dataset && this.$el.dataset.url ) {
            this.url = this.$el.dataset.url;
        }
    }
};

    // attach properties to the exports object to define
    // the exported module properties.
    exports.httpRequestMixin = httpRequestMixin;
    exports.itemListMixin = itemListMixin;
    exports.itemMixin = itemMixin;
    exports.messagesMixin = messagesMixin;
    exports.paramsMixin = paramsMixin;
    exports.typeAheadMixin = typeAheadMixin;
}));
