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

     requires `jQuery`, djaodjin-resources.js exports
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

        clearMessages: function() {
            var vm = this;
            vm.getMessagesElement().empty();
        },

        getMessagesElement: function() {
            return jQuery(this.messagesElement);
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
            const dateValue = new Date(dateISOString);
            // The `<input type="date">` element will accept dates
            // formatted as "YYYY-MM-DD".
            return !isNaN(dateValue) ?
                dateValue.toISOString().split('T')[0] : null;
        },
        asDateISOString: function(dateInputField) {
            const dateValue = new Date(dateInputField);
            return !isNaN(dateValue) ? dateValue.toISOString() : null;
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
                if( this.params.start_at ) {
                    return this.asDateInputField(this.params.start_at);
                }
                return null;
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
                if( this.params.ends_at ) {
                    return this.asDateInputField(this.params.ends_at);
                }
                return null;
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

        _safeUrl: function(base, path) {
            return djApi._safeUrl(base, path);
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
            return djApi.get(vm.$el, url, arg, arg2, arg3);
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
            return djApi.post(vm.$el, url, arg, arg2, arg3);
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
            return djApi.postBlob(vm.$el, url, form, arg2, arg3);
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
            return djApi.put(vm.$el, url, arg, arg2, arg3);
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
            return djApi.patch(vm.$el, url, arg, arg2, arg3);
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
            return djApi.delete(vm.$el, url, arg, arg2);
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
            return djApi.multiple(vm.$el, queryArray,
                successCallback, failureCallback);
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
                showErrorMessages(
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
            let element = vm.$el;
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
        var params = this.$sortByField ? {o: (dir + this.$sortByField)} : {};
        return {
            params: params,
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
                showErrorMessages(
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
                cb = function(resp){
                    if(vm.mergeResults){
                        resp.results = vm.items.results.concat(resp.results);
                    }
                    for( var key in resp ) {
                        if( resp.hasOwnProperty(key) ) {
                            vm.items[key] = resp[key];
                        }
                    }
                    vm.itemsLoaded = true;

                    if( resp.detail ) {
                        showMessages([resp.detail], "warning");
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

        highlightQuery: function(text) {
            var vm = this;
            if( !vm.query ) {
                return text;
            }
            let regex = new RegExp(vm.query, "gi"); // search for all instances
            let newText = text.replace(regex, `<mark>$&</mark>`);
            return newText;
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

        onHit: function(item) {
            console.warn('You need to implement the `onHit` method', this);
        },

        reset: function() {
            var vm = this;
            vm.clear();
            vm.query = '';
            vm.$nextTick(function() {
                var inputs = vm.$refs.input;
                if( typeof inputs.length != 'undefined' ) {
                    if( inputs.length > 0 ) {
                        inputs[0].focus();
                    }
                } else {
                    inputs.focus();
                }
            });
            vm.$emit('typeaheadreset');
        },
        resetAndReload: function() {
            var vm = this;
            vm.reset();
            vm.reload();
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
        reload: function() {
            var vm = this;
            vm.loading = true;
            var params = {};
            params[vm.queryParamName] = vm.query;
            vm.reqGet(vm.url, params,
            function (resp) {
                const data = vm.prepareResponseData ?
                    vm.prepareResponseData(resp.results) : resp.results;
                vm.items = vm.limit ? data.slice(0, vm.limit) : data;
                vm.current = -1;
                vm.loading = false;
                vm.$nextTick(function() {
                    var inputs = vm.$refs.input;
                    if( inputs.length > 0 ) {
                        inputs[0].focus();
                    }
                    if (vm.selectFirst) {
                        vm.down();
                    }
                });
            }, function() {
                // on failure we just do nothing. - i.e. we don't want a bunch
                // of error messages to pop up.
            });
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
            vm.reload();
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


/** Mixin to load profile or user details from the profile APIs
 */
var accountDetailMixin = {
    data: function() {
        return {
            api_accounts_url: this.$urls.api_accounts,
            accountsBySlug: {}
        }
    },
    methods: {
        getAccountField: function(account, fieldName) {
            var vm = this;
            if( account ) {
                let fieldValue = account.hasOwnProperty(fieldName) ?
                    account[fieldName] : null;
                if( fieldValue ) {
                    return fieldValue;
                }
                const accountSlug = account.slug ? account.slug : account;
                const cached = vm.accountsBySlug[accountSlug];
                if( cached && cached.hasOwnProperty(fieldName) ) {
                    return cached[fieldName];
                }
                // XXX disable loading individually. we need to give
                // `populateAccounts` a chance to run and complete.
                if( false && vm.api_accounts_url ) {
                    vm.accountsBySlug[accountSlug] = {
                        picture: null,
                        printable_name: accountSlug
                    };
                    vm.reqGet(vm._safeUrl(vm.api_accounts_url, accountSlug),
                    function(resp) {
                        vm.accountsBySlug[resp.slug] = resp;
                    }, function() {
                        // discard errors (ex: "not found").
                    });
                }
            }
            // If we don't return `undefined` here, we might inadvertently
            // post initialized fields (null, or "") in HTTP requests.
            return undefined;
        },
        getAccountPicture: function(account) {
            return this.getAccountField(account, 'picture');
        },
        getAccountPrintableName: function(account) {
            return this.getAccountField(account, 'printable_name');
        },
        populateAccounts: function(elements, fieldName) {
            var vm = this;
            if( !vm.api_accounts_url ) return;

            if( !fieldName ) {
                fieldName = 'slug';
            }

            const accounts = new Set();
            for( let idx = 0; idx < elements.length; ++idx ) {
                const item = elements[idx];
                accounts.add((fieldName && item[fieldName]) ?
                    item[fieldName] : item);
            }
            if( accounts.size ) {
                let queryParams = "?q_f==slug&q=";
                let sep = "";
                for( const account of accounts ) {
                    queryParams += sep + account;
                    sep = ",";
                }
                vm.reqGet(vm.api_accounts_url + queryParams,
                function(resp) {
                    for( let idx = 0; idx < resp.results.length; ++idx ) {
                        vm.$set(vm.accountsBySlug, resp.results[idx].slug,
                            resp.results[idx]);
                    }
                    vm.$forceUpdate();
                }, function() {
                    // discard errors (ex: "not found").
                });
            }
        },
    }
};

/** Mixin to load user details from the profile APIs
 */
var userDetailMixin = {
    data: function() {
        return {
            api_users_url: this.$urls.api_users,
            usersBySlug: {}
        }
    },
    methods: {
        getUserField: function(user, fieldName) {
            var vm = this;
            if( user ) {
                let fieldValue = user.hasOwnProperty(fieldName) ?
                    user[fieldName] : null;
                if( fieldValue ) {
                    return fieldValue;
                }
                const userSlug = user.slug ? user.slug : user;
                const cached = vm.usersBySlug[userSlug];
                if( cached && cached.hasOwnProperty(fieldName) ) {
                    return cached[fieldName];
                }
                // XXX disable loading individually. we need to give
                // `populateUsers` a chance to run and complete.
                if( false && vm.api_users_url ) {
                    vm.usersBySlug[userSlug] = {
                        picture: null,
                        printable_name: userSlug
                    };
                    vm.reqGet(vm._safeUrl(vm.api_users_url, userSlug),
                    function(resp) {
                        vm.usersBySlug[resp.slug] = resp;
                    }, function() {
                        // discard errors (ex: "not found").
                    });
                }
            }
            return "";
        },
        getUserPicture: function(user) {
            return this.getUserField(user, 'picture');
        },
        getUserPrintableName: function(user) {
            return this.getUserField(user, 'printable_name');
        },
        populateUsers: function(elements, fieldName) {
            var vm = this;
            if( !vm.api_users_url ) return;

            if( !fieldName ) {
                fieldName = 'slug';
            }

            const users = new Set();
            for( let idx = 0; idx < elements.length; ++idx ) {
                const item = elements[idx];
                users.add((fieldName && item[fieldName]) ?
                    item[fieldName] : item.slug);
            }
            if( users.size ) {
                let queryParams = "?q_f==slug&q=";
                let sep = "";
                for( const user of users ) {
                    queryParams += sep + user;
                    sep = ",";
                }
                vm.reqGet(vm.api_users_url + queryParams,
                function(resp) {
                    for( let idx = 0; idx < resp.results.length; ++idx ) {
                        vm.$set(vm.usersBySlug, resp.results[idx].slug,
                            resp.results[idx]);
                    }
                    vm.$forceUpdate();
                }, function() {
                    // discard errors (ex: "not found").
                });
            }
        },
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
    exports.accountDetailMixin = accountDetailMixin;
    exports.userDetailMixin = userDetailMixin;
}));
