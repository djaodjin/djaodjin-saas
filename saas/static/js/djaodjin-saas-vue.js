function getInitValue(form, fieldName) {
    if( form.length > 0 ) {
        var field = form.find("[name='" + fieldName + "']");
        if( field.length > 0 ) {
            var val = field.val();
            if( !val ) {
                val = field.data('init');
            }
            return val;
        }
    }
    return "";
}

Vue.use(uiv, {prefix: 'uiv'});

Vue.filter('formatDate', function(value, format) {
  if (value) {
    if(!format){
//        format = 'MM/DD/YYYY hh:mm'
        format = "MMM D, YYYY";
    }
    if(!(value instanceof Date)){
        value = String(value);
    }
    return moment(value).format(format)
  }
});

Vue.filter("monthHeading", function(d) {
    // shift each period by 1 month unless this is
    // current month and not a first day of the month
    if( typeof d === 'string' ) {
        d = moment(d);
    }
    if(d.date() !== 1 || d.hour() !== 0
       || d.minute() !== 0 || d.second() !== 0 ) {
        return d.format("MMM'YY*");
    }
    return d.clone().subtract(1, 'months').format("MMM'YY");
});

Vue.filter('currencyToSymbol', function(currency) {
    if( currency === "usd" || currency === "cad" ) { return "$"; }
    else if( currency === "eur" ) { return "\u20ac"; }
    return currency;
});

Vue.filter('humanizeCell', function(cell, unit, scale) {
    var currencyFilter = Vue.filter('currency');
    var currencyToSymbolFilter = Vue.filter('currencyToSymbol');
    scale = scale || 1;
    var value = cell * scale;
    var symbol = '';
    var precision = 0;
    if(unit) {
        symbol = currencyToSymbolFilter(unit);
        precision = 2;
    }
    return currencyFilter(value, symbol, precision);
});

Vue.filter('relativeDate', function(at_time) {
    var cutOff = new Date();
    if(this.ends_at ) {
        cutOff = new Date(this.ends_at);
    }
    var dateTime = new Date(at_time);
    if( dateTime <= cutOff ) {
        return moment.duration(cutOff - dateTime).humanize() + " " + gettext('ago');
    } else {
        return moment.duration(dateTime - cutOff).humanize() + " " + gettext('left');
    }
});

