// Copyright (c) 2020, DjaoDjin inc.
// All rights reserved.
// BSD 2-Clause license

/*global Vue jQuery moment interpolate gettext showMessages showErrorMessages djaodjinSettings Stripe updateBarChart updateChart getUrlParameter $ */


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
    var cutOff = moment();
    if( this.ends_at ) {
        cutOff = moment(this.ends_at, DATE_FORMAT);
    }
    var dateTime = moment(at_time);
    if( dateTime <= cutOff ) {
        return interpolate(gettext('%s ago'),
            [moment.duration(cutOff.diff(dateTime)).humanize()]);
    } else {
        return interpolate(gettext('%s left'),
            [moment.duration(dateTime.diff(cutOff)).humanize()]);
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


var httpRequestMixin = {
    // basically a wrapper around jQuery ajax functions
    methods: {
        _isFunction: function (func){
            // https://stackoverflow.com/a/7356528/1491475
            return func && {}.toString.call(func) === '[object Function]';
        },

        _isObject: function (obj) {
            // https://stackoverflow.com/a/46663081/1491475
            return obj instanceof Object && obj.constructor === Object
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
            var failureCallback = showErrorMessages;
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
            var failureCallback = showErrorMessages;
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
            } else if(vm._isObject(arg)){
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
            var failureCallback = showErrorMessages;
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
            var failureCallback = showErrorMessages;
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
            var failureCallback = showErrorMessages;
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
            var failureCallback = showErrorMessages;
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
            if(!vm.url) return;
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
            var fields = $(vm.$el).find('[name]').not(//XXX jQuery
                '[name="csrfmiddlewaretoken"]');
            for( var fieldIdx = 0; fieldIdx < fields.length; ++fieldIdx ) {
                var field = $(fields[fieldIdx]); // XXX jQuery
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
            itemsPerPage: djaodjinSettings.itemsPerPage,
            getCompleteCb: 'getCompleted',
            getBeforeCb: 'resetPage',
            qsCache: null,
            isInfiniteScroll: false,
        }
    },
    methods: {
        resetPage: function(){
            var vm = this;
            if(!vm.ISState) return;
            if(vm.qsCache && vm.qsCache !== vm.qs){
                vm.params.page = 1;
                vm.ISState.reset();
            }
            vm.qsCache = vm.qs;
        },
        getCompleted: function(){
            var vm = this;
            if(!vm.ISState) return;
            vm.mergeResults = false;
            if(vm.pageCount > 0){
                vm.ISState.loaded();
            }
            if(vm.params.page >= vm.pageCount){
                vm.ISState.complete();
            }
        },
        paginationHandler: function($state){
            var vm = this;
            if(!vm.ISState) return;
            if(!vm.itemsLoaded){
                // this handler is triggered on initial get too
                return;
            }
            // rudimentary way to detect which type of pagination
            // is active. ideally need to monitor resolution changes
            vm.isInfiniteScroll = true;
            var nxt = vm.params.page + 1;
            if(nxt <= vm.pageCount){
                vm.$set(vm.params, 'page', nxt);
                vm.mergeResults = true;
                vm.get();
            }
        },
    },
    computed: {
        totalItems: function(){
            return this.items.count
        },
        pageCount: function(){
            return Math.ceil(this.totalItems / this.itemsPerPage)
        },
        ISState: function(){
            if(!this.$refs.infiniteLoading) return;
            return this.$refs.infiniteLoading.stateChanger;
        },
        qs: function(){
            return this.getQueryString({page: null});
        },
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

var DESC_SORT_PRE = '-';

var sortableMixin = {
    data: function(){
        var defaultDir = djaodjinSettings.sortDirection || 'desc';
        var dir = (defaultDir === 'desc') ? DESC_SORT_PRE : '';
        var o = djaodjinSettings.sortByField || 'created_at';
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
    data: function(){
        return this.getInitData();
    },
    mixins: [
        httpRequestMixin,
        paginationMixin,
        filterableMixin,
        sortableMixin
    ],
    methods: {
        getInitData: function(){
            var data = {
                url: '',
                itemsLoaded: false,
                items: {
                    results: [],
                    count: 0
                },
                mergeResults: false,
                params: {
                    // The following dates will be stored as `String` objects
                    // as oppossed to `moment` or `Date` objects because this
                    // is how uiv-date-picker will update them.
                    start_at: null,
                    ends_at: null
                },
                getCb: null,
                getCompleteCb: null,
                getBeforeCb: null,
            }
            if( djaodjinSettings.date_range ) {
                if( djaodjinSettings.date_range.start_at ) {
                    data.params['start_at'] = moment(
                        djaodjinSettings.date_range.start_at).format(DATE_FORMAT);
                }
                if( djaodjinSettings.date_range.ends_at ) {
                    // uiv-date-picker will expect ends_at as a String
                    // but DATE_FORMAT will literally cut the hour part,
                    // regardless of timezone. We don't want an empty list
                    // as a result.
                    // If we use moment `endOfDay` we get 23:59:59 so we
                    // add a full day instead.
                    data.params['ends_at'] = moment(
                        djaodjinSettings.date_range.ends_at).add(1,'days').format(DATE_FORMAT);
                }
            }
            return data;
        },
        get: function(){
            var vm = this;
            if(!vm.url) return
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
                        showMessages([res.detail], "warning");
                    }

                    if(vm[vm.getCompleteCb]){
                        vm[vm.getCompleteCb]();
                    }
                }
            }
            if(vm[vm.getBeforeCb]){
                vm[vm.getBeforeCb]();
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
            return filter(vm.items.balance_amount, vm.items.balance_unit, 0.01);
        },
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
                f.values.map(function(v){
                    // localizing the period to local browser time
                    // unless showing reports in UTC.
                    v[0] = isUTC ? moment.parseZone(v[0]) : moment(v[0]);
                });
            });
        },
    },
}


