// Copyright (c) 2023, DjaoDjin inc.
// All rights reserved.
// BSD 2-Clause license

/*global Vue jQuery moment showMessages showErrorMessages Stripe updateBarChart updateChart getUrlParameter $ */


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


var timezoneMixin = {
    data: function(){
        return {
            timezone: moment.tz.guess(),
        }
    },
    methods: {
        // Used to be filters but Vue3 will not allow it.
        asPeriodHeading: function(atTime, periodType, tzString) {
            var datetime = null;
            if( typeof atTime === 'string' ) {
                datetime = new Date(atTime);
            } else {
                datetime = new Date(atTime.valueOf());
            }
            // `datetime` contains aggregated metrics before
            // (not including) `datetime`.
            datetime = new Date(datetime.valueOf() - 1);
            if( typeof tzString === 'undefined' ) {
                tzString = "UTC";
            }
            // `datetime` is in UTC but the heading must be printed
            // in the provider timezone, and not the local timezone
            // of the browser.
            datetime = datetime.toLocaleString('en-US', {
                year: 'numeric', month: '2-digit', day: '2-digit',
                hour: '2-digit', minute: '2-digit', second: '2-digit',
                hour12: false,
                timeZone: tzString});
            const regx = new RegExp(
                '(?<month>\\d\\d)/(?<day>\\d\\d)/(?<year>\\d\\d\\d\\d), (?<hour>\\d\\d):(?<minute>\\d\\d):(?<second>\\d\\d)');
            const parts = regx.exec(datetime);
            const year = parseInt(parts.groups['year']);
            const monthIndex = parseInt(parts.groups['month']) - 1;
            const day = parseInt(parts.groups['day']);
            const hour = parseInt(parts.groups['hour']);
            const minute = parseInt(parts.groups['minute']);
            const second = parseInt(parts.groups['second']);
            const lang = navigator.language;
            if( periodType == 'yearly' ) {
                return parts.groups['year'] + (
                    monthIndex !== 11 ? '*' : '');
            }
            if( periodType == 'monthly' ) {
                const dateTimeFormat = new Intl.DateTimeFormat(lang, {
                    year: 'numeric',
                    month: 'short'
                });
                return dateTimeFormat.format(
                    new Date(year, monthIndex)) + ((hour !== 23 &&
                     minute !== 59 && second !== 59)  ? '*' : '');
            }
            if( periodType == 'weekly' ) {
                const dateTimeFormat = new Intl.DateTimeFormat(lang, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    weekday: 'short'
                });
                return dateTimeFormat.format(
                    new Date(year, monthIndex, day)) + ((hour !== 23 &&
                     minute !== 59 && second !== 59)  ? '*' : '');
            }
            if( periodType == 'daily' ) {
                const dateTimeFormat = new Intl.DateTimeFormat(lang, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    weekday: 'short'
                });
                return dateTimeFormat.format(
                    new Date(year, monthIndex, day)) + ((hour !== 23 &&
                     minute !== 59 && second !== 59)  ? '*' : '');
            }
            if( periodType == 'hourly' ) {
                const dateTimeFormat = new Intl.DateTimeFormat(lang, {
                    year: 'numeric',
                    month: 'numeric',
                    day: 'numeric',
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                    hour12: false,
                });
                return dateTimeFormat.format(
                    new Date(year, monthIndex, day, hour)) + ((minute !== 59 &&
                        second !== 59)  ? '*' : '');
            }
            return datetime.toISOString();
        },
        datetimeOrNow: function(dateISOString, offset) {
            var dateTime = moment(dateISOString);
            if( dateTime.isValid() ) {
                return dateISOString;
            }
            if( offset === "startOfDay" ) {
                return moment().startOf('day').toISOString();
            } else if( offset === "endOfDay" ) {
                return moment().endOf('day').toISOString();
            }
            return moment().toISOString();
        },
        // Same as itemListMixin
        asDateInputField: function(dateISOString) {
            const dateValue = moment(dateISOString);
            return dateValue.isValid() ? dateValue.format("YYYY-MM-DD") : null;
        },
        asDateISOString: function(dateInputField) {
            const dateValue = moment(dateInputField, "YYYY-MM-DD");
            return dateValue.isValid() ? dateValue.toISOString() : null;
        }
    },
}