var countries = {
    "AF": "Afghanistan",
    "AX": "Åland Islands",
    "AL": "Albania",
    "DZ": "Algeria",
    "AS": "American Samoa",
    "AD": "Andorra",
    "AO": "Angola",
    "AI": "Anguilla",
    "AQ": "Antarctica",
    "AG": "Antigua and Barbuda",
    "AR": "Argentina",
    "AM": "Armenia",
    "AW": "Aruba",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaijan",
    "BS": "Bahamas",
    "BH": "Bahrain",
    "BD": "Bangladesh",
    "BB": "Barbados",
    "BY": "Belarus",
    "BE": "Belgium",
    "BZ": "Belize",
    "BJ": "Benin",
    "BM": "Bermuda",
    "BT": "Bhutan",
    "BO": "Bolivia (Plurinational State of)",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BA": "Bosnia and Herzegovina",
    "BW": "Botswana",
    "BV": "Bouvet Island",
    "BR": "Brazil",
    "IO": "British Indian Ocean Territory",
    "BN": "Brunei Darussalam",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "CV": "Cabo Verde",
    "KH": "Cambodia",
    "CM": "Cameroon",
    "CA": "Canada",
    "KY": "Cayman Islands",
    "CF": "Central African Republic",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CX": "Christmas Island",
    "CC": "Cocos (Keeling) Islands",
    "CO": "Colombia",
    "KM": "Comoros",
    "CD": "Congo (the Democratic Republic of the)",
    "CG": "Congo",
    "CK": "Cook Islands",
    "CR": "Costa Rica",
    "CI": "Côte d'Ivoire",
    "HR": "Croatia",
    "CU": "Cuba",
    "CW": "Curaçao",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DK": "Denmark",
    "DJ": "Djibouti",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "EC": "Ecuador",
    "EG": "Egypt",
    "SV": "El Salvador",
    "GQ": "Equatorial Guinea",
    "ER": "Eritrea",
    "EE": "Estonia",
    "SZ": "Eswatini",
    "ET": "Ethiopia",
    "FK": "Falkland Islands  [Malvinas]",
    "FO": "Faroe Islands",
    "FJ": "Fiji",
    "FI": "Finland",
    "FR": "France",
    "GF": "French Guiana",
    "PF": "French Polynesia",
    "TF": "French Southern Territories",
    "GA": "Gabon",
    "GM": "Gambia",
    "GE": "Georgia",
    "DE": "Germany",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GR": "Greece",
    "GL": "Greenland",
    "GD": "Grenada",
    "GP": "Guadeloupe",
    "GU": "Guam",
    "GT": "Guatemala",
    "GG": "Guernsey",
    "GN": "Guinea",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HT": "Haiti",
    "HM": "Heard Island and McDonald Islands",
    "VA": "Holy See",
    "HN": "Honduras",
    "HK": "Hong Kong",
    "HU": "Hungary",
    "IS": "Iceland",
    "IN": "India",
    "ID": "Indonesia",
    "IR": "Iran (Islamic Republic of)",
    "IQ": "Iraq",
    "IE": "Ireland",
    "IM": "Isle of Man",
    "IL": "Israel",
    "IT": "Italy",
    "JM": "Jamaica",
    "JP": "Japan",
    "JE": "Jersey",
    "JO": "Jordan",
    "KZ": "Kazakhstan",
    "KE": "Kenya",
    "KI": "Kiribati",
    "KP": "Korea (the Democratic People's Republic of)",
    "KR": "Korea (the Republic of)",
    "KW": "Kuwait",
    "KG": "Kyrgyzstan",
    "LA": "Lao People's Democratic Republic",
    "LV": "Latvia",
    "LB": "Lebanon",
    "LS": "Lesotho",
    "LR": "Liberia",
    "LY": "Libya",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "MO": "Macao",
    "MK": "Macedonia (the former Yugoslav Republic of)",
    "MG": "Madagascar",
    "MW": "Malawi",
    "MY": "Malaysia",
    "MV": "Maldives",
    "ML": "Mali",
    "MT": "Malta",
    "MH": "Marshall Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MU": "Mauritius",
    "YT": "Mayotte",
    "MX": "Mexico",
    "FM": "Micronesia (Federated States of)",
    "MD": "Moldova (the Republic of)",
    "MC": "Monaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MS": "Montserrat",
    "MA": "Morocco",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NL": "Netherlands",
    "NC": "New Caledonia",
    "NZ": "New Zealand",
    "NI": "Nicaragua",
    "NE": "Niger",
    "NG": "Nigeria",
    "NU": "Niue",
    "NF": "Norfolk Island",
    "MP": "Northern Mariana Islands",
    "NO": "Norway",
    "OM": "Oman",
    "PK": "Pakistan",
    "PW": "Palau",
    "PS": "Palestine, State of",
    "PA": "Panama",
    "PG": "Papua New Guinea",
    "PY": "Paraguay",
    "PE": "Peru",
    "PH": "Philippines",
    "PN": "Pitcairn",
    "PL": "Poland",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "QA": "Qatar",
    "RE": "Réunion",
    "RO": "Romania",
    "RU": "Russian Federation",
    "RW": "Rwanda",
    "BL": "Saint Barthélemy",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia",
    "MF": "Saint Martin (French part)",
    "PM": "Saint Pierre and Miquelon",
    "VC": "Saint Vincent and the Grenadines",
    "WS": "Samoa",
    "SM": "San Marino",
    "ST": "Sao Tome and Principe",
    "SA": "Saudi Arabia",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leone",
    "SG": "Singapore",
    "SX": "Sint Maarten (Dutch part)",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "SB": "Solomon Islands",
    "SO": "Somalia",
    "ZA": "South Africa",
    "GS": "South Georgia and the South Sandwich Islands",
    "SS": "South Sudan",
    "ES": "Spain",
    "LK": "Sri Lanka",
    "SD": "Sudan",
    "SR": "Suriname",
    "SJ": "Svalbard and Jan Mayen",
    "SE": "Sweden",
    "CH": "Switzerland",
    "SY": "Syrian Arab Republic",
    "TW": "Taiwan (Province of China)",
    "TJ": "Tajikistan",
    "TZ": "Tanzania, United Republic of",
    "TH": "Thailand",
    "TL": "Timor-Leste",
    "TG": "Togo",
    "TK": "Tokelau",
    "TO": "Tonga",
    "TT": "Trinidad and Tobago",
    "TN": "Tunisia",
    "TR": "Turkey",
    "TM": "Turkmenistan",
    "TC": "Turks and Caicos Islands",
    "TV": "Tuvalu",
    "UG": "Uganda",
    "UA": "Ukraine",
    "AE": "United Arab Emirates",
    "GB": "United Kingdom of Great Britain and Northern Ireland",
    "UM": "United States Minor Outlying Islands",
    "US": "United States of America",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VU": "Vanuatu",
    "VE": "Venezuela (Bolivarian Republic of)",
    "VN": "Viet Nam",
    "VG": "Virgin Islands (British)",
    "VI": "Virgin Islands (U.S.)",
    "WF": "Wallis and Futuna",
    "EH": "Western Sahara",
    "YE": "Yemen",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

var regions = {
    "CA": {
        "AB": "Alberta",
        "BC": "British Columbia",
        "MB": "Manitoba",
        "NB": "New Brunswick",
        "NL": "Newfoundland and Labrador",
        "NT": "Northwest Territories",
        "NS": "Nova Scotia",
        "NU": "Nunavut",
        "ON": "Ontario",
        "PE": "Prince Edward Island",
        "QC": "Quebec",
        "SK": "Saskatchewan",
        "YT": "Yukon"
    },
    "US": {
        "AL": "Alabama",
        "AK": "Alaska",
        "AS": "American Samoa",
        "AZ": "Arizona",
        "AR": "Arkansas",
        "AA": "Armed Forces Americas",
        "AE": "Armed Forces Europe",
        "AP": "Armed Forces Pacific",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DE": "Delaware",
        "DC": "District of Columbia",
        "FM": "Federated States of Micronesia",
        "FL": "Florida",
        "GA": "Georgia",
        "GU": "Guam",
        "HI": "Hawaii",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "IA": "Iowa",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "ME": "Maine",
        "MH": "Marshall Islands",
        "MD": "Maryland",
        "MA": "Massachusetts",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MS": "Mississippi",
        "MO": "Missouri",
        "MT": "Montana",
        "NE": "Nebraska",
        "NV": "Nevada",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NY": "New York",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "MP": "Northern Mariana Islands",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PW": "Palau",
        "PA": "Pennsylvania",
        "PR": "Puerto Rico",
        "RI": "Rhode Island",
        "SC": "South Carolina",
        "SD": "South Dakota",
        "TN": "Tennessee",
        "TX": "Texas",
        "UT": "Utah",
        "VT": "Vermont",
        "VI": "Virgin Islands",
        "VA": "Virginia",
        "WA": "Washington",
        "WV": "West Virginia",
        "WI": "Wisconsin",
        "WY": "Wyoming"
    }
}

var DATE_FORMAT = 'MMM DD, YYYY';

function handleRequestError(resp){
    showErrorMessages(resp);
}

var httpRequestMixin = {
    // basically a wrapper around jQuery ajax functions
    methods: {
        req: function(params, doneCb, failCb){
            if(!failCb) failCb = handleRequestError;
            return $.ajax(params).done(doneCb).fail(failCb);
        },
        _conditionalParams: function(orig){
            if(orig.length < 1) return [];
            var args = [{url: orig[0]}]
            if(orig[1] instanceof Function){
                // shortcut form like $.get, where params=doneCb
                // and doneCb=failCb
                args.push(orig[1]);
                if(orig[2]) args.push(orig[2]);
            } else {
                if(orig[1]) args[0].data = orig[1];
                if(orig[2]) args.push(orig[2]); // doneCb
                if(orig[3]) args.push(orig[3]) // failCb
            }
            return args;
        },
        /** This method generates a GET HTTP request to `url` with a query
            string built of a `queryParams` dictionnary.

            It supports the following prototypes:

            - reqGet(url)
            - reqGet(url, queryParams)
            - reqGet(url, queryParams, successCallback)
            - reqGet(url, queryParams, successCallback, failureCallback)
            - reqGet(url, successCallback)
            - reqGet(url, successCallback, failureCallback)

            `queryParams` when it is specified is a dictionnary
            of (key, value) pairs that is converted to an HTTP
            query string.

            `successCallback` and `failureCallback` must be Javascript
            functions (i.e. instance of type `Function`).
         */
        reqGet: function(url, data, doneCb, failCb){
            var vm = this;
            var args = vm._conditionalParams(arguments);
            return this.req.apply(this, args);
        },
        /** This method generates a POST HTTP request to `url` with
            contentType 'application/json'.

            It supports the following prototypes:

            - reqPOST(url)
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
        reqPost: function(url, data, doneCb, failCb){
            var vm = this;
            var args = vm._conditionalParams(arguments);
            if(args[0]){
                args[0].method = 'POST';
            }
            return this.req.apply(this, args);
        },
        /** This method generates a PUT HTTP request to `url` with
            contentType 'application/json'.

            It supports the following prototypes:

            - reqPUT(url)
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
        reqPut: function(url, data, doneCb, failCb){
            var vm = this;
            var args = vm._conditionalParams(arguments);
            if(args[0]){
                args[0].method = 'PUT';
            }
            return this.req.apply(this, args);
        },
        /** This method generates a PATCH HTTP request to `url` with
            contentType 'application/json'.

            It supports the following prototypes:

            - reqPATCH(url)
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
        reqPatch: function(url, data, doneCb, failCb){
            var vm = this;
            var args = vm._conditionalParams(arguments);
            if(args[0]){
                args[0].method = 'PATCH';
            }
            return this.req.apply(this, args);
        },
        /** This method generates a DELETE HTTP request to `url` with a query
            string built of a `queryParams` dictionnary.

            It supports the following prototypes:

            - reqDELETE(url)
            - reqDELETE(url, queryParams)
            - reqDELETE(url, queryParams, successCallback)
            - reqDELETE(url, queryParams, successCallback, failureCallback)
            - reqDELETE(url, successCallback)
            - reqDELETE(url, successCallback, failureCallback)

            `queryParams` when it is specified is a dictionnary
            of (key, value) pairs that is converted to an HTTP
            query string.

            `successCallback` and `failureCallback` must be Javascript
            functions (i.e. instance of type `Function`).
        */
        reqDelete: function(url, data, doneCb, failCb){
            var vm = this;
            var args = vm._conditionalParams(arguments);
            if(args[0]){
                args[0].method = 'DELETE';
            }
            return this.req.apply(this, args);
        },
    }
}

var itemListMixin = {
    data: function(){
        return this.getInitData();
    },
    mixins: [httpRequestMixin],
    methods: {
        getInitData: function(){
            data = {
                url: '',
                itemsLoaded: false,
                items: {
                    results: [],
                    count: 0
                },
                params: {
                    start_at: null,
                    ends_at: null
                },
                getCb: null,
            }
            if( djaodjinSettings.date_range ) {
                if( djaodjinSettings.date_range.start_at ) {
                    data.params['start_at'] = moment(
                        djaodjinSettings.date_range.start_at).format(DATE_FORMAT);
                }
                if( djaodjinSettings.date_range.ends_at ) {
                    data.params['ends_at'] = moment(
                        djaodjinSettings.date_range.ends_at).format(DATE_FORMAT);
                }
            }
            return data;
        },
        get: function(){
            var vm = this;
            if(!vm.url) return
            if(vm[vm.getCb]){
                var cb = vm[vm.getCb];
            } else {
                var cb = function(res){
                    vm.items = res
                    vm.itemsLoaded = true;
                }
            }
            vm.reqGet(vm.url, vm.getParams(), cb);
        },
        getParams: function(excludes){
            var vm = this;
            var params = {};
            for( var key in vm.params ) {
                if( vm.params.hasOwnProperty(key) && vm.params[key] ) {
                    if( excludes && key in excludes ) continue;
                    if( key === 'start_at' || key === 'ends_at' ) {
                        params[key] = moment(vm.params[key], DATE_FORMAT).toISOString();
                    } else {
                        params[key] = vm.params[key];
                    }
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
                    result += sep + key + '=' + params[key].toString();
                    sep = "&";
                }
            }
            if( result ) {
                result = '?' + result;
            }
            return result;
        },
        humanizeTotal: function() {
            var vm = this;
            var filter = Vue.filter('humanizeCell');
            return filter(vm.items.total, vm.items.unit, 0.01);
        },
        humanizeBalance: function() {
            var vm = this;
            var filter = Vue.filter('humanizeCell');
            return filter(vm.items.balance, vm.items.unit, 0.01);
        },
    },
}

var paginationMixin = {
    data: function(){
        return {
            params: {
                page: 1,
            },
            itemsPerPage: djaodjinSettings.itemsPerPage,
        }
    },
    computed: {
        totalItems: function(){
            return this.items.count
        },
        pageCount: function(){
            return Math.ceil(this.totalItems / this.itemsPerPage)
        }
    }
}

var filterableMixin = {
    data: function(){
        return {
            params: {
                q: '',
            },
            mixinFilterCb: 'get',
        }
    },
    methods: {
        filterList: function(){
            if(this.params.q) {
                if ("page" in this.params){
                    this.params.page = 1;
                }
            }
            if(this[this.mixinFilterCb]){
                this[this.mixinFilterCb]();
            }
        },
    },
}

var sortableMixin = {
    data: function(){
        return {
            params: {
                o: djaodjinSettings.sortByField || 'created_at',
                ot: djaodjinSettings.sortDirection || 'desc',
            },
            mixinSortCb: 'get'
        }
    },
    methods: {
        sortBy: function(fieldName) {
            if(this.params.o === fieldName) {
                if(this.params.ot === "asc") {
                    this.params.ot = "desc";
                } else {
                    this.params.ot = "asc";
                }
            }
            else {
                this.params.o = fieldName
                this.params.ot = "asc";
            }
            if(this[this.mixinSortCb]){
                this[this.mixinSortCb]();
            }
        },
        sortIcon: function(fieldName){
            var res = 'fa fa-sort';
            if(fieldName === this.params.o){
                res += ('-' + this.params.ot);
            }
            return res;
        }
    },
}

var timezoneMixin = {
    data: function(){
        return {
            timezone: 'local',
        }
    },
    methods: {
        convertDatetime: function(data, isUTC){
            // Convert datetime string to moment object in-place because we want
            // to keep extra keys and structure in the JSON returned by the API.
            return data.map(function(f){
                var values = f.values.map(function(v){
                    // localizing the period to local browser time
                    // unless showing reports in UTC.
                    v[0] = isUTC ? moment.parseZone(v[0]) : moment(v[0]);
                });
            });
        },
    },
}

var userRelationMixin = {
    mixins: [itemListMixin, paginationMixin],
    data: function(){
        return {
            modalSelector: ".add-role-modal",
            url: djaodjinSettings.urls.organization.api_roles,
            typeaheadUrl: null,
            unregistered: {
                slug: '',
                email: '',
                full_name: ''
            },
        }
    },
    methods: {
        modalShow: function() {
            var vm = this;
            var dialog = $(vm.modalSelector);
            if( dialog && jQuery().modal ) {
                dialog.modal("show");
            }
        },
        remove: function(idx){
            var vm = this;
            var ob = this.items.results[idx]
            var slug = (ob.user ? ob.user.slug : ob.slug);
            if( djaodjinSettings.user && djaodjinSettings.user.slug === slug ) {
                if( !confirm(gettext("You are about to delete yourself from" +
                    " this role. it's possible that you no longer can manage" +
                    " this organization after performing this" +
                    " action.\n\nDo you want to remove yourself" +
                    " from this organization?")) ) {
                    return;
                }
            }
            var url = vm.url + '/' + encodeURIComponent(slug);
            vm.reqDelete(url, function() {
                // splicing instead of refetching because
                // subsequent fetch might fail due to 403
                vm.items.results.splice(idx, 1);
            });
        },
        saveUserRelation: function(slug){
            var vm = this;
            vm.reqPost(vm.url, {slug: slug},
                function(resp){
                    vm.get()
                }, function(resp){
                    vm.handleNewUser(slug);
                }
            );
        },
        handleNewUser: function(str){
            var vm = this;
            if(str.length > 0){
                vm.unregistered = {
                    slug: str,
                    email: str,
                    full_name: str
                }
                vm.modalShow();
            }
        },
        save: function(item){
            var vm = this;
            vm.saveUserRelation(item.slug ? item.slug : item.toString());
        },
        create: function(){
            var vm = this;
            var data = vm.unregistered;
            vm.reqPost(vm.url + "?force=1", data, function(resp){
                vm.get()
            });
        }
    },
}

var subscriptionsMixin = {
    data: function(){
        return {
            ends_at: moment().endOf("day").toDate(),
        }
    },
    methods: {
        subscriptionURL: function(organization, plan) {
            return djaodjinSettings.urls.organization.api_profile_base
                + organization + "/subscriptions/" + plan;
        },
        endsSoon: function(subscription) {
            var cutOff = new Date(this.ends_at);
            cutOff.setDate(this.ends_at.getDate() + 5);
            var subEndsAt = new Date(subscription.ends_at);
            if( subEndsAt < cutOff ) {
                return "bg-warning";
            }
            return "";
        },
    },
}

var subscribersMixin = {
    mixins: [
        itemListMixin,
    ],
    methods: {
        editDescription: function(item, id){
            var vm = this;
            vm.$set(item, 'edit_description', true);
            // at this point the input is rendered and visible
            vm.$nextTick(function(){
                var ref = vm.refId(item, id);
                vm.$refs[ref][0].focus();
            });
        },
        saveDescription: function(item){
            // this solves a problem where user hits an enter
            // which saves the description and then once they
            // click somewhere this callback is triggered again
            // due to the fact that the input is blurred even
            // though it is hidden by that time
            if(!item.edit_description) return;
            this.$set(item, 'edit_description', false);
            delete item.edit_description;
            this.update(item)
        },
        refId: function(item, id){
            var ids = [item.organization.slug,
                item.plan.slug, id];
            return ids.join('_').replace(new RegExp('[-:]', 'g'), '');
        },
        update: function(item){
            var vm = this;
            var url = vm.subscriptionURL(
                item.organization.slug, item.plan.slug);
            vm.reqPatch(url, {description: item.description})
        },
        resolve: function (o, s){
            return s.split('.').reduce(function(a, b) {
                return a[b];
            }, o);
        },
        groupBy: function (list, groupBy) {
            var vm = this;
            var res = {};
            list.forEach(function(item){
                var value = vm.resolve(item, groupBy);
                res[value] = res[value] || [];
                res[value].push(item);
            });
            var ordered_res = [];
            for( var key in res ) {
                if( res.hasOwnProperty(key) ) {
                    ordered_res.push(res[key]);
                }
            }
            return ordered_res;
        },
    }
}

Vue.component('user-typeahead', {
    template: "",
    props: ['url', 'role'],
    data: function(){
        return {
            target: null,
            searching: false,
            // used in a http request
            typeaheadQuery: '',
            // used to hold the selected item
            itemSelected: '',
        }
    },
    mixins: [httpRequestMixin],
    computed: {
        params: function(){
            res = {}
            if(this.typeaheadQuery) res.q = this.typeaheadQuery;
            return res
        },
    },
    methods: {
        // called by typeahead when a user enters input
        getUsers: function(query, done) {
            var vm = this;
            if(!vm.url) {
                done([]);
            }
            else {
                vm.searching = true;
                vm.typeaheadQuery = query;
                vm.reqGet(vm.url, vm.params, function(res){
                    vm.searching = false;
                    done(res.results)
                });
            }
        },
        submit: function(){
            this.$emit('item-save', this.itemSelected);
            this.itemSelected = '';
        }
    },
    mounted: function() {
        // TODO we should probably use one interface everywhere
        if(this.$refs.tphd)
            this.target = this.$refs.tphd[0];
    }
});

// TODO it probably makes sense to use this component in other
// places where user relations are needed
Vue.component('user-relation', {
    template: "",
    props: {
        roleUrl: '',
        role: {
            type: Object,
            default: function(){
                return {
                    slug: '',
                    title: ''
                }
            }
        },
    },
    mixins: [userRelationMixin],
    data: function(){
        return {
            url: this.roleUrl,
            typeaheadUrl: djaodjinSettings.urls.api_candidates,
        }
    },
    watch: {
        // this should have been a computed propery, however
        // vue doesn't allow to have computed properties with
        // the same name as in data
        roleUrl: function (newVal, oldVal) {
            if(newVal != oldVal){
                this.url = newVal;
                this.params.page = 1;
                this.get();
            }
        }
    },
    mounted: function(){
        this.get();
    },
});

if($('#coupon-list-container').length > 0){
new Vue({
    el: "#coupon-list-container",
    mixins: [
        itemListMixin,
        paginationMixin,
        filterableMixin,
        sortableMixin
    ],
    data: {
        url: djaodjinSettings.urls.provider.api_coupons,
        newCoupon: {
            code: '',
            percent: ''
        },
        edit_description: [],
        date: null
    },
    methods: {
        remove: function(idx){
            var vm = this;
            var code = this.items.results[idx].code;
            vm.reqDelete(vm.url + '/' + code, function() {
                vm.get();
            });
        },
        update: function(coupon){
            var vm = this;
            vm.reqPut(vm.url + '/' + coupon.code, coupon, function(resp){
                vm.get();
            });
        },
        save: function(){
            var vm = this;
            vm.reqPost(vm.url, vm.newCoupon, function(resp){
                vm.get();
                vm.newCoupon = {
                    code: '',
                    percent: ''
                }
            });
        },
        editDescription: function(idx){
            var vm = this;
            vm.edit_description = Array.apply(
                null, new Array(vm.items.results.length)).map(function() {
                return false;
            });
            vm.$set(vm.edit_description, idx, true)
            // at this point the input is rendered and visible
            vm.$nextTick(function(){
                vm.$refs.edit_description_input[idx].focus();
            });
        },
        saveDescription: function(coupon, idx, event){
            if (event.which === 13 || event.type === "blur" ){
                this.$set(this.edit_description, idx, false)
                this.update(this.items.results[idx])
            }
        },
        selected: function(idx){
            var coupon = this.items.results[idx]
            coupon.ends_at = (new Date(coupon.ends_at)).toISOString()
            this.update(coupon)
        },
    },
    mounted: function(){
        this.get()
    }
})
}

if($('#search-list-container').length > 0){
new Vue({
    el: "#search-list-container",
    mixins: [itemListMixin, paginationMixin, filterableMixin],
    data: {
        url: djaodjinSettings.urls.provider.api_accounts,
    },
})
}

if($('#today-sales-container').length > 0){
new Vue({
    el: "#today-sales-container",
    mixins: [itemListMixin, paginationMixin],
    data: {
        url: djaodjinSettings.urls.provider.api_receivables,
        params: {
            start_at: moment().startOf('day'),
            o: 'created_at',
            ot: 'desc'
        }
    },
    mounted: function(){
        this.get()
    }
})
}

if($('#user-list-container').length > 0){
new Vue({
    el: "#user-list-container",
    mixins: [itemListMixin, paginationMixin],
    data: {
        url: djaodjinSettings.urls.provider.api_accounts,
        params: {
            start_at: moment().startOf('day'),
            o: '-created_at'
        }
    },
    mounted: function(){
        this.get()
    }
})
}

var userRelationListMixin = {
    mixins: [userRelationMixin, filterableMixin],
    data: function(){
        return {
            showPending: false,
            typeaheadUrl: djaodjinSettings.urls.api_candidates,
        }
    },
    methods: {
        sendInvite: function(slug){
            var vm = this;
            vm.reqPost(vm.url + '/' + slug + '/', {}, function(res){
                showMessages([interpolate(gettext(
                    "Invite for %s has been sent"), [slug])],
                    "success");
            });
        },
    },
    mounted: function(){
        this.get()
    }
}

if($('#user-relation-list-container').length > 0){
new Vue({
    el: "#user-relation-list-container",
    mixins: [userRelationListMixin],
})
}

if($('#user-relation-active-list-container').length > 0){
var app = new Vue({
    el: "#user-relation-active-list-container",
    mixins: [userRelationListMixin],
    data: function(){
        return {
            params: {
                role_status: 'active',
                o: 'username',
                ot: 'asc',
            }
        }
    },
})
}

if($('#user-relation-pending-list-container').length > 0){
var app = new Vue({
    el: "#user-relation-pending-list-container",
    mixins: [userRelationListMixin],
    data: function(){
        return {
            params: {
                role_status: 'pending',
                o: 'username',
                ot: 'asc',
            }
        }
    },
})
}

if($('#metrics-container').length > 0){
new Vue({
    el: "#metrics-container",
    mixins: [httpRequestMixin, timezoneMixin],
    data: function(){
        var data = {
            tables: djaodjinSettings.tables,
            activeTab: 0,
        }
        data.ends_at = moment();
        if( djaodjinSettings.date_range
            && djaodjinSettings.date_range.ends_at ) {
            var ends_at = moment(djaodjinSettings.date_range.ends_at);
            if(ends_at.isValid()){
                data.ends_at = ends_at;
            }
        }
        data.ends_at = data.ends_at.format(DATE_FORMAT);
        return data;
    },
    methods: {
        fetchTableData: function(table, cb){
            var vm = this;
            var params = {"ends_at": moment(vm.ends_at, DATE_FORMAT).format()};
            if( vm.timezone !== 'utc' ) {
                params["timezone"] = moment.tz.guess();
            }
            vm.reqGet(table.location, params, function(resp){
                var unit = resp.unit;
                var scale = resp.scale;
                scale = parseFloat(scale);
                if( isNaN(scale) ) {
                    scale = 1.0;
                }
                // add "extra" rows at the end
                var extra = resp.extra || [];

                var tableData = {
                    key: table.key,
                    title: table.title,
                    location: table.location,
                    unit: unit,
                    scale: scale,
                    data: resp.table
                }
                vm.convertDatetime(tableData.data, vm.timezone === 'utc');
                for( var idx = 0; idx < vm.tables.length; ++idx ) {
                    if( vm.tables[idx].key === table.key ) {
                        vm.$set(vm.tables, idx, tableData);
                        break;
                    }
                }
                if(cb) cb();
            });
        },
        endOfMonth: function(date) {
            return new Date(
                date.getFullYear(),
                date.getMonth() + 1,
                0
            );
        },
        prepareCurrentTabData: function(){
            var vm = this;
            var table = vm.currentTable;
            vm.fetchTableData(table, function(){
                var tableData = vm.currentTableData;
                 // manual binding - trigger updates to the graph
                if( table.key === "balances") {
                    // XXX Hard-coded.
                    updateBarChart("#" + table.key +  " .chart-content",
                        tableData.data, tableData.unit, tableData.scale, tableData.extra);
                } else {
                    updateChart("#" + table.key +  " .chart-content",
                        tableData.data, tableData.unit, tableData.scale, tableData.extra);
                }
            });
        },
        tabClicked: function(index) {
            var vm = this;
            vm.activeTab = index;
            vm.prepareCurrentTabData();
        },
        tabTitle: function(table){
            var filter = Vue.filter('currencyToSymbol');
            var unit = '';
            if(table && table.unit){
                unit = ' (' + filter(table.unit) + ')';
            }
            return table.title + unit;
        },
        activeClass: function(index) {
            var vm = this;
            var base = 'nav-link';
            return (index === vm.activeTab) ? base + " active" : base;
        },
        humanizeCell: function(value, unit, scale) {
            var vm = this;
            var filter = Vue.filter('humanizeCell');
            return filter(value, unit, scale);
        },
    },
    computed: {
        currentTable: function(){
            return this.tables[this.activeTab];
        },
        currentTableData: function(){
            var vm = this;
            var res = {data: []}
            if(vm.currentTable.data){
                res = vm.currentTable;
            }
            return res;
        },
        currentTableDates: function(){
            var vm = this;
            var res = [];
            var data = vm.currentTableData.data;
            if(data && data.length > 0){
                res = data[0].values;
            }
            return res;
        }
    },
    mounted: function(){
        var vm = this;
        vm.prepareCurrentTabData();
        if( false ) {
            // XXX donot pretetch other tabs to match angularjs code
            //     and pass tests.
            for( var idx = 1; idx < vm.tables.length; ++idx ) {
                var table = vm.tables[(vm.activeTab + idx) % vm.tables.length];
                vm.fetchTableData(table);
            }
        }
    }
})
}

if($('#registered').length > 0){
  new Vue({
    el: "#registered",
    mixins: [
        itemListMixin,
        paginationMixin,
        filterableMixin,
        sortableMixin,
    ],
    data: {
        url: djaodjinSettings.urls.broker.api_users_registered,
    },
    mounted: function(){
        this.get();
    },
})
}

if($('#subscribed').length > 0){
var app = new Vue({
    el: "#subscribed",
    mixins: [
        subscriptionsMixin,
        subscribersMixin,
        paginationMixin,
        filterableMixin,
        sortableMixin,
    ],
    data: {
        url: djaodjinSettings.urls.provider.api_subscribers_active,
    },
    mounted: function(){
        this.get();
    },
})
}

if($('#churned').length > 0){
var app = new Vue({
    el: "#churned",
    mixins: [
        subscriptionsMixin,
        subscribersMixin,
        paginationMixin,
        filterableMixin,
        sortableMixin,
    ],
    data: {
        url: djaodjinSettings.urls.provider.api_subscribers_churned,
    },
    mounted: function(){
        this.get();
    },
})
}

if($('#plans-tab-container').length > 0){
var app = new Vue({
    el: "#plans-tab-container",
    mixins: [
        httpRequestMixin,
        timezoneMixin
    ],
    data: function(){
        var data = {
            url: djaodjinSettings.urls.provider.api_metrics_plans,
            endsAt: moment(),
            plansData: {
                data: []
            },
        }
        if( djaodjinSettings.date_range
            && djaodjinSettings.date_range.ends_at ) {
            var ends_at = moment(djaodjinSettings.date_range.ends_at);
            if(ends_at.isValid()){
                data.endsAt = ends_at;
            }
        }
        data.endsAt = data.endsAt.format(DATE_FORMAT);

        return data;
    },
    methods: {
        get: function(){
            var vm = this;
            var params = {"ends_at": moment(vm.endsAt, DATE_FORMAT).format()};
            if( vm.timezone !== 'utc' ) {
                params["timezone"] = moment.tz.guess();
            }
            vm.reqGet(vm.url, params, function(resp){
                var unit = resp.unit;
                var scale = resp.scale;
                scale = parseFloat(scale);
                if( isNaN(scale) ) {
                    scale = 1.0;
                }
                // add "extra" rows at the end
                var extra = resp.extra || [];

                var tableData = {
                    key: 'plan',
                    title: resp.title,
                    unit: unit,
                    scale: scale,
                    data: resp.table,
                    extra: resp.extra
                }
                vm.convertDatetime(tableData.data, vm.timezone === 'utc');
                vm.plansData = tableData

                if(window.updateChart){
                    // in djaodjin-saas there is no metrics code, that's
                    // why we need to check if there is a global defined
                    updateChart(".chart-content", tableData.data,
                        tableData.unit, tableData.scale, tableData.extra);
                }
            });
        },
        humanizeCell: function(value, unit, scale) {
            var vm = this;
            var filter = Vue.filter('humanizeCell');
            return filter(value, unit, scale);
        },
    },
    computed: {
        planTableDates: function(){
            var res = this.plansData.data;
            if(res.length > 0){
                return res[0].values;
            }
            return []
        },
    },
    mounted: function(){
        this.get();
    },
})
}

/*
    XXX
    We define a global here because another VM needs to be able
    to communicate with this one, specifically when a user is
    unsubscribed, an event is triggered which causes another VM
    to reload its list of objects
*/
var subscriptionsListVM;

if($('#subscriptions-list-container').length > 0){
subscriptionsListVM = new Vue({
    el: "#subscriptions-list-container",
    mixins: [subscriptionsMixin, paginationMixin, itemListMixin],
    data: {
        url: djaodjinSettings.urls.organization.api_subscriptions,
        plan: {},
        params: {
            state: 'active',
        },
        toDelete: {
            plan: null,
            org: null
        },
    },
    methods: {
        update: function(item){
            var vm = this;
            var url = vm.subscriptionURL(
                item.organization.slug, item.plan.slug);
            var data = {
                description: item.description,
                ends_at: item.ends_at
            };
            vm.reqPatch(url, data);
        },
        selected: function(idx){
            var item = this.items.results[idx];
            item.ends_at = (new Date(item.ends_at)).toISOString();
            this.update(item);
        },
        subscribersURL: function(provider, plan) {
            return djaodjinSettings.urls.organization.api_profile_base + provider + "/plans/" + plan + "/subscriptions/";
        },
        subscribe: function(org){
            var vm = this;
            var url = vm.subscribersURL(vm.plan.organization, vm.plan.slug);
            var data = {
                organization: {
                  slug: org
                }
            }
            vm.req({
                method: 'POST',
                url: url,
                contentType: 'application/json',
                data: JSON.stringify(data),
            }, function (){
                vm.get();
            });
        },
        unsubscribeConfirm: function(org, plan) {
            this.toDelete = {
                org: org,
                plan: plan
            }
        },
        unsubscribe: function() {
            var vm = this;
            var data = vm.toDelete;
            if(!(data.org && data.plan)) return;
            var url = vm.subscriptionURL(data.org, data.plan);
            vm.reqDelete(url, function (){
                vm.$emit('expired');
                vm.params.page = 1;
                vm.get();
            });
        },
        acceptRequest: function(organization, request_key) {
            var vm = this;
            var url = (djaodjinSettings.urls.organization.api_profile_base +
                organization + "/subscribers/accept/" + request_key + "/");
            vm.reqPut(url, function (){
                vm.get();
            });
        },
    },
    mounted: function(){
        this.get();
    }
})
}

if($('#expired-subscriptions-list-container').length > 0){
new Vue({
    el: "#expired-subscriptions-list-container",
    mixins: [subscriptionsMixin, paginationMixin, itemListMixin],
    data: {
        url: djaodjinSettings.urls.organization.api_subscriptions,
        params: {
            state: 'expired',
        },
    },
    mounted: function(){
        this.get();
        subscriptionsListVM.$on('expired', this.get);
    }
})
}

if($('#import-transaction-container').length > 0){
new Vue({
    el: "#import-transaction-container",
    data: {
        url: djaodjinSettings.urls.provider.api_subscribers_active,
        createdAt: moment().format("YYYY-MM-DD"),
        itemSelected: '',
        searching: false,
        amount: 0,
        description: '',
    },
    mixins: [httpRequestMixin],
    methods: {
        getSubscriptions: function(query, done) {
            var vm = this;
            vm.searching = true;
            vm.reqGet(vm.url, {q: query}, function(res){
                vm.searching = false;
                // current typeahead implementation does not
                // support dynamic keys that's why we are
                // creating them here
                res.results.forEach(function(e){
                    e.itemKey = e.organization.slug + ':' + e.plan.slug
                });
                done(res.results)
            });
        },
        addPayment: function(){
            var vm = this;
            var sel = vm.itemSelected
            if(!sel.plan){
                alert(gettext('select a subscription from dropdown'));
                return;
            }
            var sub = sel.organization.slug + ':' + sel.plan.slug;
            vm.reqPost(djaodjinSettings.urls.organization.api_import, {
                subscription: sub,
                amount: vm.amount,
                descr: vm.description,
                created_at: moment(vm.createdAt).toISOString(),
            }, function () {
                vm.itemSelected = '';
                vm.amount = '';
                vm.description = '';
                vm.createdAt = moment().format("YYYY-MM-DD");
                showMessages([gettext("Profile was updated.")], "success");
            });
        }
    },
});
}

if($('#coupon-users-container').length > 0){
new Vue({
    el: "#coupon-users-container",
    mixins: [itemListMixin, sortableMixin, paginationMixin, filterableMixin],
    data: {
        params: {
            o: 'created_at',
            ot: "desc",
        },
        url: djaodjinSettings.urls.provider.api_metrics_coupon_uses
    },
    mounted: function(){
        this.get()
    }
})
}

if($('#billing-statement-container').length > 0){
new Vue({
    el: "#billing-statement-container",
    mixins: [
        itemListMixin,
        sortableMixin,
        paginationMixin,
        filterableMixin
    ],
    data: function(){
        var res = {
            url: djaodjinSettings.urls.organization.api_transactions,
            last4: gettext("N/A"),
            exp_date: gettext("N/A"),
            cardLoaded: false
        }
        return res;
    },
    methods: {
        getCard: function(){
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.organization.api_card,
            function(resp){
                if(resp.last4) {
                    vm.last4 = resp.last4;
                }
                if(resp.exp_date) {
                    vm.exp_date = resp.exp_date;
                }
                vm.cardLoaded = true;
            });
        },
        reload: function(){
            var vm = this;
            // We want to make sure the 'Write off...' transaction will display.
            vm.params.o = 'created_at';
            vm.params.ot = 'desc';
            if( vm.params.ends_at ) {
                delete vm.params['ends_at'];
            }
            vm.get();
        },
        cancelBalance: function(){
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.organization.api_cancel_balance_due,
                function() {
                    vm.reload()
                },
                function(resp){
                    vm.reload()
                    handleRequestError(resp);
                }
            );
        }
    },
    mounted: function(){
        this.getCard();
        this.get();
    }
})
}