var cardMixin = {
    mixins: [
        itemMixin
    ],
    data: function() {
        return $.extend({ // XXX jQuery
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
            updateCard: false, //used in legacy checkout
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
        }, this.getCardFormData());
    },
    methods: {
        getCardFormData: function() {
            var vm = this;
            var data = {};
            var cardForm = $("#card-use"); // XXX jQuery
            if( cardForm.length > 0 ) {
                data['card_name'] = vm.getInitValue(cardForm, 'card_name');
                data['card_address_line1'] = vm.getInitValue(cardForm, 'card_address_line1');
                data['card_city'] = vm.getInitValue(cardForm, 'card_city');
                data['ard_adress_zip'] = vm.getInitValue(cardForm, 'card_address_zip');
                data['country'] = vm.getInitValue(cardForm, 'country');
                data['region'] = vm.getInitValue(cardForm, 'region');
            }
            return data;
        },
        clearCardData: function() {
            var vm = this;
            vm.savedCard.last4 = '';
            vm.savedCard.exp_date = '';
            vm.cardNumber = '';
            vm.cardCvc = '';
            vm.cardExpMonth = '';
            vm.cardExpYear = '';
        },
        deleteCard: function() {
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.organization.api_card,
            function() {
                vm.clearCardData();
            });
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
            var cls = [];
            if( field ){
                cls.push('has-error');
            }
            return cls;
        },
        getInitValue: function(form, fieldName) {
            if( form.length > 0 ) {
                var field = form.find("[name='" + fieldName + "']");
                if( field.length > 0 ) {
                    var val = field.attr('type') === 'checkbox' ?
                        field.prop('checked') : (
                            field.val() ? field.val() : field.data('init'));
                    return val;
                }
            }
            return "";
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
            }).fail(showErrorMessages);
        },
        validateForm: function(){
            var vm = this;
            var valid = true;
            var errors = {}
            var errorMessages = "";
            vm.validate.forEach(function(field){
                if(vm[field] === ''){
                    vm[field] = vm.getInitValue($(vm.$el), field);//XXX jQuery
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
                    errorMessages += gettext("Security Code");
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
                    errorMessages += gettext("Street address");
                }
                if( vm.errors['card_city'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("City/Town");
                }
                if( vm.errors['card_adress_zip'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Zip/Postal code");
                }
                if( vm.errors['country'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("Country");
                }
                if( vm.errors['region'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += gettext("State/Province/County");
                }
                if( errorMessages ) {
                    errorMessages = interpolate(
                      gettext("%s field(s) cannot be empty."), [errorMessages]);
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
        elements = vm.$el.querySelectorAll('[data-exp-date]');
        if( elements.length > 0 ) {
            vm.savedCard.exp_date = elements[0].getAttribute('data-exp-date');
        }
    }
}

var roleDetailMixin = {
    methods: {
        acceptGrant: function(accessible){
            var vm = this;
            var url = accessible.accept_grant_api_url;
            if(!url) return;
            vm.reqPut(url, function() { vm.get(); });
        },
        sendInvite: function(slug){
            var vm = this;
            vm.reqPost(vm.url + '/' + slug + '/', {}, function() {
                showMessages([interpolate(gettext(
                    "Invite for %s has been sent"), [slug])],
                    "success");
            });
        },
    }
}


var roleListMixin = {
    mixins: [
        itemListMixin,
        roleDetailMixin
    ],
    data: function(){
        return {
            url: null,
            create_url: null,
            typeaheadUrl: null,
            showInvited: false,
            showRequested: false,
            profileRequestDone: false,
            inNewProfileFlow: false,
            unregistered: {
                slug: '',
                email: '',
                full_name: ''
            },
            newProfile: {
                slug: '',
                email: '',
                full_name: ''
            }
        }
    },
    methods: {
        _addRole: function(item, force) {
            var vm = this;
            if( jQuery.type(item) === "string" ) {
                var stringVal = item;
                item = {slug: "", email: "", full_name: ""};
                var pattern = /@[a-zA-Z\-]+\.[a-zA-Z\-]{2,3}/;
                if( pattern.test(stringVal) ) {
                    item['email'] = stringVal;
                } else {
                    item['slug'] = stringVal;
                }
            }
            var data = {};
            var fields = ['slug', 'email', 'full_name', 'message'];
            for( var idx = 0; idx < fields.length; ++idx ) {
                if( item[fields[idx]] ) {
                    data[fields[idx]] = item[fields[idx]];
                }
            }
            vm.reqPost(vm.url + (force ? "?force=1" : ""), data,
                function() {
                    vm.clearRequestProfile();
                    vm.refresh();
                }, function() {
                    vm.profileRequestDone = true;
                    vm.unregistered = item;
                    vm.$emit('invite');
                }
            );
        },
        clearRequestProfile: function() {
            var vm = this;
            vm.unregistered = {slug: "", email: "", full_name: ""};
            vm.profileRequestDone = false;
            if( vm.$refs.typeahead ) {
                vm.$refs.typeahead.clear();
            }
            vm.$emit('invite-completed');
        },
        clearNewProfile: function() {
            var vm = this;
            vm.newProfile = {slug: "", email: "", full_name: ""};
            vm.inNewProfileFlow = false;
            vm.$emit('create-completed');
        },
        create: function() { // create a new profile to be owned by user.
            var vm = this;
            vm.clearRequestProfile();
            if( !vm.inNewProfileFlow ) {
                vm.inNewProfileFlow = true;
                vm.$emit('create');
            } else {
                if( jQuery.type(vm.newProfile) === "string" ) {
                    var stringVal = vm.newProfile;
                    vm.newProfile = {slug: "", email: "", full_name: ""};
                    var pattern = /@[a-zA-Z\-]+\.[a-zA-Z\-]{2,3}/;
                    if( pattern.test(stringVal) ) {
                        vm.newProfile['email'] = stringVal;
                    } else {
                        vm.newProfile['slug'] = stringVal;
                    }
                }
                var data = {};
                var fields = ['slug', 'email', 'full_name'];
                for( var idx = 0; idx < fields.length; ++idx ) {
                    if( vm.newProfile[fields[idx]] ) {
                        data[fields[idx]] = vm.newProfile[fields[idx]];
                    }
                }
                vm.reqPost(vm.create_url, data,
                    function() {
                        vm.clearNewProfile();
                        vm.refresh();
                    }
                );
            }
        },
        updateItemSelected: function(item) { // user-typeahead @item-selected="updateItemSelected"
            var vm = this;
            if( item ) {
                vm.unregistered = item;
                vm.profileRequestDone = false;
                vm.clearNewProfile();
            }
        },
        refresh: function() {
            // overridden in subclasses.
        },
        remove: function(idx){ // saas/_user_card.html
            var vm = this;
            var ob = vm.items.results[idx];
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
            vm.reqDelete(ob.remove_api_url, function() {
                // splicing instead of refetching because
                // subsequent fetch might fail due to 403
                vm.items.results.splice(idx, 1);
                if( ob.grant_key ) { vm.items.invited_count -= 1; }
                if( ob.request_key ) { vm.items.requested_count -= 1; }
            });
        },
        save: function(item){ // user-typeahead @item-save="save"
            this._addRole(item);
        },
        submit: function() {
            var vm = this;
            this._addRole(vm.unregistered, vm.profileRequestDone);
        },
        updateParams: function(){ // internal
            var vm = this;
            vm.params.role_status = vm.roleStatus;
            if(vm.showInvited || vm.showRequested){
                vm.params.o = ['-grant_key', '-request_key'];
            }
            vm.get();
        },
    },
    computed: {
        roleStatus: function() {
            var args = ['active'];
            if(this.showInvited) args.push('invited');
            if(this.showRequested) args.push('requested');
            return args.join(',');
        },
        requestedProfilePrintableName: function() {
            var vm = this;
            if( typeof vm.unregistered !== 'undefined' ) {
                if( jQuery.type(vm.unregistered) === "string" ) {
                    return vm.unregistered ? vm.unregistered : "The profile";
                }
                if( typeof vm.unregistered.full_name !== 'undefined' &&
                    vm.unregistered.full_name ) {
                    return vm.unregistered.full_name;
                }
                if( typeof vm.unregistered.email !== 'undefined' &&
                    vm.unregistered.email ) {
                    return vm.unregistered.email;
                }
            }
            return  "The profile";
        }
    },
    watch: {
        showInvited: function() {
            this.updateParams();
        },
        showRequested: function() {
            this.updateParams();
        },
    },
    mounted: function(){
        this.get()
    }
}


var subscriptionDetailMixin = {
    data: function(){
        return {
            ends_at: moment().endOf("day").format(DATE_FORMAT),
        }
    },
    methods: {
        acceptRequest: function(organization, request_key) {
            var vm = this;
            var url = (djaodjinSettings.urls.organization.api_profile_base +
                organization + "/subscribers/accept/" + request_key + "/");
            vm.reqPost(url, function (){
                vm.get();
            });
        },
        editDescription: function(item, id){
            var vm = this;
            vm.$set(item, 'edit_description', true);
            // at this point the input is rendered and visible
            vm.$nextTick(function(){
                var ref = vm.refId(item, id);
                vm.$refs[ref][0].focus();
            });
        },
        endsSoon: function(subscription) {
            var vm = this;
            var cutOff = moment(vm.ends_at, DATE_FORMAT).add(5, 'days');
            var subEndsAt = moment(subscription.ends_at);
            if( subEndsAt < cutOff ) {
                return "bg-warning";
            }
            return "";
        },
        refId: function(item, id){
            var ids = [item.organization.slug,
                item.plan.slug, id];
            return ids.join('_').replace(new RegExp('[-:]', 'g'), '');
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
            this.update(item);
        },
        subscriptionURL: function(organization, plan) {
            return djaodjinSettings.urls.organization.api_profile_base
                + organization + "/subscriptions/" + plan;
        },
        update: function(item) {
            var vm = this;
            var url = vm.subscriptionURL(
                item.organization.slug, item.plan.slug);
            var data = {
                description: item.description,
                ends_at: item.ends_at
            };
            vm.reqPatch(url, data);
        },
    },
}


var subscriptionListMixin = {
    mixins: [
        itemListMixin,
        subscriptionDetailMixin
    ],
    data: function() {
        return {
            typeaheadUrl: null,
            url: null,
            newProfile: {},
            plan: {},
            params: {
            },
            toDelete: {
                plan: null,
                org: null
            },
        }
    },
    methods: {
        _resolve: function (o, s){
            return s.split('.').reduce(function(a, b) {
                return a[b];
            }, o);
        },
        create: function(){
            var vm = this;
            vm.reqPost(vm.url + "?force=1", vm.newProfile,
            function() {
                vm.get();
            });
        },
        groupBy: function (list, groupBy) {
            var vm = this;
            var res = {};
            list.forEach(function(item){
                var value = vm._resolve(item, groupBy);
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
        save: function(item){
            var vm = this;
            var slug = item.slug ? item.slug : item.toString();
            vm.reqPost(vm.url, {slug: slug},
                function() {
                    vm.get();
                },
                function() {
                    if(slug.length > 0){
                        vm.newProfile = {
                            slug: slug,
                            email: slug,
                            full_name: slug
                        }
                        vm.modalShow();
                    }
                }
            );
        },
        subscribe: function(org){ // XXX same as `save`?
            var vm = this;
            var url = vm.subscribersURL(vm.plan.organization, vm.plan.slug);
            var data = {
                organization: {
                  slug: org
                }
            }
            vm.reqPost(url, data, function (){
                vm.get();
            });
        },
        selected: function(idx){
            var item = this.items.results[idx];
            item.ends_at = (new Date(item.ends_at)).toISOString();
            this.update(item);
        },
        subscribersURL: function(provider, plan) {
            return djaodjinSettings.urls.organization.api_profile_base + provider + "/plans/" + plan + "/subscriptions/";
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
        unsubscribeConfirm: function(org, plan) {
            this.toDelete = {
                org: org,
                plan: plan
            }
        },
    },
    mounted: function(){
        this.get();
    }
}

Vue.component('user-typeahead', {
    template: "",
    props: ['url', 'role'],
    data: function() {
        return {
            target: null,
            searching: false,
            // used in a http request
            typeaheadQuery: '',
            itemSelected: ""
        }
    },
    mixins: [
        httpRequestMixin
    ],
    computed: {
        params: function(){
            var res = {}
            if(this.typeaheadQuery) res.q = this.typeaheadQuery;
            return res
        },
    },
    methods: {
        clear: function() {
            this.itemSelected = '';
        },
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
            this.clear();
        }
    },
    mounted: function() {
        // TODO we should probably use one interface everywhere
        if(this.$refs.tphd)
            this.target = this.$refs.tphd[0];
    },
    watch: {
        itemSelected: function(val) {
            this.$emit('item-selected', this.itemSelected);
        }
    }
});


var couponDetailMixin = {
    methods: {
        update: function(coupon, cb) {
            var vm = this;
            vm.reqPut(vm.url + '/' + coupon.code, coupon,
            function(){
                vm.get();
                if(cb) cb();
            });
        },
        editPlan: function(item){
            var vm = this;
            vm.$set(item, '_editPlan', true);
            vm.$nextTick(function(){
                vm.$refs['editPlan_' + item.code][0].focus();
            });
        },
        savePlan: function(item){
            var vm = this;
            if(!item._editPlan) return;
            vm.update(item, function(){
                vm.$set(item, '_editPlan', false);
                delete item._editPlan;
            });
        },
        editAttempts: function(item){
            var vm = this;
            vm.$set(item, '_editAttempts', true);
            vm.$nextTick(function(){
                vm.$refs['editAttempts_' + item.code][0].focus();
            });
        },
        saveAttempts: function(item){
            var vm = this;
            if(!item._editAttempts) return;
            vm.update(item, function(){
                vm.$set(item, '_editAttempts', false);
                delete item._editAttempts;
            })
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
    }
}


Vue.component('coupon-list', {
    mixins: [
        itemListMixin,
        couponDetailMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_coupons,
            params: {
                o: 'ends_at',
            },
            newCoupon: {
                code: '',
                percent: ''
            },
            edit_description: [],
            date: null,
            plans: []
        }
    },
    methods: {
        remove: function(idx){
            var vm = this;
            var code = this.items.results[idx].code;
            vm.reqDelete(vm.url + '/' + code,
            function() {
                vm.get();
            });
        },
        save: function(){
            var vm = this;
            vm.reqPost(vm.url, vm.newCoupon,
            function() {
                vm.get();
                vm.newCoupon = {
                    code: '',
                    percent: ''
                }
            });
        },
        getPlans: function(){
            var vm = this;
            vm.reqGet(djaodjinSettings.urls.provider.api_plans,
                {active: true}, function(res){
                vm.plans = res.results;
            });
        },
        selected: function(idx){
            var coupon = this.items.results[idx];
            if( coupon.ends_at ) {
                coupon.ends_at = (new Date(coupon.ends_at)).toISOString();
            } else {
                coupon.ends_at = null;
            }
            this.update(coupon);
        },
        planTitle: function(slug){
            var title = gettext('No plan');
            if(this.plans.length > 0){
                this.plans.forEach(function(e){
                    if(e.slug === slug){
                        title = e.title;
                        return;
                    }
                });
            }
            return title;
        },
    },
    mounted: function(){
        this.get()
        this.getPlans()
    }
});


Vue.component('user-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_accounts,
            params: {
                start_at: moment().startOf('day'),
                o: '-created_at'
            }
        }
    },

    mounted: function(){
        this.get()
    }
});


/** Profiles accessible, granted or requested by a user.
 */
Vue.component('role-profile-list', {
    mixins: [
        roleListMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.user.api_accessibles,
            create_url: djaodjinSettings.urls.user.api_profile_create,
            typeaheadUrl: djaodjinSettings.urls.api_candidates,
            showInvited: false,
            showRequested: false,
            params: {
                role_status: "",
            },
        }
    },
    methods: {
        refresh: function() {
            var vm = this;
            vm.params = {};
            vm.get();
        },
    },
});


/** Users who have a role, have been granted or requested a role on a profile.
 */
Vue.component('role-user-list', {
    mixins: [
        roleListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.organization.api_roles,
            typeaheadUrl: djaodjinSettings.urls.api_candidates,
            params: {
                role_status: 'active',
            },
        }
    },
    methods: {
        refresh: function() {
            var vm = this;
            vm.showInvited = true;
        },
    },
});


Vue.component('metrics-charts', {
    mixins: [
        httpRequestMixin,
        timezoneMixin
    ],
    data: function() {
        var data = {
            tables: djaodjinSettings.tables,
            activeTab: 0,
            params: {
                ends_at: moment(),
            },
        }
        if( djaodjinSettings.date_range
            && djaodjinSettings.date_range.ends_at ) {
            var ends_at = moment(djaodjinSettings.date_range.ends_at);
            if(ends_at.isValid()){
                data.params.ends_at = ends_at;
            }
        }
        data.params.ends_at = data.params.ends_at.format(DATE_FORMAT);
        return data;
    },
    methods: {
        fetchTableData: function(table, cb){
            var vm = this;
            var params = {"ends_at": moment(vm.params.ends_at, DATE_FORMAT).toISOString()};
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
        // an alias for consistent method usage in datepickers templates
        get: function(){
            this.prepareCurrentTabData();
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
});


Vue.component('registered', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.broker.api_users_registered,
        }
    },
    mounted: function(){
        this.get();
    },
});


Vue.component('subscribed', {
    mixins: [
        subscriptionListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_subscribers_active,
        }
    }
});


Vue.component('churned', {
    mixins: [
        subscriptionListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_subscribers_churned,
        }
    }
});


Vue.component('plan-subscriber-list', {
    mixins: [
        subscriptionListMixin
    ],
    data: function() {
        return {
            newProfile: {},
            typeaheadUrl: djaodjinSettings.urls.api_candidates,
            url: djaodjinSettings.urls.provider.api_plan_subscribers,
        }
    }
});


Vue.component('subscription-list', {
    mixins: [
        subscriptionListMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.organization.api_subscriptions,
            params: {
                state: 'active',
            },
        }
    }
});


Vue.component('expired-subscription-list', {
    mixins: [
        subscriptionListMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.organization.api_subscriptions,
            params: {
                state: 'expired',
            },
        }
    }
});