var cardMixin = {
    mixins: [
        httpRequestMixin
    ],
    data: function() {
        return $.extend({ // XXX jQuery
            api_card_url: this.$urls.organization.api_card,
            api_profile_url: this.$urls.organization.api_base,
            processor_pub_key: null,
            stripe_intent_secret: null,
            stripe_account: null,
            stripe: null,
            cardNumber: '',
            cardCvc: '',
            cardExpMonth: '',
            cardExpYear: '',
            card_name: '',
            card_address_line1: '',
            card_city: '',
            card_address_zip: '',
            country: '',
            region: '',
            savedCard: {
                last4: '',
                exp_date: '',
            },
            countries: countries,
            regions: regions,
            profile: {},
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
                'card_address_zip',
                'country',
                'region',
            ],
            labels: {
                cardNumberLabel: (this.$labels && this.$labels.cardNumberLabel) || "Card Number",
                securityCodeLabel: (this.$labels && this.$labels.securityCodeLabel) || "Security Code",
                expirationLabel: (this.$labels && this.$labels.expirationLabel) || "Expiration",
                cardHolderLabel: (this.$labels && this.$labels.cardHolderLabel) || "Card Holder",
                streetAddressLabel: (this.$labels && this.$labels.streetAddressLabel) || "Street address",
                localityLabel: (this.$labels && this.$labels.localityLabel) || "City/Town",
                regionLabel: (this.$labels && this.$labels.regionLabel) || "State/Province/County",
                postalCodeLabel: (this.$labels && this.$labels.postalCodeLabel) || "Zip/Postal code",
                countryLabel: (this.$labels && this.$labels.countryLabel) || "Country",
                fieldShoundNotBeEmptyError: (this.$labels && this.$labels.fieldShoundNotBeEmptyError) || "This field shouldn't be empty",
                fieldsCannotBeEmptyError: (this.$labels && this.$labels.fieldsCannotBeEmptyError) || " field(s) cannot be empty."
            }
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
            vm.reqDelete(vm.api_card_url,
            function(resp) {
                vm.clearCardData();
                if( resp.detail ) {
                    showMessages([resp.detail], "success");
                }
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
            vm.reqGet(vm.api_card_url,
            function(resp) {
                if( resp.last4 ) {
                    vm.savedCard.last4 = resp.last4;
                }
                if( resp.exp_date ) {
                    vm.savedCard.exp_date = resp.exp_date;
                }
                if( resp.processor && resp.processor.STRIPE_PUB_KEY ) {
                    vm.processor_pub_key = resp.processor.STRIPE_PUB_KEY;
                }
                if( resp.processor && resp.processor.STRIPE_INTENT_SECRET ) {
                    vm.stripe_intent_secret = resp.processor.STRIPE_INTENT_SECRET;
                }
                if( resp.processor && resp.processor.STRIPE_ACCOUNT ) {
                    vm.stripe_account = resp.processor.STRIPE_ACCOUNT;
                }
                if( vm.processor_pub_key ) {
                    if( vm.stripe_account ) {
                        vm.stripe = Stripe(vm.processor_pub_key, {
                            stripeAccount: vm.stripe_account
                        });
                    } else {
                        vm.stripe = Stripe(vm.processor_pub_key);
                    }
                    if( vm.stripe_intent_secret ) {
                        var elements = vm.stripe.elements();
                        vm.cardElement = elements.create("card", {
                            hidePostalCode: true
                        });
                        vm.cardElement.mount("#card-element");
                    }
                }
            });
        },
        getCardToken: function(cb){
            var vm = this;
            // this identifies your website in the createToken call below
            if( vm.stripe_intent_secret ) {
                if( !vm.stripe ){
                    showErrorMessages("You haven't set a valid Stripe public key");
                    return;
                }
                if( vm.stripe_intent_secret.substring(0, 3) === 'pi_' ) {
                    vm.stripe.confirmCardPayment(
                        vm.stripe_intent_secret, {
                            payment_method: {
                                type: "card",
                                card: vm.cardElement,
                                billing_details: {
                                    address: {
                                        city: vm.card_city,
                                        country: vm.country,
                                        line1: vm.card_address_line1,
                                        // line2: null,
                                        postal_code: vm.card_address_zip,
                                        state: vm.region,
                                    },
                                    name: vm.card_name,
                                }
                            }
                        }
                    ).then(function(resp) {
                        vm.stripeResponseHandler(resp, cb);
                    });
                } else {
                    vm.stripe.confirmCardSetup(
                        vm.stripe_intent_secret, {
                            payment_method: {
                                type: "card",
                                card: vm.cardElement,
                                billing_details: {
                                    address: {
                                        city: vm.card_city,
                                        country: vm.country,
                                        line1: vm.card_address_line1,
                                        // line2: null,
                                        postal_code: vm.card_address_zip,
                                        state: vm.region,
                                    },
                                    name: vm.card_name,
                                }
                            }
                        }
                    ).then(function(resp) {
                        vm.stripeResponseHandler(resp, cb);
                    });
                }
            } else if( vm.validateForm() ) {
                // use https://js.stripe.com/v2/
                Stripe.setPublishableKey(vm.processor_pub_key);
                Stripe.createToken({
                    number: vm.cardNumber,
                    cvc: vm.cardCvc,
                    exp_month: vm.cardExpMonth,
                    exp_year: vm.cardExpYear,
                    name: vm.card_name,
                    address_line1: vm.card_address_line1,
                    address_city: vm.card_city,
                    address_state: vm.region,
                    address_zip: vm.card_address_zip,
                    address_country: vm.country
                }, function(status, resp) {
                    vm.stripeResponseHandler(resp, cb);
                });
            }
        },
        stripeResponseHandler: function(resp, cb) {
            var vm = this;
            if( resp.error ) {
                showMessages([resp.error.message], "error");
            } else {
                var token = resp.id;
                if( !token && resp.paymentIntent ) {
                    token = resp.paymentIntent.id;
                }
                if( !token && resp.setupIntent ) {
                    token = resp.setupIntent.id;
                }
                if(vm.cardElement) vm.cardElement.clear();
                if(cb) {
                    cb(token);
                }
            }
        },
        getOrgAddress: function(){
            var vm = this;
            vm.reqGet(vm.api_profile_url, function(org) {
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
                    vm.card_address_zip = org.postal_code;
                }
                if(org.country){
                    vm.country = org.country;
                }
                if(org.region){
                    vm.region = org.region;
                }
                vm.profile = org;
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
                    errors[field] = [vm.labels.fieldShoundNotBeEmptyError];
                }
            });
            vm.errors = errors;
            if(Object.keys(vm.errors).length > 0){
                if( vm.errors['cardNumber'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.cardNumberLabel;
                }
                if( vm.errors['cardCvc'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.securityCodeLabel;
                }
                if( vm.errors['cardExpMonth']
                         || vm.errors['cardExpYear'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.expirationLabel;
                }
                if( vm.errors['card_name'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages +=  vm.labels.cardHolderLabel;
                }
                if( vm.errors['card_address_line1'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.streetAddressLabel;
                }
                if( vm.errors['card_city'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.localityLabel;
                }
                if( vm.errors['card_address_zip'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.regionLabel;
                }
                if( vm.errors['country'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.countryLabel;
                }
                if( vm.errors['region'] ) {
                    if( errorMessages ) { errorMessages += ", "; }
                    errorMessages += vm.labels.postalCodeLabel;
                }
                if( errorMessages ) {
                    errorMessages = errorMessages + vm.labels.fieldsCannotBeEmptyError;
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
        vm.processor_pub_key = vm.$el.getAttribute('data-processor-pub-key');
        vm.stripe_intent_secret = vm.$el.getAttribute(
            'data-stripe-intent-secret');
        vm.stripe_account =  vm.$el.getAttribute('data-stripe-account');
        if( vm.processor_pub_key ) {
            if( vm.stripe_account ) {
                vm.stripe = Stripe(vm.processor_pub_key, {
                    stripeAccount: vm.stripe_account
                });
            } else {
                vm.stripe = Stripe(vm.processor_pub_key);
            }
            if( vm.stripe_intent_secret ) {
                var elements = vm.stripe.elements();
                vm.cardElement = elements.create("card", {
                    hidePostalCode: true
                });
                vm.cardElement.mount("#card-element");
            }
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
            vm.reqPost(vm.url + '/' + slug + '/', {}, function(resp) {
                showMessages([resp.detail], "success");
            });
        },
    }
}


/** list users with roles on a profile or profiles connected to a user.
 */
var roleListMixin = {
    mixins: [
        itemListMixin,
        roleDetailMixin
    ],
    props: [
        'requestUser'
    ],
    data: function(){
        return {
            url: null,
            create_url: null,
            typeaheadUrl: null,
            params: {
                role_status: '',
            },
            showInvited: false,
            showRequested: false,
            profileRequestDone: false,
            inNewProfileFlow: false,
            candidateId: "",
            unregistered: {
                slug: '',
                email: '',
                full_name: ''
            },
            newProfile: {
                slug: '',
                email: '',
                full_name: ''
            },
            toDelete: {
                idx: null
            },
        }
    },
    methods: {
        _addRole: function(item, force) {
            var vm = this;
            if( jQuery.type(item) === "string" ) {
                var stringVal = item;
                item = {slug: "", email: "", full_name: ""};
                var pattern = /@[a-zA-Z0-9\-]+\.([a-zA-Z\-]{2,3}|localdomain)/;
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
            vm.candidateId = "";
            vm.unregistered = {slug: "", email: "", full_name: ""};
            vm.profileRequestDone = false;
            if( vm.$refs.typeahead ) {
                vm.$refs.typeahead.reset();
            }
            vm.$emit('invite-completed');
        },
        clearNewProfile: function() {
            var vm = this;
            vm.newProfile = {slug: "", email: "", full_name: ""};
            vm.inNewProfileFlow = false;
            if( vm.$refs.typeahead ) {
                vm.$refs.typeahead.reset();
            }
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
                    function(resp) {
                        vm.clearNewProfile();
                        const queryString = window.location.search;
                        const params = new URLSearchParams(queryString);
                        const next = params.get('next');
                        if( next ) {
                            const redirectTo = next.replace(
                                '/:profile/', '/' + resp.slug + '/');
                            window.location = redirectTo
                        } else {
                            vm.refresh();
                        }
                    }
                );
            }
        },
        updateItemSelected: function(item) {
            var vm = this;
            if( item ) {
                vm.unregistered = item;
                vm.profileRequestDone = false;
                vm.submit();
            } else {
                vm.newProfile.full_name = vm.$refs.typeahead.query;
                vm.newProfile.email = vm.requestUser ? (
                    vm.requestUser.email ? vm.requestUser.email : vm.requestUser) : "";
//                vm.newProfile.slug = "XXX";
                vm.create();
            }
        },
        refresh: function() {
            // overridden in subclasses.
        },
        removeConfirm: function(idx) { // saas/_user_card.html
            var vm = this;
            var role = vm.items.results[idx];
            vm.toDelete.idx = idx;
            if( role.user && role.user.slug === vm.requestUser ) {
                vm.$emit('remove');
            } else {
                vm.remove();
            }
        },
        remove: function(idx){ // saas/_user_card.html
            var vm = this;
            if( typeof idx === 'undefined' ) {
                idx = vm.toDelete.idx;
            }
            var role = vm.items.results[idx];
            vm.reqDelete(role.remove_api_url, function() {
                // splicing instead of refetching because
                // subsequent fetch might fail due to 403
                vm.items.results.splice(idx, 1);
                if( role.grant_key ) { vm.items.invited_count -= 1; }
                if( role.request_key ) { vm.items.requested_count -= 1; }
                vm.toDelete.idx = null;
                vm.$emit('remove-completed');
            });
        },
        reset: function() {
            var vm = this;
            vm.candidateId = "";
            vm.unregistered = {slug: "", email: "", full_name: ""};
            vm.newProfile = {slug: "", email: "", full_name: ""};
            vm.profileRequestDone = false;
            vm.inNewProfileFlow = false;
            if( vm.$refs.typeahead ) {
                vm.$refs.typeahead.reset();
                vm.$refs.typeahead.$refs.input.focus();
            }
        },
        save: function(item){ // user-typeahead @item-save="save"
            this._addRole(item);
        },
        submit: function() {
            var vm = this;
            if( vm.newProfile.full_name || vm.newProfile.full_name ||
                vm.newProfile.email ) {
                vm.create();
            } else {
                if( vm.unregistered.slug || vm.unregistered.email) {
                    this._addRole(vm.unregistered, vm.profileRequestDone);
                } else {
                    this._addRole(
                        (vm.$refs.typeahead && vm.$refs.typeahead.query) ?
                            vm.$refs.typeahead.query : vm.candidateId,
                        vm.profileRequestDone);
                }
            }
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
    mounted: function() {
        if( this.$el.dataset ) {
            this.params.role_status = this.$el.dataset.roleStatus;
        }
        this.get();
    }
}

/**
 XXX used in conjunction with ``itemListMixin`` in ``subscriptionListMixin``
 to compute cut-off dates.
 */
var subscriptionDetailMixin = {
    mixins: [
        timezoneMixin
    ],
    data: function(){
        return {
            api_profile_url: this.$urls.organization.api_profile_base,
            ends_at: this.datetimeOrNow(
                this.$dateRange ? this.$dateRange.ends_at : null, 'endOfDay'),
        }
    },
    methods: {
        acceptRequest: function(profile, request_key) {
            var vm = this;
            vm.reqPost(vm.acceptRequestURL(profile, request_key),
            function (){
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
            var cutOff = moment(vm.ends_at).add(5, 'days');
            var subEndsAt = moment(subscription.ends_at);
            if( subEndsAt < cutOff ) {
                return "bg-warning";
            }
            return "";
        },
        refId: function(item, id){
            var ids = [item.profile.slug,
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
        toggleEndsAt: function (item, event) {
            var vm = this;
            vm.$set(item, '_editEndsAt', !item._editEndsAt);
            if( item._editEndsAt ) {
                vm.$nextTick(function(){
                    vm.$refs['editEndsAt_' + item.code][0].focus();
                });
            } else {
                item.ends_at = vm.asDateISOString(event.target.value);
                vm.update(item);
            }
        },
        update: function(item) {
            var vm = this;
            var url = vm.subscriptionURL(item.profile.slug, item.plan.slug);
            var data = {
                description: item.description,
                ends_at: item.ends_at
            };
            vm.reqPatch(url, data);
        },
        acceptRequestURL: function(profile, request_key) {
           var vm = this;
           return vm._safeUrl(vm.api_profile_url,
                profile + "/subscribers/accept/" + request_key + "/");
        },
        subscriptionURL: function(profile, plan) {
           var vm = this;
            return vm._safeUrl(vm.api_profile_url,
                profile + "/subscriptions/" + plan);
        },
    }
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
            var url = vm.subscribersURL(vm.plan.profile, vm.plan.slug);
            var data = {profile: org};
            vm.itemsLoaded = false;
            vm.reqPost(url, data, function (){
                vm.get();
            });
        },
        selected: function(idx){
            var item = this.items.results[idx];
            item.ends_at = (new Date(item.ends_at)).toISOString();
            this.update(item);
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
        subscribersURL: function(provider, plan) {
            var vm = this;
            return vm._safeUrl(vm.api_profile_url,
                provider + "/plans/" + plan + "/subscriptions");
        },
    },
    mounted: function(){
        this.get();
    }
}

Vue.component('user-typeahead', {
    template: "",
    props: [
        'url',
        'role'
    ],
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
                if(cb) cb(); else vm.get();
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
        toggleEndsAt: function (item, event) {
            var vm = this;
            if( item._editEndsAt ) {
                item.ends_at = vm.asDateISOString(event.target.value);
                vm.update(item, function() {
                    vm.$set(item, '_editEndsAt', !item._editEndsAt);
                });
            } else {
                vm.$set(item, '_editEndsAt', !item._editEndsAt);
                vm.$nextTick(function(){
                    vm.$refs['editEndsAt_' + item.code][0].focus();
                });
            }
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
    }
}


Vue.component('coupon-list', {
    mixins: [
        itemListMixin,
        couponDetailMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_coupons,
            api_plans_url: this.$urls.provider.api_plans,
            params: {
                o: 'ends_at',
            },
            newCoupon: {
                code: '',
                discount_type: 'percentage',
                discount_value: 0
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
            vm.reqDelete(vm._safeUrl(vm.url, code),
            function() {
                vm.get();
            });
        },
        save: function(){
            var vm = this;
            var data = {};
            for( var key in vm.newCoupon ) {
                if( vm.newCoupon.hasOwnProperty(key) ) {
                    if( key === 'discount_value' ) {
                        data[key] = vm.newCoupon[key] * 100;
                    } else {
                        data[key] = vm.newCoupon[key];
                    }
                }
            }
            vm.reqPost(vm.url, data,
            function() {
                vm.get();
                vm.newCoupon = {
                    code: '',
                    discount_type: 'percentage',
                    discount_value: 0
                }
            });
        },
        getPlans: function(){
            var vm = this;
            vm.reqGet(vm.api_plans_url,
                {active: true}, function(res){
                vm.plans = res.results;
                vm.$forceUpdate();
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
        planTitle: function(plan){
            var vm = this;
            if( typeof plan.title !== 'undefined' ) {
                return plan.title;
            }
            if( vm.plans.length > 0 ) {
                for( var idx = 0; idx < vm.plans.length; ++idx ) {
                    if( vm.plans[idx].slug === plan ) {
                        return vm.plans[idx].title;
                    }
                }
            }
            return "";
        },
    },
    mounted: function(){
        this.get()
        this.getPlans()
    }
});


/** Lists users recently registered.
    XXX only used in saas testsite.
 */
Vue.component('user-list', {
    mixins: [
        itemListMixin,
        timezoneMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_accounts,
            params: {
                start_at: this.datetimeOrNow(
                    this.$dateRange ? this.$dateRange.start_at : null,
                    'startOfDay'),
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
            url: this.$urls.user.api_accessibles,
            create_url: this.$urls.user.api_profile_create,
            typeaheadUrl: this.$urls.api_candidates,
            showInvited: false,
            showRequested: false,
            params: {
                role_status: "",
                include_personal_profile: true,
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
            url: this.$urls.organization.api_roles,
            typeaheadUrl: this.$urls.api_candidates
        }
    },
    methods: {
        refresh: function() {
            var vm = this;
            vm.params = {};
            vm.showInvited = true;
            // You would think `showInvited = true` would trigger
            // the `watch` but it does not; or at least not consistently.
            // Better have two calls rather than none.
            vm.get();
        },
    }
});


/** XXX We need an ends_at and timezone to compute metrics accurately.
 */
Vue.component('metrics-charts', {
    mixins: [
        httpRequestMixin,
        timezoneMixin
    ],
    data: function() {
        var data = {
            tables: this.$tables,
            activeTab: 0,
            params: {
                ends_at: this.datetimeOrNow(
                    this.$dateRange ? this.$dateRange.ends_at : null),
                period_type: "monthly"
            },
        }
        return data;
    },
    methods: {
        fetchTableData: function(table, cb){
            var vm = this;
            var params = {
                ends_at: vm.params.ends_at,
                period_type: vm.params.period_type,
            };
            if( vm.timezone ) {
                params["timezone"] = vm.timezone;
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
                    download: table.download,
                    unit: unit,
                    scale: scale,
                    data: resp.results
                }
                // We have rationalized the unique id field names as 'slug',
                // but nv.d3.js expects 'key'.
                for( var idx = 0; idx < tableData.data.length; ++idx ) {
                    tableData.data[idx]['key'] = tableData.data[idx]['slug'];
                }
                for( var idx = 0; idx < vm.tables.length; ++idx ) {
                    if( vm.tables[idx].key === table.key ) {
                        vm.$set(vm.tables, idx, tableData);
                        break;
                    }
                }
                if(cb) cb();
            });
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
        currencyToSymbol: function(currency) {
            // This is a copy/paste from the definition of `currencyToSymbol`
            // in `itemListMixin`.
            if( currency === "usd" || currency === "cad" ) { return "$"; }
            else if( currency === "eur" ) { return "\u20ac"; }
            return currency;
        },
        tabClicked: function(index) {
            var vm = this;
            vm.activeTab = index;
            vm.prepareCurrentTabData();
        },
        tabTitle: function(table){
            var vm = this;
            var unit = '';
            if(table && table.unit){
                unit = ' (' + vm.currencyToSymbol(table.unit) + ')';
            }
            return table.title + unit;
        },
        activeClass: function(index) {
            var vm = this;
            var base = 'nav-link';
            return (index === vm.activeTab) ? base + " active" : base;
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
        },
        // Same as in `itemListMixin`.
        _ends_at: {
            get: function() {
                // form field input="date" will expect ends_at as a String
                // but will literally cut the hour part regardless of timezone.
                // We don't want an empty list as a result.
                // If we use moment `endOfDay` we get 23:59:59 so we
                // add a full day instead.
                const dateValue = moment(this.params.ends_at).add(1,'days');
                return dateValue.isValid() ? dateValue.format("YYYY-MM-DD") : null;
            },
            set: function(newVal) {
                this.$set(this.params, 'ends_at', this.asDateISOString(newVal));
                this.get();
            }
        },
        periodType: {
        get: function() {
          return this.params.period_type;
        },
        set: function(newVal) {
          this.$set(this.params, 'period_type', newVal);
          this.get();
        }
      },
    },
    mounted: function(){
        var vm = this;
        vm.get();
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
            url: this.$urls.broker.api_users_registered,
        }
    }
});


Vue.component('subscribed', {
    mixins: [
        subscriptionListMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_subscribers_active,
        }
    }
});


Vue.component('churned', {
    mixins: [
        subscriptionListMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_subscribers_churned,
        }
    }
});


Vue.component('lazy-load-tabs', {
    methods: {
        tabClicked: function(refName) {
            var vm = this;
            vm.$refs[refName].get();
        },
    }
});


Vue.component('lifetimevalue-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_metrics_lifetimevalue
        }
    },
    mounted: function(){
        this.get();
    }
});

Vue.component('balancesdue-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_metrics_balances_due
        }
    },
    mounted: function(){
        this.get();
    },
});


Vue.component('plan-subscriber-list', {
    mixins: [
        subscriptionListMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_plan_subscribers,
            typeaheadUrl: this.$urls.api_candidates,
            profileRequestDone: false,
            newItem: {},
        }
    },
    methods: {
        _addItem: function(item, force) {
            var vm = this;
            if( jQuery.type(item) === "string" ) {
                var stringVal = item;
                item = {slug: "", email: "", full_name: ""};
                var pattern = /@[a-zA-Z0-9\-]+\.([a-zA-Z\-]{2,3}|localdomain)/;
                if( pattern.test(stringVal) ) {
                    item['email'] = stringVal;
                } else {
                    item['full_name'] = stringVal;
                }
            }
            var data = {'profile':{'type': 'organization'}};
            var fields = ['slug', 'email', 'full_name', 'message'];
            for( var idx = 0; idx < fields.length; ++idx ) {
                if( item[fields[idx]] ) {
                    data['profile'][fields[idx]] = item[fields[idx]];
                }
            }
            vm.reqPost(vm.url + (force ? "?force=1" : ""), data,
                function() {
                    vm.resetNewItem();
                    vm.refresh();
                }, function() {
                    vm.profileRequestDone = true;
                    vm.newItem = item;
                    vm.$emit('invite');
                }
            );
        },
        resetNewItem: function() {
            var vm = this;
            vm.candidateId = "";
            vm.newItem = {slug: "", email: "", full_name: ""};
            vm.profileRequestDone = false;
            if( vm.$refs.account ) {
                vm.$refs.account.reset();
            }
            vm.$emit('invite-completed');
        },
        refresh: function() {
            this.get();
        },
        submit: function() {
            var vm = this;
            if( vm.newItem.slug || vm.newItem.email) {
                this._addItem(vm.newItem, vm.profileRequestDone);
            } else {
                this._addItem((vm.$refs.account && vm.$refs.account.query) ?
                    vm.$refs.account.query : vm.candidateId,
                    vm.profileRequestDone);
            }
        },
        updateItemSelected: function(item) {
            var vm = this;
            if( item ) {
                vm.newItem = item;
                vm.profileRequestDone = false;
                vm.submit();
            }
        },
    },
    computed: {
        requestedProfilePrintableName: function() {
            var vm = this;
            if( typeof vm.newItem !== 'undefined' ) {
                if( jQuery.type(vm.newItem) === "string" ) {
                    return vm.newItem ? vm.newItem : "The profile";
                }
                if( typeof vm.newItem.full_name !== 'undefined' &&
                    vm.newItem.full_name ) {
                    return vm.newItem.full_name;
                }
                if( typeof vm.newItem.email !== 'undefined' &&
                    vm.newItem.email ) {
                    return vm.newItem.email;
                }
            }
            return  "The profile";
        }
    },
});


Vue.component('subscription-list', {
    mixins: [
        subscriptionListMixin,
    ],
    data: function() {
        return {
            url: this.$urls.organization.api_subscriptions,
        }
    }
});


Vue.component('expired-subscription-list', {
    mixins: [
        subscriptionListMixin,
    ],
    data: function() {
        return {
            url: this._safeUrl(this.$urls.organization.api_subscriptions, 'expired')
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
            url: this.$urls.provider.api_metrics_coupon_uses,
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
            url: this.$urls.broker.api_charges,
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
            url: this.$urls.provider.api_plans,
        }
    },
    mounted: function(){
        this.get();
    }
});

/** XXX default value to import new transactions.
 */
Vue.component('import-transaction', {
    mixins: [
        httpRequestMixin,
        timezoneMixin,
    ],
    data: function() {
        return {
            url: this.$urls.organization.api_import,
            typeaheadUrl: this.$urls.provider.api_subscribers_active,
            itemSelected: '',
            entry: this.defaultNewItem(),
        }
    },
    methods: {
        defaultNewItem: function() {
            return {
                subscription: null,
                created_at: this.datetimeOrNow(),
                amount: 0,
                descr: '',
            }
        },
        addPayment: function(){
            var vm = this;
            if( vm.itemSelected ) {
                vm.entry.subscription = (vm.itemSelected.profile.slug
                    + ':' + vm.itemSelected.plan.slug);
            }
            vm.reqPost(vm.url, vm.entry,
            function(resp) {
                vm.clearNewPayment();
                if( resp.detail ) {
                    showMessages([resp.detail], "success");
                }
            });
        },
        clearNewPayment: function() {
            var vm = this;
            vm.itemSelected = '';
            vm.entry = vm.defaultNewItem();
        },
        get: function() {
            // We want to keep a single template for `date_input_field`.
        },
        updateItemSelected: function(item) {
            var vm = this;
            if( item ) {
                vm.itemSelected = item;
            }
        },
    },
    computed: {
        _created_at: {
            get: function() {
                return this.asDateInputField(this.entry.created_at);
            },
            set: function(newVal) {
                if( newVal ) {
                    // The setter might be call with `newVal === null`
                    // when the date is incorrect (ex: 09/31/2022).
                    this.$set(this.entry, 'created_at',
                        this.asDateISOString(newVal));
                }
            }
        },
    }
});


Vue.component('billing-statement', {
    mixins: [
        cardMixin,
        itemListMixin,
    ],
    data: function(){
        var res = {
            url: this.$urls.organization.api_transactions,
            api_cancel_balance_url: this.$urls.organization.api_cancel_balance_due,
            last4: (this.$labels && this.$labels.notAvailableLabel) || "N/A",
            exp_date: (this.$labels && this.$labels.notAvailableLabel) || "N/A",
            cardLoaded: false
        }
        return res;
    },
    methods: {
        getCard: function(){
            var vm = this;
            vm.reqGet(vm.api_card_url,
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
            vm.modalHide();
            vm.reqDelete(vm.api_cancel_balance_url,
                function() {
                    vm.reload()
                },
                function(resp){
                    vm.reload()
                    showErrorMessages(resp);
                }
            );
        },
        modalHide: function() {
            var vm = this;
            if( vm.dialog ) {
                vm.dialog.modal("hide");
            }
        }
    },
    computed: {
        dialog: function(){ // XXX depends on jQuery / bootstrap.js
            var dialog = $(this.$el).find('.modal');
            if(dialog && jQuery().modal){
                return dialog;
            }
        },
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
            url: this.$urls.organization.api_transactions,
            api_balance_url: this.$urls.provider.api_bank,
            balanceLoaded: false,
            last4: (this.$labels && this.$labels.notAvailableLabel) || "N/A",
            bank_name: (this.$labels && this.$labels.notAvailableLabel) || "N/A",
            balance_amount: (this.$labels && this.$labels.notAvailableLabel) || "N/A",
            balance_unit: '',
        }
    },
    methods: {
        getBalance: function() {
            var vm = this;
            vm.reqGet(vm.api_balance_url,
            function(resp){
                vm.balance_amount = resp.balance_amount;
                vm.balance_unit = resp.balance_unit;
                vm.last4 = resp.last4;
                vm.bank_name = resp.bank_name;
                vm.balanceLoaded = true;
            });
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
            url: this.$urls.organization.api_transactions,
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
            url: this.$urls.organization.api_base,
            picture_url: this.$urls.organization.api_profile_picture,
            verify_url: null,
            redirect_url: this.$urls.profile_redirect,
            formFields: {},
            countries: countries,
            regions: regions,
            currentPicture: null,
            picture: null,
            codeSent: false,
            profile_url: this.$urls.user_profiles,
        }
    },
    methods: {
        deleteProfile: function(){
            var vm = this;
            vm.reqDelete(vm.url,
                function() {
                    window.location = vm.redirect_url;
                }
            );
        },
        get: function(cb){
            var vm = this;
            vm.reqGet(vm.url,
            function(resp) {
                vm.formFields = resp;
                if(cb) cb();
            });
        },
        updateProfile: function(){
            var vm = this;
            vm.validateForm();
            var data = {}
            for( var field in vm.formFields ) {
                if( vm.formFields.hasOwnProperty(field) &&
                    vm.formFields[field] ) {
                    data[field] = vm.formFields[field];
                }
            }
            vm.reqPut(vm.url, data,
            function(resp) {
                if( resp.detail ) {
                    showMessages([resp.detail], "success");
                }
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
                    vm.picture_url,
                    form,
                    function(resp) {
                        vm.formFields.picture = resp.location;
                        vm.picture.remove();
                        vm.$forceUpdate();
                        showMessages(["Profile was updated."], "success");
                });
            }, 'image/png');
        },
        verifyEmail: function() {
            var vm = this;
            vm.reqPost(vm.verify_url, {email: vm.$refs.email.value},
            function(resp) {
                vm.modalHide();
                if( resp.detail ) {
                    vm.showMessages([resp.detail], "success");
                }
            }, function(resp) {
                vm.codeSent = true;
                if( resp.detail ) {
                    vm.showMessages([resp.detail], "success");
                }
            });
        },
        verifyPhone: function() {
            var vm = this;
            vm.reqPost(vm.verify_url, {email: vm.$refs.phone.value},
            function(resp) {
                vm.codeSent = true;
                if( resp.detail ) {
                    vm.showMessages([resp.detail], "success");
                }
            }, function(resp) {
                vm.codeSent = true;
                if( resp.detail ) {
                    vm.showMessages([resp.detail], "success");
                }
            });
        },
        submitCode: function() {
            // submit the one-time code that was e-mailed
            // or sent by text message.
            var vm = this;
            vm.reqPost(vm.verify_url, {code: vm.$refs.code.value},
            function(resp) {
                vm.modalHide();
                if( resp.detail ) {
                    vm.showMessages([resp.detail], "success");
                }
            });
        },
            convertToOrganization: function() {
              var vm = this;
                vm.reqPost(vm.profile_url + `?convert_from_personal=1`, { full_name: vm.formFields.full_name },
                    function(resp) {
                        if (  resp.detail  ) {
                            vm.showMessages([resp.detail], "success");
                        }
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


Vue.component('roledescr-list', {
    mixins: [
        itemListMixin
    ],
    data: function() {
        return {
            url: this.$urls.organization.api_role_descriptions,
            newItem: {title: ''},
        }
    },
    methods: {
        save: function() {
            var vm = this;
            vm.reqPost(vm.url, vm.newItem,
            function() {
                vm.newItem.title = '';
                vm.params.page = 1;
                vm.get()
            });
        },
        remove: function(role) {
            var vm = this;
            var url = vm.url + "/" + role.slug
            vm.reqDelete(url, function() {
                vm.params.page = 1;
                vm.get()
            });
        },
        update: function(role) {
            var vm = this;
            var url = vm.url + "/" + role.slug
            vm.reqPut(url, role, function() {
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
            url: this.$urls.api_broker_balances,
            balanceLineUrl : this.$urls.api_balance_lines,
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
        remove: function(id){
            var vm = this;
            vm.reqDelete(vm._safeUrl(vm.balanceLineUrl, id), function() {
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
            url: this.$urls.organization.api_checkout,
            api_cart_url: this.$urls.api_cart,
            api_redeem_url: this.$urls.api_redeem_coupon,
            receipt_url: this.$urls.organization.receipt,
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
            vm.reqDelete(vm.api_cart_url, {plan: plan},
            function() {
                vm.get();
            });
        },
        redeem: function(){
            var vm = this;
            vm.reqPost(vm.api_redeem_url, {code: vm.coupon},
            function(resp) {
                if( resp.detail ) {
                    showMessages([resp.detail], "success");
                }
                vm.get();
            });
        },
        getAndPrepareData: function(resp){
            var vm = this;
            var results = resp.results;
            var periods = {}
            var users = {}
            var optionsConfirmed = results.length > 0 ? true : false;
            var seatsConfirmed = results.length > 0 ? true : false;
            results.map(function(elm){
                var plan = elm.subscription.plan.slug;
                if( elm.options.length > 0 ){
                    optionsConfirmed = false;
                    if( vm.init ){
                        periods[plan] = 1;
                    }
                }
                if( elm.subscription.profile.is_bulk_buyer ) {
                    seatsConfirmed = false;
                }
                users[plan] = {
                    fullName: '', email: ''
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
                this.seatsConfirmed = seatsConfirmed;
            }
        },
        addPlanUser: function(plan){
            var vm = this;
            var user = this.planUser(plan);
            var data = {
                plan: plan,
                full_name: user.fullName,
                sync_on: user.email
            }
            var option = vm.plansOption[plan];
            if(option){
                data.option = option
            }
            vm.reqPost(vm.api_cart_url, data,
            function(resp) {
                if( resp.detail ) {
                    showMessages([resp.detail], "success");
                }
                vm.init = false;
                vm.$set(vm.plansUser, plan, {
                    fullName: '',
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
        optionSelected: function(plan, index){
            this.$set(this.plansOption, plan, index);
        },
        isOptionSelected: function(plan, index){
            var selected = this.plansOption[plan];
            return selected !== undefined && selected == index;
        },
        doCheckout: function(token){
            var vm = this;
            var opts = vm.getOptions();
            var data = {
                remember_card: true,
                items: opts,
                street_address: vm.card_address_line1,
                locality: vm.card_city,
                postal_code: vm.card_address_zip,
                country: vm.country,
                region: vm.region,
            }
            if(token){
                data.processor_token = token;
            }
            vm.reqPost(vm.url, data,
            function(resp) {
                window.location = vm.receiptUrl(resp.processor_key);
            });
        },
        nextStep: function(){
            var vm = this;
            if( vm.allConfirmed ) {
                if(vm.haveCardData){
                    vm.doCheckout();
                } else {
                    vm.getCardToken(vm.doCheckout);
                }
            } else if( !vm.optionsConfirmed ) {
                var queryArray = [];
                vm.items.results.map(function(elm){
                    var plan = elm.subscription.plan.slug;
                    if( elm.options.length > 0 ) {
                        var option = vm.plansOption[plan];
                        queryArray.push({
                            method: 'POST',
                            url: vm.api_cart_url,
                            data: {plan: plan, option: option}
                        })
                    }
                });
                vm.reqMultiple(queryArray,
                function() {
                    vm.get(); // `optionsConfirmed` will be set in `get`.
                });
            } else if( !vm.seatsConfirmed ) {
                vm.seatsConfirmed = true;
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
                        vm.getCardToken(vm.doCheckoutForm);
                    } else {
                        vm.doCheckoutForm();
                    }
                } else {
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
            vm.reqPostBlob(vm.bulkUploadUrl(plan),
                form,
                function(){
                    vm.get();
            });
        },
    },
    computed: {
        allConfirmed: function() {
            return this.optionsConfirmed && this.seatsConfirmed;
        },
        linesPrice: function() {
            var vm = this;
            var total = 0;
            var unit = 'usd';
            if(this.items.results){
                this.items.results.map(function(elm) {
                    var plan = elm.subscription.plan.slug;
                    if( elm.options.length > 0 ) {
                        var option = vm.plansOption[plan];
                        if( option !== undefined ) {
                            total += elm.options[option-1].dest_amount;
                            unit = elm.options[option-1].dest_unit;
                        }
                    }
                    elm.lines.map(function(line) {
                        total += line.dest_amount;
                        unit = line.dest_unit;
                    });
                });
            }
            return [total / 100, unit];
        },
        bulkUploadUrl: function(plan) {
            var vm = this;
            return vm.api_cart + plan + "/upload/";
        },
        receiptUrl: function(processor_key) {
            var vm = this;
            return vm.receipt_url.replace('_', processor_key);
        }
    },
    mounted: function(){
        var vm = this;
        vm.get();
        vm.getUserCard();
        var cardData = vm.getCardFormData();
        if( !$.isEmptyObject(cardData) ) { // XXX jQuery
            vm.card_name = cardData['card_name'];
            vm.card_address_line1 = cardData['card_address_line1'];
            vm.card_city = cardData['card_city'];
            vm.card_address_zip = cardData['card_address_zip'];
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
            vm.deleteCard();
        },
        save: function(){
            var vm = this;
            vm.getCardToken(function(token){
                vm.reqPut(vm.api_card_url, {
                    token: token,
                    full_name: vm.card_name,
                    street_address: vm.card_address_line1,
                    locality: vm.card_city,
                    postal_code: vm.card_address_zip,
                    country: vm.country,
                    region: vm.region,
                },
                function(resp) {
                    // We do not get card information on the response
                    // from Stripe, only a paymentMethodId.
                    vm.clearCardData();
                    vm.savedCard.last4 = resp.last4;
                    vm.savedCard.exp_date = resp.exp_date;

                    // matching the code in `CardUpdateView` for redirects.
                    var redirectUrl = getUrlParameter('next');
                    if( redirectUrl ) {
                        window.location = redirectUrl;
                    }
                    if( resp.detail ) {
                        showMessages([resp.detail], "success");
                    }
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
            url: (this.$urls.plan ?
                this.$urls.plan.api_plan : null),
            api_plans_url: this.$urls.provider.api_plans,
            redirect_url: this.$urls.provider.metrics_plans,
            formFields: {
                unit: 'usd',
            },
            isActive: false,
        }
    },
    methods: {
        _populateParams: function() {
            var vm = this;
            vm.validateForm();
            var data = {};
            var advance_discount = {};
            for( var field in vm.formFields ) {
                if( vm.formFields.hasOwnProperty(field) ) {
                    if( field == 'advance_discount_type' ) {
                        advance_discount['discount_type'] =
                            vm.formFields[field];
                    } else if( field == 'advance_discount_value' ) {
                        advance_discount['discount_value'] =
                            parseFloat(vm.formFields[field]);
                    } else if( field == 'advance_discount_length' ) {
                        advance_discount['length'] =
                            parseInt(vm.formFields[field]);
                    } else {
                        data[field] = vm.formFields[field];
                    }
                }
            }
            if( data.period_amount ) {
                data.period_amount = Math.round(data.period_amount * 100);
            }
            if( data.setup_amount ) {
                data.setup_amount = Math.round(data.setup_amount * 100);
            }
            if( advance_discount && advance_discount.discount_value ) {
                data['advance_discounts'] = [advance_discount];
                for( var idx = 0; idx < data.advance_discounts.length; ++idx ) {
                    if( data.advance_discounts[idx].discount_type !== 'period' ) {
                        data.advance_discounts[idx].discount_value = Math.round(
                            data.advance_discounts[idx].discount_value * 100);
                    }
                }
            }
            return data;
        },
        createPlan: function(){
            var vm = this;
            vm.reqPost(vm.api_plans_url, vm._populateParams(),
            function() {
                window.location = vm.redirect_url;
            });
        },
        deletePlan: function(){
            var vm = this;
            vm.reqDelete(vm.url,
            function() {
                window.location = vm.redirect_url;
            });
        },
        get: function(){
            if(!vm.url) return;
            var vm = this;
            vm.reqGet(vm.url,
            function(resp) {
                vm.formFields = resp;
                vm.formFields.period_amount = vm.formatNumber(
                    resp.period_amount);
                vm.formFields.setup_amount = vm.formatNumber(
                    resp.setup_amount);
                for( var idx = 0; idx < resp.advance_discounts.length; ++idx ) {
                    vm.formFields.advance_discount_type =
                        resp.advance_discounts[idx].discount_type;
                    vm.formFields.advance_discount_value = vm.formatNumber(
                        resp.advance_discounts[idx].discount_value);
                    vm.formFields.advance_discount_length =
                        resp.advance_discounts[idx].length;
                }
                vm.isActive = resp.is_active;
            });
        },
        formatNumber: function(num){
            return (parseFloat(num) / 100).toFixed(2);
        },
        togglePlanStatus: function(){
            var vm = this;
            var next = !vm.isActive;
            vm.reqPut(vm.url, {is_active: next},
            function(){
                vm.isActive = next;
            });
        },
        updatePlan: function(){
            var vm = this;
            if( vm.url ) {
                vm.reqPut(vm.url, vm._populateParams(),
                function(resp) {
                    showMessages([resp.detail], "success");
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

// Widgets for activity page
// -------------------------
Vue.component('engaged-subscribers', {
    mixins: [
        itemListMixin
    ],
    data: function(){
        return {
            url: this.$urls.api_engaged_subscribers,
            messagesElement: '#engaged-subscribers-content',
            scrollToTopOnMessages: false
        }
    },
    methods: {
    },
    mounted: function(){
        this.params.ends_at = null;
        this.get();
    },
});


Vue.component('unengaged-subscribers', {
    mixins: [
        itemListMixin
    ],
    data: function(){
        return {
            url: this.$urls.api_unengaged_subscribers,
            messagesElement: '#unengaged-subscribers-content',
            scrollToTopOnMessages: false
        }
    },
    methods: {
        showHideRoles: function(entry) {
            var vm = this;
            if( !entry.roles ) {
                vm.reqGet(vm._safeUrl(vm.$urls.organization.api_profile_base,
                    entry.slug) + '/roles',
                function success(resp) {
                    // Vue.set(entry, 'roles', [{printable_name: "Alice"}]);
                    Vue.set(entry, 'roles', resp.results);
                });
            }
        }
    },
    mounted: function(){
        this.get()
    },
});


// Widgets for dashboard
// ---------------------

Vue.component('search-profile', {
    mixins: [
        typeAheadMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_accounts,
        }
    }
});


Vue.component('subscription-typeahead', {
    mixins: [
        typeAheadMixin
    ],
    methods: {
        onHit: function onHit(newItem) {
            var vm = this;
            vm.$emit('selectitem', newItem);
            vm.clear();
        }
    }
});


Vue.component('today-sales', {
    mixins: [
        itemListMixin,
        timezoneMixin
    ],
    data: function() {
        return {
            url: this.$urls.provider.api_receivables,
            params: {
                start_at: this.datetimeOrNow(
                    this.$dateRange ? this.$dateRange.start_at : null,
                    'startOfDay'),
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
            url: this.$urls.provider.api_revenue,
        }
    },
    computed: {
        amount: function(){
            var amount = 0;
            if(this.itemLoaded){
                this.item.results.forEach(function(e){
                    if(e.slug === 'Total Sales'){
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

Vue.component('active-carts', {
    mixins: [itemListMixin],
    data: function(){
        return {
            url: this.$urls.saas_api_cartitems,
            api_pricing: this.$urls.saas_api_pricing,
            plans: {},
            byUser: [],
            getCompleteCb: '_decorateCartItems',
        };
    },
    methods: {
        _decorateCartItems: function(item) {
            var vm = this;
            vm.items.results.forEach(vm.addCartItemToUser);
        },
        getKey: function (cartItem) {
            return cartItem.user ?
                cartItem.user.slug : cartItem.claim_code;
        },
        addCartItemToUser: function(cartItem) {
            var vm = this;
            const cartItemId = vm.getKey(cartItem);
            const foundUser = vm.byUser.find(function(item) {
                return item.username === cartItemId;
            });
            if( foundUser ) {
                var plan = vm.plans[cartItem.plan.slug];
                if (plan) {
                    foundUser.totalAmount += cartItem.quantity * plan.period_amount * 0.01;
                }
                foundUser.totalItems++;
                if (cartItem.created_at > foundUser.latestUpdate) {
                    foundUser.latestUpdate = cartItem.created_at;
                }
            } else {
                var newUser = {
                    username: cartItemId,
                    email: cartItem.email || (cartItem.user ? cartItem.user.email : ''),
                    totalAmount: 0,
                    totalItems: 1,
                    latestUpdate: cartItem.created_at
                };
                vm.byUser.push(newUser);
            }
        },
        fetchPlans: function() {
            var vm = this;
            vm.reqGet(vm.api_pricing, function(resp) {
                vm.plans = resp.results.reduce((acc, plan) => {
                    acc[plan.slug] = plan;
                    return acc;
                });
            });
        },
    },
    mounted: function () {
        this.fetchPlans();
        this.get();
    }
});


Vue.component('user-active-cart', {
    mixins: [itemListMixin],
    data: function(){
        return {
            url: this.$urls.saas_api_user_cartitems,
            crudUrl: this.$urls.saas_api_cartitems,
            api_pricing: this.$urls.saas_api_pricing,
            newItemPlan: null,
            newItemQuantity: 1,
            plans: [],
        };
    },
    methods: {
        addItem: function() {
            var vm = this;
            var data = {
                user: vm.items.user.slug,
                plan: vm.newItemPlan,
                quantity: vm.newItemQuantity
            };
            vm.reqPost(vm.crudUrl, data, vm.get);
        },
        updateItem: function(cartItem) {
            var vm = this;
            const data = { quantity: cartItem.quantity };
            vm.reqPatch(vm._safeUrl(crudUrl, cartItem.id), data, vm.get);
        },
        removeItem: function(cartItem) {
            var vm = this;
            vm.reqDelete(vm._safeUrl(vm.crudUrl, cartItem.id), vm.get);
        },
        fetchPlans: function() {
            var vm = this;
            vm.reqGet(vm.api_pricing, function(resp) {
                vm.plans = resp.results || [];
            });
        },
    },
    mounted: function(){
        this.fetchPlans();
        this.get();
    }
});