if($('#transfers-container').length > 0){
new Vue({
    el: "#transfers-container",
    mixins: [
        itemListMixin,
        sortableMixin,
        paginationMixin,
        filterableMixin
    ],
    data: {
        url: djaodjinSettings.urls.organization.api_transactions,
        balanceLoaded: false,
        last4: gettext("N/A"),
        bank_name: gettext("N/A"),
        balance_amount: gettext("N/A"),
        balance_unit: '',
    },
    methods: {
        getBalance: function() {
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.provider.api_bank,
            function(resp){
                vm.balance_amount = resp.balance_amount;
                vm.balance_unit = resp.balance_unit;
                vm.last4 = resp.last4;
                vm.bank_name = resp.bank_name;
                vm.balanceLoaded = true;
            });
        },
        humanizeBalance: function() {
            var vm = this;
            var filter = Vue.filter('humanizeCell');
            return filter(vm.balance_amount, vm.balance_unit, 0.01);
        },
    },
    mounted: function(){
        this.getBalance();
        this.get();
    },
})
}

if($('#transactions-container').length > 0){
new Vue({
    el: "#transactions-container",
    mixins: [itemListMixin, sortableMixin, paginationMixin, filterableMixin],
    data: {
        url: djaodjinSettings.urls.organization.api_transactions,
    },
    mounted: function(){
        this.get();
    },
})
}