/*
    We nedd to communicate the unsubscribe event from the <subscription-list>
    to the <expired-subscription-list>. We use `events` and `refs` to do that.
*/
Vue.component('subscription-list-container', {
    data: function() {
        return {
        }
    },
    methods: {
        expired: function() {
            this.$refs.expired.get();
        }
    }
});


Vue.component('coupon-user-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_metrics_coupon_uses,
            params: {
                o: '-created_at',
            },
        }
    },
    mounted: function(){
        this.get()
    }
});


Vue.component('charge-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.broker.api_charges,
        }
    },
    mounted: function(){
        this.get();
    }
});


Vue.component('plan-list', {
    mixins: [
        itemListMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_plans,
        }
    },
    mounted: function(){
        this.get();
    }
});


Vue.component('import-transaction', {
    mixins: [
        httpRequestMixin
    ],
    data: function() {
        return {
            typeaheadUrl: djaodjinSettings.urls.provider.api_subscribers_active,
            createdAt: moment().format("YYYY-MM-DD"),
            itemSelected: '',
            searching: false,
            amount: 0,
            description: '',
        }
    },
    methods: {
        getSubscriptions: function(query, done) {
            var vm = this;
            vm.searching = true;
            vm.reqGet(vm.typeaheadUrl, {q: query}, function(res){
                vm.searching = false;
                // current typeahead implementation does not
                // support dynamic keys that's why we are
                // creating them here
                res.results.forEach(function(e){
                    e.itemKey = e.organization.slug + ':' + e.plan.slug
                });
//XXX                done(res.results)
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


Vue.component('billing-statement', {
    mixins: [
        itemListMixin,
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
            vm.params.o = '-created_at';
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
                    showErrorMessages(resp);
                }
            );
        }
    },
    mounted: function(){
        this.getCard();
        this.get();
    }
});


Vue.component('transfers-statement', {
    mixins: [
        itemListMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.organization.api_transactions,
            balanceLoaded: false,
            last4: gettext("N/A"),
            bank_name: gettext("N/A"),
            balance_amount: gettext("N/A"),
            balance_unit: '',
        }
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
});


Vue.component('transaction-list', {
    mixins: [
        itemListMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.organization.api_transactions,
        }
    },
    mounted: function(){
        this.get();
    },
});


Vue.component('profile-update', {
    mixins: [
        itemMixin,
    ],
    data: function() {
        return {
            formFields: {},
            countries: countries,
            regions: regions,
            currentPicture: null,
            picture: null,
        }
    },
    methods: {
        deleteProfile: function(){
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.organization.api_base,
                function() {
                    window.location = djaodjinSettings.urls.profile_redirect;
                }
            );
        },
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
            vm.reqPut(djaodjinSettings.urls.organization.api_base, vm.formFields,
            function() {
                showMessages([gettext("Profile was updated.")], "success");
            });
            if(vm.imageSelected){
                vm.uploadProfilePicture();
            }
        },
        uploadProfilePicture: function() {
            var vm = this;
            vm.picture.generateBlob(function(blob){
                if(!blob) return;
                var form = new FormData();
                form.append('file', blob, vm.picture.getChosenFile().name);
                vm.reqPostBlob(
                    djaodjinSettings.urls.organization.api_profile_picture,
                    form,
                    function(resp) {
                        vm.formFields.picture = resp.location;
                        vm.picture.remove();
                        vm.$forceUpdate();
                        showMessages(["Profile was updated."], "success");
                });
            }, 'image/jpeg');
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


Vue.component('roledescr-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.organization.api_role_descriptions,
            role: {
                title: '',
            },
        }
    },
    methods: {
        create: function(){
            var vm = this;
            vm.reqPost(vm.url, vm.role,
            function() {
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
});


Vue.component('balance-list', {
    mixins: [
        itemListMixin,
        timezoneMixin,
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.api_broker_balances,
            balanceLineUrl : djaodjinSettings.urls.api_balance_lines,
            startPeriod: moment().subtract(1, 'months').toISOString(),
            balanceLine: {
                title: '',
                selector: '',
                rank: 0,
            },
        }
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
            vm.reqPost(vm.balanceLineUrl, vm.balanceLine,
            function() {
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
});


Vue.component('checkout', {
    mixins: [
        cardMixin,
        itemListMixin
    ],
    data: function() {
        return {
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
        }
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
            vm.reqDelete(url, {plan: plan},
            function() {
                vm.get()
            });
        },
        redeem: function(){
            var vm = this;
            vm.reqPost(djaodjinSettings.urls.api_redeem_coupon, {
                code: vm.coupon },
            function() {
                showMessages([gettext("Discount was successfully applied.")],
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
            function() {
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
            var vm = this;
            var form = $(vm.$el).find('form'); // XXX jQuery
            if(token){
                form.append("<input type='hidden' name='stripeToken' value='" + token + "'/>");
            }
            form.get(0).submit();
        },
        // used in legacy checkout
        checkoutForm: function() {
            var vm = this;
            var cardUse = $('#card-use'); // XXX jQuery
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
            var form = new FormData();
            form.append("file", vm.csvFiles[plan]);
            vm.reqPostBlob("/api/cart/" + plan + "/upload/",
                form,
                function(){
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
        var cardData = vm.getCardFormData();
        if( !$.isEmptyObject(cardData) ) { // XXX jQuery
            vm.card_name = cardData['card_name'];
            vm.card_address_line1 = cardData['card_address_line1'];
            vm.card_city = cardData['card_city'];
            vm.card_adress_zip = cardData['card_address_zip'];
            vm.country = cardData['country'];
            vm.region = cardData['region'];
        } else {
            vm.getOrgAddress();
        }
    }
});


Vue.component('card-update', {
    mixins: [
        cardMixin
    ],
    data: function() {
        return {
            updateCard: true,
        }
    },
    methods: {
        remove: function() {
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.organization.api_card,
            function() {
                vm.clearCardData();
                showMessages([gettext(
                    "Your credit card is no longer on file with us.")],
                    "success");
            });
        },
        save: function(){
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
                if( redirectUrl ) {
                    window.location = redirectUrl;
                }
                showMessages([gettext(
                    "Your credit card on file was sucessfully updated.")],
                    "success");
                });
            });
        },
    },
    mounted: function(){
// XXX This shouldn't be called on billing
//        this.getUserCard();
//        this.getOrgAddress();
    }
});


Vue.component('plan-update', {
    mixins: [
        itemMixin,
    ],
    data: function() {
        return {
            formFields: {
                unit: 'usd',
            },
            isActive: false,
        }
    },
    methods: {
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
            function() {
                window.location = djaodjinSettings.urls.provider.metrics_plans;
            });
        },
        deletePlan: function(){
            var vm = this;
            vm.reqDelete(djaodjinSettings.urls.plan.api_plan,
            function() {
                window.location = djaodjinSettings.urls.provider.metrics_plans;
            });
        },
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
        togglePlanStatus: function(){
            var vm = this;
            var next = !vm.isActive;
            vm.reqPut(djaodjinSettings.urls.plan.api_plan, {is_active: next},
            function(){
                vm.isActive = next;
            });
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
                function() {
                    showMessages([interpolate(gettext(
                        "Successfully updated plan titled '%s'."), [
                            vm.formFields.title])
                                 ], "success");
                });
            } else {
                vm.createPlan();
            }
        },
    },
    mounted: function(){
        var vm = this;
        if( !vm.validateForm() ) {
            // It seems the form is completely blank. Let's attempt
            // to load the form fields from the API then.
            vm.get();
        } else {
            var activateBtn = vm.$el.querySelector("#activate-plan");
            if( activateBtn) {
                vm.isActive = parseInt(activateBtn.value);
            }
        }
    },
});


// Widgets for dashboard
// ---------------------

Vue.component('search-profile', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_accounts,
        }
    },
});


Vue.component('today-sales', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: djaodjinSettings.urls.provider.api_receivables,
            params: {
                start_at: moment().startOf('day'),
                o: '-created_at',
            }
        }
    },
    mounted: function(){
        this.get()
    }
});


Vue.component('monthly-revenue', {
    mixins: [
        itemMixin
    ],
    data: function(){
        return {
            url: djaodjinSettings.urls.provider.api_revenue,
        }
    },
    computed: {
        amount: function(){
            var amount = 0;
            if(this.itemLoaded){
                this.item.table.forEach(function(e){
                    if(e.key === 'Total Sales'){
                        // get MRR from last month
                        amount = e.values[e.values.length - 2][1];
                    }
                });
            }
            return amount;
        }
    },
    mounted: function(){
        this.get();
    }
});