if($('#accessible-list-container').length > 0){
new Vue({
    el: "#accessible-list-container",
    mixins: [userRelationMixin, sortableMixin, filterableMixin],
    data: {
        params: {
            o: "slug",
            ot: "asc",
        },
        url: djaodjinSettings.urls.user.api_accessibles,
        typeaheadUrl: djaodjinSettings.urls.api_candidates,
    },
    mounted: function(){
        this.get()
    },
})
}

if($('#plan-subscribers-container').length > 0){
new Vue({
    el: "#plan-subscribers-container",
    mixins: [
        subscriptionsMixin,
        subscribersMixin,
        paginationMixin,
        sortableMixin,
        filterableMixin,
    ],
    data: {
        url: djaodjinSettings.urls.provider.api_plan_subscribers,
    },
    mounted: function(){
        this.get();
    }
})
}

if($('#profile-container').length > 0){
Vue.use(Croppa);

new Vue({
    el: "#profile-container",
    data: {
        formFields: {},
        countries: countries,
        regions: regions,
        currentPicture: null,
        picture: null,
    },
    mixins: [httpRequestMixin],
    methods: {
        get: function(cb){
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.organization.api_base,
            function(resp) {
                vm.formFields = resp;
                if(cb) cb();
            });
        },
        updateProfile: function(){
            var vm = this;
            vm.validateForm();
            var data = vm.formFields;
            if(vm.imageSelected){
                vm.saveProfileWithPicture(data);
            } else {
                vm.saveProfile(data);
            }
        },
        validateForm: function(){
            var vm = this;
            var isEmpty = true;
            var fields = $(vm.$el).find('[name]').not(
                '[name="csrfmiddlewaretoken"]');
            for( var fieldIdx = 0; fieldIdx < fields.length; ++fieldIdx ) {
                var fieldName = $(fields[fieldIdx]).attr('name');
                var fieldValue = $(fields[fieldIdx]).val();
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
        saveProfile: function(data){
            vm.reqPut(djaodjinSettings.urls.organization.api_base, data,
            function(resp) {
                showMessages([gettext("Profile was updated.")], "success");
            });
        },
        saveProfileWithPicture: function(data){
            var vm = this;
            this.picture.generateBlob(function(blob){
                if(!blob) return;
                var form = new FormData();
                form.append('picture', blob);
                for(var key in data){
                    form.append(key, data[key]);
                }
                vm.req({
                    method: 'PUT',
                    url: djaodjinSettings.urls.organization.api_base,
                    contentType: false,
                    processData: false,
                    data: form,
                }, function() {
                    vm.get(function(){
                        vm.picture.remove();
                    });
                    showMessages(["Profile was updated."], "success");
                });
            }, 'image/jpeg');
        },
        deleteProfile: function(){
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.organization.api_base,
                function() {
                    window.location = djaodjinSettings.urls.profile_redirect;
                }
            );
        },
    },
    computed: {
        imageSelected: function(){
            return this.picture && this.picture.hasImage();
        }
    },
    mounted: function() {
        var vm = this;
        if( !vm.validateForm() ) {
            // It seems the form is completely blank. Let's attempt
            // to load the profile from the API then.
            vm.get();
        }
    },
});
}

if($('#charge-list-container').length > 0){
new Vue({
    el: "#charge-list-container",
    mixins: [
        itemListMixin,
        filterableMixin
    ],
    data: {
        url: djaodjinSettings.urls.broker.api_charges,
    },
    mounted: function(){
        this.get();
    }
})
}

if($('#role-list-container').length > 0){
new Vue({
    el: "#role-list-container",
    mixins: [
        itemListMixin,
        paginationMixin,
    ],
    data: {
        url: djaodjinSettings.urls.organization.api_role_descriptions,
        role: {
            title: '',
        },
    },
    methods: {
        create: function(){
            var vm = this;
            vm.reqPost(vm.url, vm.role, function(resp) {
                vm.role.title = '';
                vm.params.page = 1;
                vm.get()
            });
        },
        remove: function(role){
            var vm = this;
            var url = vm.url + "/" + role.slug
            vm.reqDelete(url, function() {
                vm.params.page = 1;
                vm.get()
            });
        },
    },
    mounted: function(){
        this.get();
    },
})
}

if($('#balance-list-container').length > 0){
new Vue({
    el: "#balance-list-container",
    mixins: [
        itemListMixin,
        timezoneMixin,
    ],
    data: {
        url: djaodjinSettings.urls.api_broker_balances,
        balanceLineUrl : djaodjinSettings.urls.api_balance_lines,
        startPeriod: moment().subtract(1, 'months').toISOString(),
        balanceLine: {
            title: '',
            selector: '',
            rank: 0,
        },
    },
    computed: {
        values: function(){
            if(this.items.table && this.items.table.length > 0){
                return this.items.table[0].values
            }
            return [];
        }
    },
    methods: {
        create: function(){
            var vm = this;
            vm.reqPost(vm.balanceLineUrl, vm.balanceLine, function(resp){
                vm.get()
                vm.balanceLine = {
                    title: '',
                    selector: '',
                    rank: 0,
                }
            });
        },
        humanizeCell: function(value, unit, scale) {
            var vm = this;
            if( typeof unit == 'undefined' ) {
                unit = vm.items.unit;
            }
            if( typeof scale == 'undefined' ) {
                scale = vm.items.scale;
            }
            var filter = Vue.filter('humanizeCell');
            return filter(value, unit, scale);
        },
        remove: function(id){
            var vm = this;
            vm.reqDelete(vm.balanceLineUrl + '/' + id, function() {
                vm.get()
            });
        },
    },
    mounted: function(){
        this.get();
    }
})
}

var cardMixin = {
    data: {
        cardNumber: '',
        cardCvc: '',
        cardExpMonth: '',
        cardExpYear: '',
        savedCard: {
          last4: '',
          exp_date: '',
        },
        countries: countries,
        regions: regions,
        organization: {},
        card_name: getInitValue($("#card-use"), 'card_name'),
        card_address_line1: getInitValue($("#card-use"), 'card_address_line1'),
        card_city: getInitValue($("#card-use"), 'card_city'),
        card_adress_zip: getInitValue($("#card-use"), 'card_address_zip'),
        country: getInitValue($("#card-use"), 'country'),
        region: getInitValue($("#card-use"), 'region'),
        errors: {},
        validate: [
            'cardNumber',
            'cardCvc',
            'cardExpMonth',
            'cardExpYear',
            'card_name',
            'card_address_line1',
            'card_city',
            'card_adress_zip',
            'country',
            'region',
        ],
        updateCard: false, //used in legacy checkout
    },
    mixins: [httpRequestMixin],
    methods: {
        clearCardData: function() {
            var vm = this;
            vm.savedCard.last4 = '';
            vm.savedCard.exp_date = '';
            vm.cardNumber = '';
            vm.cardCvc = '';
            vm.cardExpMonth = '';
            vm.cardExpYear = '';
        },
        inputClass: function(name){
            var vm = this;
            var field = this.errors[name];
            if(name === 'cardExp'){
                // a hack to validate card expiration year and month as
                // a single field
                if(vm.errors['cardExpMonth'] || this.errors['cardExpYear']){
                    field = true;
                }
            }
            cls = [];
            if( field ){
                cls.push('has-error');
            }
            return cls;
        },
        getUserCard: function(){
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.organization.api_card,
            function(resp){
                if(resp.last4){
                    vm.savedCard.last4 = resp.last4;
                    vm.savedCard.exp_date = resp.exp_date;
                }
            });
        },
        getCardToken: function(cb){
            var vm = this;
            if(!djaodjinSettings.stripePubKey){
                showMessages([
                    gettext("You haven't set a valid Stripe public key")
                ], "error");
                return;
            }
            Stripe.setPublishableKey(djaodjinSettings.stripePubKey);
            Stripe.createToken({
                number: vm.cardNumber,
                cvc: vm.cardCvc,
                exp_month: vm.cardExpMonth,
                exp_year: vm.cardExpYear,
                name: vm.card_name,
                address_line1: vm.card_address_line1,
                address_city: vm.card_city,
                address_state: vm.region,
                address_zip: vm.card_adress_zip,
                address_country: vm.country
            }, function(code, res){
                if(code === 200) {
                    vm.savedCard.last4 = '***-' + res.card.last4;
                    vm.savedCard.exp_date = (
                        res.card.exp_month + '/' + res.card.exp_year);
                    if(cb) cb(res.id)
                } else {
                    showMessages([res.error.message], "error");
                }
            });
        },
        getOrgAddress: function(){
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.organization.api_base, function(org) {
                if(org.full_name){
                    vm.card_name = org.full_name;
                }
                if(org.street_address){
                    vm.card_address_line1 = org.street_address;
                }
                if(org.locality){
                    vm.card_city = org.locality;
                }
                if(org.postal_code){
                    vm.card_adress_zip = org.postal_code;
                }
                if(org.country){
                    vm.country = org.country;
                }
                if(org.region){
                    vm.region = org.region;
                }
                vm.organization = org;
            }).fail(handleRequestError);
        },
        validateForm: function(){
            var vm = this;
            var valid = true;
            var errors = {}
            var errorMessages = "";
            vm.validate.forEach(function(field){
                if(vm[field] === ''){
                    vm[field] = getInitValue($(vm.$el), field);
                }
                if( vm[field] === '') {
                    valid = false;
                    errors[field] = [gettext("This field shouldn't be empty")];
                }
            });
            vm.errors = errors;
            if(Object.keys(vm.errors).length > 0){
                if( vm.errors['cardNumber'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Card Number");
                }
                if( vm.errors['cardCvc'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Card Security Code");
                }
                if( vm.errors['cardExpMonth']
                         || vm.errors['cardExpYear'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Expiration");
                }
                if( vm.errors['card_name'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Card Holder");
                }
                if( vm.errors['card_address_line1'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Street");
                }
                if( vm.errors['card_city'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("City");
                }
                if( vm.errors['card_adress_zip'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Zip");
                }
                if( vm.errors['country'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Country");
                }
                if( vm.errors['region'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("State/Province");
                }
                if( errorMessages ) {
                    errorMessages += " " + gettext("field(s) cannot be empty.");
                }
                showErrorMessages(errorMessages);
            }
            return valid;
        },
    },
    computed: {
        haveCardData: function() {
            var vm = this;
            return vm.savedCard.last4 && vm.savedCard.exp_date;
        }
    },
    mounted: function() {
        var vm = this;
        var elements = vm.$el.querySelectorAll('[data-last4]');
        if( elements.length > 0 ) {
            vm.savedCard.last4 = elements[0].getAttribute('data-last4');
        }
        var elements = vm.$el.querySelectorAll('[data-exp-date]');
        if( elements.length > 0 ) {
            vm.savedCard.exp_date = elements[0].getAttribute('data-exp-date');
        }
    }
}

if($('#checkout-container').length > 0){
new Vue({
    el: "#checkout-container",
    mixins: [itemListMixin, cardMixin],
    data: {
        url: djaodjinSettings.urls.organization.api_checkout,
        isBulkBuyer: djaodjinSettings.bulkBuyer,
        plansOption: {},
        plansUser: {},
        coupon: '',
        optionsConfirmed: false,
        seatsConfirmed: false,
        getCb: 'getAndPrepareData',
        init: true,
        csvFiles: {},
    },
    methods: {
        getOptions: function(){
            var vm = this;
            var res = [];
            vm.items.results.map(function(item, index){
                var plan = item.subscription.plan.slug
                var option = vm.plansOption[plan];
                if(option){
                    res[index] = {option: option}
                }
            });
            return res;
        },
        remove: function(plan){
            var vm = this;
            var url = djaodjinSettings.urls.api_cart;
            vm.reqDelete(url, {plan: plan}, function() {
                vm.get()
            });
        },
        redeem: function(){
            var vm = this;
            vm.reqPost(djaodjinSettings.urls.api_redeem_coupon, {
                code: vm.coupon },
            function(resp) {
                showMessages([gettext("Coupon was successfully applied.")],
                    "success");
                vm.get();
            });
        },
        getAndPrepareData: function(res){
            var vm = this;
            var results = res.items
            var periods = {}
            var users = {}
            var optionsConfirmed = results.length > 0 ? true : false;
            results.map(function(e){
                var plan = e.subscription.plan.slug;
                if(e.options.length > 0){
                    optionsConfirmed = false;
                    if(vm.init){
                        periods[plan] = 1;
                    }
                }
                users[plan] = {
                    firstName: '', lastName: '', email: ''
                }
            });

            this.items = {
                results: results,
                count: results.length
            }
            this.itemsLoaded = true;
            if(this.init){
                this.plansOption = periods;
                this.plansUser = users;
                this.optionsConfirmed = optionsConfirmed;
                this.seatsConfirmed = false;
            }
        },
        addPlanUser: function(plan){
            var vm = this;
            var user = this.planUser(plan);
            var data = {
                plan: plan,
                full_name: user.firstName + ' ' + user.lastName,
                sync_on: user.email
            }
            var option = vm.plansOption[plan];
            if(option){
                data.option = option
            }
            vm.reqPost(djaodjinSettings.urls.api_cart, data,
            function(resp) {
                showMessages([gettext("User was added.")], "success");
                vm.init = false;
                vm.$set(vm.plansUser, plan, {
                    firstName: '',
                    lastName: '',
                    email: ''
                });
                vm.get();
            });
        },
        planUser: function(plan){
            return this.plansUser[plan] && this.plansUser[plan] || {}
        },
        getLastUserPlanIndex: function(plan){
            var lastItemIndex = -1;
            this.items.results.map(function(e, i){
                if(e.subscription.plan.slug === plan){
                    lastItemIndex = i;
                }
            });
            return lastItemIndex;
        },
        isLastUserPlan: function(index){
            var plan = this.items.results[index].subscription.plan.slug;
            var lastItemIndex = this.getLastUserPlanIndex(plan);
            return lastItemIndex === index;
        },
        activeOption: function(item){
            var index = this.plansOption[item.subscription.plan.slug];
            if(index !== undefined){
                var option = item.options[index - 1];
                if(option) return option;
            }
            return {};
        },
        optionSelected: function(plan, index){
            this.$set(this.plansOption, plan, index);
        },
        isOptionSelected: function(plan, index){
            var selected = this.plansOption[plan];
            return selected !== undefined && selected == index;
        },
        saveChanges: function(){
            if(this.optionsConfirmed){
                this.seatsConfirmed = true;
            }
            else {
                this.optionsConfirmed = true;
                if(!this.isBulkBuyer){
                    this.seatsConfirmed = true;
                }
            }
        },
        doCheckout: function(token){
            var vm = this;
            var opts = vm.getOptions();
            var data = {
                remember_card: true,
                items: opts,
                street_address: vm.card_address_line1,
                locality: vm.card_city,
                postal_code: vm.card_adress_zip,
                country: vm.country,
                region: vm.region,
            }
            if(token){
                data.processor_token = token;
            }
            vm.reqPost(djaodjinSettings.urls.organization.api_checkout, data,
            function(resp) {
                showMessages([gettext("Success.")], "success");
                var id = resp.processor_key;
                location = djaodjinSettings.urls.organization.receipt.replace('_', id);
            });
        },
        checkout: function(){
            var vm = this;
            if(vm.haveCardData){
                vm.doCheckout();
            } else {
                if(!vm.validateForm()) return;
                vm.getCardToken(vm.doCheckout);
            }
        },
        // used in legacy checkout
        doCheckoutForm: function(token) {
            var form = $('#checkout-container form');
            if(token){
                form.append("<input type='hidden' name='stripeToken' value='" + token + "'/>");
            }
            form.get(0).submit();
        },
        // used in legacy checkout
        checkoutForm: function() {
            var vm = this;
            cardUse = $('#card-use');
            if( cardUse.length > 0 && cardUse.is(":visible") ) {
                if(vm.haveCardData){
                    if(vm.updateCard){
                        if(!vm.validateForm()) return;
                        vm.getCardToken(vm.doCheckoutForm);
                    } else {
                        vm.doCheckoutForm();
                    }
                } else {
                    if(!vm.validateForm()) return;
                    vm.getCardToken(vm.doCheckoutForm);
                }
            } else {
                vm.doCheckoutForm();
            }
        },
        fileChanged: function(plan, e){
            var file = e.target.files.length > 0 ?
                e.target.files[0] : null;
            if(file)
                this.$set(this.csvFiles, plan, file);
        },
        bulkImport: function(plan){
            var vm = this;
            if(!vm.csvFiles[plan]) return;
            var formData = new FormData();
            formData.append("file", vm.csvFiles[plan]);
            vm.req({
                type: "POST",
                url: "/api/cart/" + plan + "/upload/",
                data: formData,
                processData: false,
                contentType: false,
            }, function(){
                vm.get();
            });
        },
    },
    computed: {
        linesPrice: function(){
            var vm = this;
            var total = 0;
            var unit = 'usd';
            if(this.items.results){
                this.items.results.map(function(e){
                    if(e.options.length > 0){
                        var option = vm.plansOption[e.subscription.plan.slug];
                        if(option !== undefined){
                            total += e.options[option-1].dest_amount;
                            unit = e.options[option-1].dest_unit;
                        }
                    }
                    e.lines.map(function(l){
                        total += l.dest_amount;
                        unit = l.dest_unit;
                    });
                });
            }
            return [total / 100, unit];
        }
    },
    mounted: function(){
        var vm = this;
        vm.get()
        vm.getUserCard();
        var cardForm = $("#card-use");
        if( cardForm.length > 0 ) {
            vm.card_name = getInitValue(cardForm, 'card_name');
            vm.card_address_line1 = getInitValue(cardForm, 'card_address_line1');
            vm.card_city = getInitValue(cardForm, 'card_city');
            vm.card_adress_zip = getInitValue(cardForm, 'card_address_zip');
            vm.country = getInitValue(cardForm, 'country');
            vm.region = getInitValue(cardForm, 'region');
        } else {
            vm.getOrgAddress();
        }
    }
})
}

if($('#payment-form').length > 0){
new Vue({
    el: "#payment-form",
    mixins: [cardMixin],
    data: {
        updateCard: true,
    },
    methods: {
        saveCard: function(){
            var vm = this;
            if(!vm.validateForm()) return;
            vm.getCardToken(function(token){
                vm.reqPut(djaodjinSettings.urls.organization.api_card, {
                    token: token,
                    full_name: vm.card_name,
                    street_address: vm.card_address_line1,
                    locality: vm.card_city,
                    postal_code: vm.card_adress_zip,
                    country: vm.country,
                    region: vm.region,
                },
            function(resp) {
                vm.clearCardData();
                if( resp.last4 ){
                    vm.savedCard.last4 = resp.last4;
                }
                if( resp.exp_date ) {
                    vm.savedCard.exp_date = resp.exp_date;
                }
                // matching the code in `CardUpdateView` for redirects.
                var redirectUrl = getUrlParameter('next');
                if( !redirectUrl ) {
                    redirectUrl = document.referrer;
                }
                if( redirectUrl ) {
                    window.location = redirectUrl;
                }
                showMessages([gettext(
                    "Your credit card on file was sucessfully updated.")],
                    "success");
                });
            });
        },
        save: function(){
            this.saveCard();
        },
        remove: function() {
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.organization.api_card,
            function(resp) {
                vm.clearCardData();
                showMessages([gettext(
                    "Your credit card is no longer on file with us.")],
                    "success");
            });
        }
    },
    mounted: function(){
// XXX This shouldn't be called on billing
//        this.getUserCard();
//        this.getOrgAddress();
    }
})
}

if($('#plan-container').length > 0){
new Vue({
    el: "#plan-container",
    data: {
        formFields: {
            unit: 'usd',
        },
        title: '',
        description: '',
        unit: 'usd',
        periodAmount: '0.00',
        setupAmount: '0.00',
        interval: 'YEARLY',
        periodLength: 1,
        advanceDiscount: '0.00',
        isActive: false,
        isNotPriced: false,
        renewalType: 1 // AUTO_RENEW,
    },
    mixins: [httpRequestMixin],
    methods: {
        get: function(){
            if(!djaodjinSettings.urls.plan.api_plan) return;
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.plan.api_plan,
            function(resp) {
                vm.formFields = resp;
                vm.formFields.period_amount = vm.formatNumber(
                    resp.period_amount);
                vm.formFields.setup_amount = vm.formatNumber(
                    resp.setup_amount);
                vm.formFields.advance_discount = vm.formatNumber(
                    resp.advance_discount);
                vm.isActive = resp.is_active;
            });
        },
        formatNumber: function(num){
            return (parseFloat(num) / 100).toFixed(2);
        },
        updatePlan: function(){
            var vm = this;
            vm.validateForm();
            var data = {};
            for( var field in vm.formFields ) {
                if( vm.formFields.hasOwnProperty(field) ) {
                    data[field] = vm.formFields[field];
                }
            }
            if( data.period_amount ) {
                data.period_amount = Math.round(data.period_amount * 100);
            }
            if( data.setup_amount ) {
                data.setup_amount = Math.round(data.setup_amount * 100);
            }
            if( data.advance_discount ) {
                data.advance_discount = Math.round(data.advance_discount * 100);
            }
            if( djaodjinSettings.urls.plan &&
                djaodjinSettings.urls.plan.api_plan ) {
                vm.reqPut(djaodjinSettings.urls.plan.api_plan, data,
                function(res) {
                    showMessages([interpolate(gettext(
                        "Successfully updated plan titled '%s'."), [
                            vm.formFields.title])
                                 ], "success");
                });
            } else {
                vm.createPlan();
            }
        },
        validateForm: function(){
            var vm = this;
            var isEmpty = true;
            var fields = $(vm.$el).find('[name]').not(
                '[name="csrfmiddlewaretoken"]');
            for( var fieldIdx = 0; fieldIdx < fields.length; ++fieldIdx ) {
                var fieldName = $(fields[fieldIdx]).attr('name');
                var fieldValue = $(fields[fieldIdx]).val();
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
        togglePlanStatus: function(){
            var vm = this;
            var next = !vm.isActive;
            vm.reqPut(djaodjinSettings.urls.plan.api_plan, {is_active: next}, function(res){
                vm.isActive = next;
            });
        },
        deletePlan: function(){
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.plan.api_plan, function(res) {
                window.location = djaodjinSettings.urls.provider.metrics_plans;
            });
        },
        createPlan: function(){
            var vm = this;
            vm.validateForm();
            var data = {};
            for( var field in vm.formFields ) {
                if( vm.formFields.hasOwnProperty(field) ) {
                    data[field] = vm.formFields[field];
                }
            }
            if( data.period_amount ) {
                data.period_amount = Math.round(data.period_amount * 100);
            }
            if( data.setup_amount ) {
                data.setup_amount = Math.round(data.setup_amount * 100);
            }
            if( data.advance_discount ) {
                data.advance_discount = Math.round(data.advance_discount * 100);
            }
            vm.reqPost(djaodjinSettings.urls.provider.api_plans, data,
            function(resp) {
                window.location = djaodjinSettings.urls.provider.metrics_plans;
            });
        },
    },
    mounted: function(){
        var vm = this;
        if( !vm.validateForm() ) {
            // It seems the form is completely blank. Let's attempt
            // to load the form fields from the API then.
            vm.get();
        }
    },
});
}

if($('#plan-list-container').length > 0){
new Vue({
    el: "#plan-list-container",
    mixins: [
        itemListMixin,
        paginationMixin,
        filterableMixin,
        sortableMixin,
    ],
    data: {
        url: djaodjinSettings.urls.provider.api_plans,
    },
    mounted: function(){
        this.get();
    }
})
}
